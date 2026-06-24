"""
Join Center — safe SQL JOIN builder.

This module converts a structured ``JoinSpec`` dict into a fully-quoted,
dialect-aware SELECT statement.  It is designed to be the *only* path through
which user-supplied join metadata reaches the database, so it is conservative
about what it accepts:

* Identifiers (table names, column names, aliases) are matched against a
  whitelist pattern **and** cross-checked against a live schema snapshot taken
  from the adapter before any SQL is built.  Any identifier that could break
  out of the quoting character (backtick for MySQL, double-quote for everyone
  else) is rejected outright.
* Literals used in filter clauses are escaped with ``escape_literal`` — no
  string concatenation of raw user input ever reaches the SQL.
* Join types, operators, and direction keywords come from fixed sets of
  constants; any value outside the set raises ``JoinSpecError``.
* Hard caps are applied on columns, joins, and row count.

The module has zero external dependencies and is self-testable: run
``python core/join_center.py`` to exercise the identifier quoter, the literal
escaper, and the SQL builder against a fabricated schema.
"""

from __future__ import annotations

import math
import re
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SUPPORTED_DIALECTS = {"sqlite", "mysql", "postgresql", "mssql", "oracle"}
VALID_JOIN_TYPES = {"INNER", "LEFT", "RIGHT", "FULL", "CROSS"}
VALID_OPERATORS = {
    "=", "!=", "<>", "<", "<=", ">", ">=",
    "LIKE", "NOT LIKE", "IS NULL", "IS NOT NULL", "IN",
}
VALID_DIRECTIONS = {"ASC", "DESC"}

MAX_ROWS = 1000
MAX_JOINS = 10
MAX_COLUMNS = 200
DEFAULT_LIMIT = 100

# Must start with letter/underscore; alnum/_/$ segments separated by single
# spaces. No leading/trailing/consecutive spaces. ASCII-only by design.
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*(?: [A-Za-z0-9_$]+)*$")


class JoinSpecError(ValueError):
    """Raised when a JoinSpec fails validation."""


# ---------------------------------------------------------------------------
# Identifier & literal handling
# ---------------------------------------------------------------------------
def quote_ident(name: str, dialect: str) -> str:
    """Quote an identifier per dialect, rejecting anything suspicious."""
    if not isinstance(name, str) or not name:
        raise JoinSpecError("Identifier must be a non-empty string.")
    if not _IDENT_RE.match(name):
        raise JoinSpecError(f"Invalid identifier: {name!r}")

    dialect = (dialect or "").lower()
    if dialect == "mysql":
        if "`" in name:
            raise JoinSpecError(f"Identifier contains illegal character: {name!r}")
        return f"`{name}`"
    if dialect == "mssql":
        if "[" in name or "]" in name:
            raise JoinSpecError(f"Identifier contains illegal character: {name!r}")
        return f"[{name}]"
    # sqlite, postgresql, oracle accept ANSI double-quotes
    if '"' in name:
        raise JoinSpecError(f"Identifier contains illegal character: {name!r}")
    return f'"{name}"'


def escape_literal(value: Any, dialect: str) -> str:
    """Turn a Python value into a safe SQL literal."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise JoinSpecError("Non-finite numeric literal not allowed.")
        return repr(value)
    if isinstance(value, str):
        if "\x00" in value:
            raise JoinSpecError("Null byte not allowed in string literal.")
        d = (dialect or "").lower()
        if d == "mysql":
            # MySQL treats `\` as an escape char in string literals unless
            # NO_BACKSLASH_ESCAPES is set — double both backslash and quote.
            escaped = value.replace("\\", "\\\\").replace("'", "''")
        else:
            escaped = value.replace("'", "''")
        return f"'{escaped}'"
    raise JoinSpecError(f"Unsupported literal type: {type(value).__name__}")


# ---------------------------------------------------------------------------
# Schema introspection
# ---------------------------------------------------------------------------
def build_schema_snapshot(adapter) -> dict:
    """Return a dialect-aware schema snapshot used for validation and UI hints."""
    dialect = getattr(adapter, "dialect", "") or ""
    tables_out: list[dict] = []

    try:
        table_names = adapter.list_tables() or []
    except Exception:
        table_names = []

    try:
        all_fks = adapter.get_foreign_keys() or []
    except Exception:
        all_fks = []

    fks_by_table: dict[str, list[dict]] = {}
    for fk in all_fks:
        fks_by_table.setdefault(fk.get("from_table", ""), []).append(fk)

    for tname in table_names:
        try:
            desc = adapter.describe_table(tname) or {}
        except Exception:
            desc = {}
        cols_in = desc.get("columns") or []
        cols_out = []
        for c in cols_in:
            cols_out.append({
                "name": c.get("name", ""),
                "type": c.get("type", ""),
                "pk": bool(c.get("primary_key", False)),
            })
        # Adapters expose two FK shapes: describe_table uses {"from","to_table","to_column"};
        # get_foreign_keys uses {"from_table","from_column","to_table","to_column"}.
        # Normalize to the latter so suggest_joins can rely on a single shape.
        raw_fks = desc.get("foreign_keys") or fks_by_table.get(tname, [])
        norm_fks = []
        for fk in raw_fks:
            norm_fks.append({
                "from_table": fk.get("from_table", tname),
                "from_column": fk.get("from_column") or fk.get("from", ""),
                "to_table": fk.get("to_table", ""),
                "to_column": fk.get("to_column", ""),
            })
        tables_out.append({
            "name": tname,
            "columns": cols_out,
            "foreign_keys": norm_fks,
        })

    return {"dialect": dialect, "tables": tables_out}


def _table_lookup(schema: dict) -> dict:
    return {t["name"]: t for t in schema.get("tables", [])}


def _column_names(table: dict) -> set:
    return {c["name"] for c in table.get("columns", [])}


# ---------------------------------------------------------------------------
# Join suggestions
# ---------------------------------------------------------------------------
def suggest_joins(adapter, left_table: str, right_table: str) -> list:
    """Suggest plausible join conditions between two tables."""
    schema = build_schema_snapshot(adapter)
    tables = _table_lookup(schema)
    left = tables.get(left_table)
    right = tables.get(right_table)
    if not left or not right:
        return []

    suggestions: list[dict] = []
    seen: set = set()

    # FK-driven suggestions (both directions)
    for fk in left.get("foreign_keys", []) or []:
        if fk.get("from_table") == left_table and fk.get("to_table") == right_table:
            key = (fk["from_column"], fk["to_column"])
            if key not in seen:
                seen.add(key)
                suggestions.append({
                    "left": f"{left_table}.{fk['from_column']}",
                    "right": f"{right_table}.{fk['to_column']}",
                    "confidence": "fk",
                })
    for fk in right.get("foreign_keys", []) or []:
        if fk.get("from_table") == right_table and fk.get("to_table") == left_table:
            key = (fk["to_column"], fk["from_column"])
            if key not in seen:
                seen.add(key)
                suggestions.append({
                    "left": f"{left_table}.{fk['to_column']}",
                    "right": f"{right_table}.{fk['from_column']}",
                    "confidence": "fk",
                })

    # Name-match fallback
    left_cols = _column_names(left)
    right_cols = _column_names(right)
    for col in sorted(left_cols & right_cols):
        key = (col, col)
        if key in seen:
            continue
        seen.add(key)
        suggestions.append({
            "left": f"{left_table}.{col}",
            "right": f"{right_table}.{col}",
            "confidence": "name-match",
        })

    return suggestions


# ---------------------------------------------------------------------------
# SQL builder
# ---------------------------------------------------------------------------
def _ensure_dialect(schema: dict) -> str:
    dialect = (schema.get("dialect") or "").lower()
    if dialect not in SUPPORTED_DIALECTS:
        raise JoinSpecError(f"Unsupported dialect: {dialect!r}")
    return dialect


def _validate_column(alias_to_table: dict, ref_name: str, column: str) -> None:
    table = alias_to_table.get(ref_name)
    if table is None:
        raise JoinSpecError(f"Unknown table/alias in reference: {ref_name!r}")
    if column not in _column_names(table):
        raise JoinSpecError(f"Column {column!r} not found in {ref_name!r}.")


def _qualify(ref_name: str, column: str, dialect: str) -> str:
    return f"{quote_ident(ref_name, dialect)}.{quote_ident(column, dialect)}"


def build_join_sql(spec: dict, schema: dict) -> str:
    """Validate a JoinSpec against the schema and build a safe SELECT statement."""
    if not isinstance(spec, dict):
        raise JoinSpecError("JoinSpec must be an object.")

    dialect = _ensure_dialect(schema)
    tables = _table_lookup(schema)

    base_table = spec.get("base_table")
    if not isinstance(base_table, str) or not base_table:
        raise JoinSpecError("base_table is required.")
    if base_table not in tables:
        raise JoinSpecError(f"Unknown base_table: {base_table!r}")

    joins = spec.get("joins") or []
    if not isinstance(joins, list):
        raise JoinSpecError("joins must be a list.")
    if len(joins) > MAX_JOINS:
        raise JoinSpecError(f"Too many joins (max {MAX_JOINS}).")

    # Build alias map: alias -> table def.  base_table is its own alias.
    alias_to_table: dict = {base_table: tables[base_table]}
    resolved_joins: list[dict] = []  # with normalized alias
    for idx, j in enumerate(joins):
        if not isinstance(j, dict):
            raise JoinSpecError(f"join[{idx}] must be an object.")
        jtype = (j.get("type") or "INNER").upper()
        if jtype not in VALID_JOIN_TYPES:
            raise JoinSpecError(f"Invalid join type: {jtype!r}")
        jtable = j.get("table")
        if not isinstance(jtable, str) or jtable not in tables:
            raise JoinSpecError(f"Unknown join table: {jtable!r}")
        alias = j.get("alias") or jtable
        if not isinstance(alias, str) or not alias:
            raise JoinSpecError(f"Invalid alias for join[{idx}].")
        # Validate alias pattern up front (quote_ident would catch it later too)
        if not _IDENT_RE.match(alias):
            raise JoinSpecError(f"Invalid alias: {alias!r}")
        if alias in alias_to_table:
            raise JoinSpecError(f"Duplicate alias: {alias!r}")
        alias_to_table[alias] = tables[jtable]

        on_clauses = j.get("on") or []
        if not isinstance(on_clauses, list):
            raise JoinSpecError(f"join[{idx}].on must be a list.")
        if jtype == "CROSS":
            if on_clauses:
                raise JoinSpecError("CROSS JOIN must have empty 'on'.")
        else:
            if not on_clauses:
                raise JoinSpecError(f"{jtype} JOIN requires at least one ON condition.")

        resolved_joins.append({
            "table": jtable,
            "alias": alias,
            "type": jtype,
            "on": on_clauses,
            "columns": j.get("columns"),
        })

    # ---- SELECT list ----
    select_parts: list[str] = []

    def _add_select(ref: str, columns):
        if columns is None or columns == []:
            select_parts.append(f"{quote_ident(ref, dialect)}.*")
            return
        if not isinstance(columns, list):
            raise JoinSpecError(f"columns for {ref!r} must be a list.")
        for col in columns:
            if not isinstance(col, str):
                raise JoinSpecError(f"Column name must be a string in {ref!r}.")
            _validate_column(alias_to_table, ref, col)
            select_parts.append(_qualify(ref, col, dialect))

    _add_select(base_table, spec.get("base_columns"))
    for j in resolved_joins:
        _add_select(j["alias"], j["columns"])

    if len(select_parts) > MAX_COLUMNS:
        raise JoinSpecError(f"Too many columns selected (max {MAX_COLUMNS}).")
    if not select_parts:
        raise JoinSpecError("No columns selected.")

    # ---- FROM + JOIN ----
    from_clause = f"FROM {quote_ident(base_table, dialect)}"
    join_sql_parts: list[str] = []
    for j in resolved_joins:
        jtype = j["type"]
        keyword = "CROSS JOIN" if jtype == "CROSS" else f"{jtype} JOIN"
        piece = f"{keyword} {quote_ident(j['table'], dialect)}"
        if j["alias"] != j["table"]:
            piece += f" AS {quote_ident(j['alias'], dialect)}"
        if jtype != "CROSS":
            on_sqls = []
            for cond in j["on"]:
                if not isinstance(cond, dict):
                    raise JoinSpecError("ON condition must be an object.")
                lt = cond.get("left_table")
                lc = cond.get("left_column")
                rt = cond.get("right_table")
                rc = cond.get("right_column")
                op = (cond.get("op") or "=").strip()
                if op not in {"=", "!=", "<>", "<", "<=", ">", ">="}:
                    raise JoinSpecError(f"Unsupported ON operator: {op!r}")
                if not (isinstance(lt, str) and isinstance(lc, str)
                        and isinstance(rt, str) and isinstance(rc, str)):
                    raise JoinSpecError("ON condition fields must be strings.")
                _validate_column(alias_to_table, lt, lc)
                _validate_column(alias_to_table, rt, rc)
                on_sqls.append(
                    f"{_qualify(lt, lc, dialect)} {op} {_qualify(rt, rc, dialect)}"
                )
            piece += " ON " + " AND ".join(on_sqls)
        join_sql_parts.append(piece)

    # ---- WHERE ----
    filters = spec.get("filters") or []
    if filters and not isinstance(filters, list):
        raise JoinSpecError("filters must be a list.")
    where_parts: list[str] = []
    for f in filters:
        if not isinstance(f, dict):
            raise JoinSpecError("Each filter must be an object.")
        ref = f.get("table")
        col = f.get("column")
        op = (f.get("op") or "=").upper().strip()
        if op not in VALID_OPERATORS:
            raise JoinSpecError(f"Invalid filter operator: {op!r}")
        if not isinstance(ref, str) or not isinstance(col, str):
            raise JoinSpecError("Filter table/column must be strings.")
        _validate_column(alias_to_table, ref, col)
        qualified = _qualify(ref, col, dialect)
        if op in {"IS NULL", "IS NOT NULL"}:
            if f.get("value") not in (None, ""):
                raise JoinSpecError(f"{op} filter must not have a value.")
            where_parts.append(f"{qualified} {op}")
        elif op == "IN":
            values = f.get("value")
            if not isinstance(values, list) or not values:
                raise JoinSpecError("IN filter requires a non-empty list.")
            literals = ", ".join(escape_literal(v, dialect) for v in values)
            where_parts.append(f"{qualified} IN ({literals})")
        else:
            if "value" not in f:
                raise JoinSpecError(f"Filter with op {op!r} requires a value.")
            if f["value"] is None:
                raise JoinSpecError(
                    f"Use 'IS NULL' / 'IS NOT NULL' instead of {op!r} with null value."
                )
            where_parts.append(f"{qualified} {op} {escape_literal(f['value'], dialect)}")

    # ---- ORDER BY ----
    order_by = spec.get("order_by") or []
    if order_by and not isinstance(order_by, list):
        raise JoinSpecError("order_by must be a list.")
    order_parts: list[str] = []
    for o in order_by:
        if not isinstance(o, dict):
            raise JoinSpecError("Each order_by entry must be an object.")
        ref = o.get("table")
        col = o.get("column")
        direction = (o.get("dir") or "ASC").upper()
        if direction not in VALID_DIRECTIONS:
            raise JoinSpecError(f"Invalid order direction: {direction!r}")
        if not isinstance(ref, str) or not isinstance(col, str):
            raise JoinSpecError("order_by table/column must be strings.")
        _validate_column(alias_to_table, ref, col)
        order_parts.append(f"{_qualify(ref, col, dialect)} {direction}")

    # ---- LIMIT ----
    limit = spec.get("limit")
    if limit is None:
        limit = DEFAULT_LIMIT
    if not isinstance(limit, int) or isinstance(limit, bool):
        raise JoinSpecError("limit must be an integer.")
    if limit < 1:
        raise JoinSpecError("limit must be >= 1.")
    limit = min(limit, MAX_ROWS)

    # ---- Assemble ----
    sql = "SELECT " + ", ".join(select_parts) + "\n" + from_clause
    if join_sql_parts:
        sql += "\n" + "\n".join(join_sql_parts)
    if where_parts:
        sql += "\nWHERE " + " AND ".join(where_parts)
    if order_parts:
        sql += "\nORDER BY " + ", ".join(order_parts)
    sql += f"\nLIMIT {limit}"
    return sql


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------
def execute_join(adapter, spec: dict) -> dict:
    """Build, execute, and return the result of a JoinSpec."""
    schema = build_schema_snapshot(adapter)
    if not isinstance(spec, dict):
        raise JoinSpecError("JoinSpec must be an object.")
    # Hard-cap limit before building SQL.
    capped_spec = dict(spec)
    raw_limit = capped_spec.get("limit")
    if raw_limit is None:
        effective_limit = DEFAULT_LIMIT
    elif isinstance(raw_limit, int) and not isinstance(raw_limit, bool):
        effective_limit = min(max(raw_limit, 1), MAX_ROWS)
    else:
        raise JoinSpecError("limit must be an integer.")
    capped_spec["limit"] = effective_limit

    sql = build_join_sql(capped_spec, schema)
    columns, rows = adapter.execute(sql)
    row_list = [list(r) for r in rows] if rows else []
    return {
        "sql": sql,
        "columns": list(columns or []),
        "rows": row_list,
        "row_count": len(row_list),
        "truncated": len(row_list) >= effective_limit,
    }


# ---------------------------------------------------------------------------
# Self-tests
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    failures: list[str] = []

    def check(label: str, cond: bool, detail: str = "") -> None:
        if cond:
            print(f"  PASS  {label}")
        else:
            failures.append(f"{label}: {detail}")
            print(f"  FAIL  {label}  {detail}")

    print("quote_ident")
    check("accepts simple name",
          quote_ident("Customer", "sqlite") == '"Customer"')
    check("accepts 'Order Details'",
          quote_ident("Order Details", "sqlite") == '"Order Details"')
    check("mysql uses backticks",
          quote_ident("Customer", "mysql") == "`Customer`")
    try:
        quote_ident('x"; DROP', "sqlite")
        check("rejects double-quote injection", False, "no error raised")
    except JoinSpecError:
        check("rejects double-quote injection", True)
    try:
        quote_ident("a`b", "mysql")
        check("rejects backtick injection", False, "no error raised")
    except JoinSpecError:
        check("rejects backtick injection", True)
    try:
        quote_ident("1bad", "sqlite")
        check("rejects leading digit", False, "no error raised")
    except JoinSpecError:
        check("rejects leading digit", True)
    try:
        quote_ident("bad;name", "sqlite")
        check("rejects semicolon", False, "no error raised")
    except JoinSpecError:
        check("rejects semicolon", True)

    print("escape_literal")
    check("None -> NULL", escape_literal(None, "sqlite") == "NULL")
    check("True -> 1", escape_literal(True, "sqlite") == "1")
    check("False -> 0", escape_literal(False, "sqlite") == "0")
    check("int", escape_literal(42, "sqlite") == "42")
    check("float", escape_literal(1.5, "sqlite") == "1.5")
    check("str with quote",
          escape_literal("O'Brien", "sqlite") == "'O''Brien'")
    try:
        escape_literal(float("inf"), "sqlite")
        check("rejects inf", False, "no error")
    except JoinSpecError:
        check("rejects inf", True)
    try:
        escape_literal("a\x00b", "sqlite")
        check("rejects null byte", False, "no error")
    except JoinSpecError:
        check("rejects null byte", True)

    print("build_join_sql")
    schema = {
        "dialect": "sqlite",
        "tables": [
            {"name": "customers",
             "columns": [{"name": "id", "type": "INT", "pk": True},
                         {"name": "name", "type": "TEXT", "pk": False}],
             "foreign_keys": []},
            {"name": "orders",
             "columns": [{"name": "id", "type": "INT", "pk": True},
                         {"name": "customer_id", "type": "INT", "pk": False},
                         {"name": "total", "type": "REAL", "pk": False}],
             "foreign_keys": [{"from_table": "orders", "from_column": "customer_id",
                               "to_table": "customers", "to_column": "id"}]},
        ],
    }

    spec = {
        "base_table": "customers",
        "base_columns": ["id", "name"],
        "joins": [
            {"table": "orders", "type": "LEFT",
             "on": [{"left_table": "customers", "left_column": "id",
                     "right_table": "orders", "right_column": "customer_id",
                     "op": "="}],
             "columns": ["total"]},
        ],
        "filters": [
            {"table": "customers", "column": "name", "op": "LIKE", "value": "A%"},
            {"table": "orders", "column": "total", "op": "IS NOT NULL"},
        ],
        "order_by": [{"table": "orders", "column": "total", "dir": "DESC"}],
        "limit": 50,
    }
    sql = build_join_sql(spec, schema)
    check("SELECT present", sql.startswith("SELECT "))
    check("LEFT JOIN present", "LEFT JOIN \"orders\"" in sql)
    check("ON clause built", '"customers"."id" = "orders"."customer_id"' in sql)
    check("LIKE literal escaped", "LIKE 'A%'" in sql)
    check("IS NOT NULL built", '"orders"."total" IS NOT NULL' in sql)
    check("LIMIT applied", sql.rstrip().endswith("LIMIT 50"))

    # unknown column
    bad = dict(spec, base_columns=["nope"])
    try:
        build_join_sql(bad, schema)
        check("rejects unknown column", False, "no error")
    except JoinSpecError:
        check("rejects unknown column", True)

    # duplicate alias
    bad_alias = {
        "base_table": "customers",
        "joins": [
            {"table": "orders", "alias": "customers", "type": "INNER",
             "on": [{"left_table": "customers", "left_column": "id",
                     "right_table": "customers", "right_column": "customer_id",
                     "op": "="}]}
        ],
    }
    try:
        build_join_sql(bad_alias, schema)
        check("rejects duplicate alias", False, "no error")
    except JoinSpecError:
        check("rejects duplicate alias", True)

    # cross join requires empty on
    bad_cross = {
        "base_table": "customers",
        "joins": [{"table": "orders", "type": "CROSS",
                   "on": [{"left_table": "customers", "left_column": "id",
                           "right_table": "orders", "right_column": "customer_id",
                           "op": "="}]}],
    }
    try:
        build_join_sql(bad_cross, schema)
        check("rejects CROSS with ON", False, "no error")
    except JoinSpecError:
        check("rejects CROSS with ON", True)

    # mysql dialect uses backticks
    mysql_schema = dict(schema, dialect="mysql")
    mysql_sql = build_join_sql(spec, mysql_schema)
    check("mysql uses backticks", "`customers`.`id`" in mysql_sql)

    print()
    if failures:
        print(f"{len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        raise SystemExit(1)
    print("All self-tests passed.")
