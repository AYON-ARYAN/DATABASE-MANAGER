"""
Flask API Blueprint for React frontend.
All routes return JSON. Keeps existing routes in app.py intact.
"""
from datetime import datetime
from flask import Blueprint, request, session, jsonify

from werkzeug.security import generate_password_hash, check_password_hash

from core.validator import is_safe, classify_query
from core.snapshot import (
    take_snapshot, undo, list_snapshots,
    delete_snapshot, restore_snapshot
)
from core.llm import generate_query_with_explanation
from core.connection_manager import (
    list_connections, add_connection, delete_connection as rem_connection,
    get_adapter_for_connection, test_connection, test_new_connection,
)
from core.adapters import DB_TYPES, DB_DISPLAY_NAMES, DB_CONNECTION_FIELDS
from core.metrics import get_summary
from core.dashboards import list_dashboards, get_dashboard
from core import llm_manager

import os

api = Blueprint('api', __name__)

# ---------------------------------------------------
# Users & permissions (same as app.py)
# ---------------------------------------------------
USERS = {
    "viewer1": {"password": generate_password_hash("viewer123"), "role": "VIEWER"},
    "editor1": {"password": generate_password_hash("editor123"), "role": "EDITOR"},
    "admin1":  {"password": generate_password_hash("admin123"),  "role": "ADMIN"},
}

ROLE_PERMISSIONS = {
    "VIEWER": {"READ", "SYSTEM"},
    "EDITOR": {"READ", "WRITE", "SYSTEM"},
    "ADMIN":  {"READ", "WRITE", "SCHEMA", "SYSTEM"},
}

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
analysis_enabled = bool(GROQ_API_KEY)
PAGE_SIZE = 50


def is_allowed(role, task):
    return task in ROLE_PERMISSIONS.get(role, set())


def rows_to_list(rows):
    return [list(r) for r in rows] if rows else []


def get_active_adapter():
    name = session.get("active_db", "Default SQLite")
    try:
        return get_adapter_for_connection(name)
    except Exception:
        session["active_db"] = "Default SQLite"
        return get_adapter_for_connection("Default SQLite")


def get_active_db_info():
    name = session.get("active_db", "Default SQLite")
    connections = list_connections()
    for conn in connections:
        if conn["name"] == name:
            return {
                "name": name,
                "db_type": conn["db_type"],
                "display_type": DB_DISPLAY_NAMES.get(conn["db_type"], conn["db_type"]),
                "is_nosql": conn["db_type"] in ("mongodb", "redis"),
                "supports_snapshot": conn["db_type"] == "sqlite",
            }
    return {"name": name, "db_type": "sqlite", "display_type": "SQLite", "is_nosql": False, "supports_snapshot": True}


def is_system_query(sql):
    sql_l = sql.lower()
    return any(k in sql_l for k in ("sqlite_master", "pragma", "information_schema"))


def is_already_limited(sql):
    sql_l = sql.lower()
    return " limit " in sql_l or " offset " in sql_l


def paginate_sql(sql, page):
    sql = sql.rstrip(";")
    offset = (page - 1) * PAGE_SIZE
    return f"{sql} LIMIT {PAGE_SIZE} OFFSET {offset}"


def safe_count(adapter, sql):
    if is_system_query(sql) or is_already_limited(sql):
        return None
    try:
        _, rows = adapter.execute(f"SELECT COUNT(*) FROM ({sql.rstrip(';')}) AS subq")
        return rows[0][0] if rows else 0
    except Exception:
        return None


# ---------------------------------------------------
# Auth
# ---------------------------------------------------
@api.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.json or {}
    username = data.get('username', '')
    password = data.get('password', '')

    user = USERS.get(username)
    if not user or not check_password_hash(user["password"], password):
        return jsonify({"success": False, "error": "Invalid credentials"})

    session.clear()
    session["logged_in"] = True
    session["username"] = username
    session["role"] = user["role"]
    session["active_db"] = "Default SQLite"

    return jsonify({"success": True, "username": username, "role": user["role"]})


@api.route('/api/auth/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({"success": True})


@api.route('/api/auth/session', methods=['GET'])
def api_session():
    if session.get("logged_in"):
        return jsonify({
            "logged_in": True,
            "username": session.get("username"),
            "role": session.get("role"),
        })
    return jsonify({"logged_in": False}), 401


# ---------------------------------------------------
# Connections
# ---------------------------------------------------
@api.route('/api/connections', methods=['GET'])
def api_connections():
    conns = list_connections()
    return jsonify({
        "connections": conns,
        "active_db": session.get("active_db", "Default SQLite"),
        "db_info": get_active_db_info(),
        "llm_provider": session.get("llm_provider", "mistral"),
    })


@api.route('/api/connections', methods=['POST'])
def api_add_connection():
    data = request.json or {}
    name = data.get('name', '').strip()
    db_type = data.get('db_type', 'sqlite')
    config = data.get('config', {})

    result = add_connection(name, db_type, config)
    return jsonify(result)


@api.route('/api/connections/<name>', methods=['DELETE'])
def api_delete_connection(name):
    if name == "Default SQLite":
        return jsonify({"success": False, "message": "Cannot delete default connection"})
    if session.get("active_db") == name:
        session["active_db"] = "Default SQLite"
    result = rem_connection(name)
    return jsonify(result)


@api.route('/api/connections/select', methods=['POST'])
def api_select_connection():
    data = request.json or {}
    name = data.get('name', '')
    conns = list_connections()
    names = [c["name"] for c in conns]

    if name in names:
        session["active_db"] = name
        session.pop("last_read_sql", None)
        session.pop("last_read_columns", None)
        session.pop("last_sql", None)
        session.pop("last_task", None)
        session.pop("last_explanation", None)
        session.pop("conversation_context", None)
        return jsonify({"success": True, "db_info": get_active_db_info()})
    return jsonify({"success": False, "error": f"Connection '{name}' not found"})


@api.route('/api/db-types', methods=['GET'])
def api_db_types():
    return jsonify({
        "db_types": DB_TYPES,
        "db_display_names": DB_DISPLAY_NAMES,
        "db_fields": DB_CONNECTION_FIELDS,
    })


# ---------------------------------------------------
# Main Command Execution
# ---------------------------------------------------
@api.route('/api/command', methods=['POST'])
def api_command():
    data = request.json or {}
    user_cmd = data.get('command', '').strip()
    if not user_cmd:
        return jsonify({"error": "Empty command."})

    role = session.get("role", "VIEWER")
    adapter = get_active_adapter()
    dialect = adapter.dialect
    cmd_lower = user_cmd.lower().strip()

    # --- Hardcoded: DESCRIBE TABLE ---
    describe_match = None
    for prefix in ("describe ", "desc ", "show structure ", "show columns ", "show schema "):
        if cmd_lower.startswith(prefix):
            describe_match = user_cmd[len(prefix):].strip().strip(";").strip('"').strip("'")
            break

    if describe_match and hasattr(adapter, 'describe_table'):
        try:
            info = adapter.describe_table(describe_match)
            columns = ["Column", "Type", "Not Null", "Default", "Primary Key"]
            rows = []
            for c in info["columns"]:
                rows.append([c["name"], c["type"], "YES" if c["not_null"] else "NO",
                             c["default"] if c["default"] is not None else "", "YES" if c["primary_key"] else "NO"])
            if info["foreign_keys"]:
                rows.append(["", "", "", "", ""])
                rows.append(["--- FOREIGN KEYS ---", "", "", "", ""])
                for fk in info["foreign_keys"]:
                    rows.append([fk["from"], f"-> {fk['to_table']}.{fk['to_column']}", "", "", ""])
            if info["indexes"]:
                rows.append(["", "", "", "", ""])
                rows.append(["--- INDEXES ---", "", "", "", ""])
                for idx in info["indexes"]:
                    rows.append([idx["name"], ", ".join(idx["columns"]), "UNIQUE" if idx["unique"] else "", "", ""])

            session["last_read_sql"] = f'DESCRIBE "{describe_match}"'
            session["last_read_columns"] = columns
            return jsonify({"task": "SYSTEM", "columns": columns, "results": rows, "sql": f'DESCRIBE "{describe_match}"',
                            "explanation": f"Table '{describe_match}': {info['row_count']} rows", "total_rows": len(rows), "page": 1, "page_size": len(rows)})
        except Exception as e:
            return jsonify({"error": f"Table '{describe_match}' not found: {str(e)}"})

    # --- Hardcoded: SHOW FOREIGN KEYS ---
    if cmd_lower in ("show foreign keys", "list foreign keys", "show fk", "show fks",
                      "show relationships", "list relationships", "show refs", "show references"):
        if hasattr(adapter, 'get_foreign_keys'):
            fks = adapter.get_foreign_keys()
            columns = ["From Table", "From Column", "To Table", "To Column"]
            rows = [[fk["from_table"], fk["from_column"], fk["to_table"], fk["to_column"]] for fk in fks]
            if not rows:
                rows = [["No foreign keys found", "", "", ""]]
            session["last_read_sql"] = "-- Foreign Key Relationships"
            session["last_read_columns"] = columns
            return jsonify({"task": "SYSTEM", "columns": columns, "results": rows, "total_rows": len(rows), "page": 1, "page_size": len(rows),
                            "explanation": f"Found {len(fks)} foreign key relationships."})

    # --- FK for specific table ---
    fk_table_match = None
    for prefix in ("show foreign keys for ", "show fk for ", "show fks for ", "show references for ", "show refs for "):
        if cmd_lower.startswith(prefix):
            fk_table_match = user_cmd[len(prefix):].strip().strip(";").strip('"').strip("'")
            break
    if fk_table_match and hasattr(adapter, 'describe_table'):
        try:
            info = adapter.describe_table(fk_table_match)
            columns = ["From Column", "References Table", "References Column"]
            rows = [[fk["from"], fk["to_table"], fk["to_column"]] for fk in info["foreign_keys"]]
            if not rows:
                rows = [["No foreign keys found", "", ""]]
            return jsonify({"task": "SYSTEM", "columns": columns, "results": rows, "total_rows": len(rows), "page": 1, "page_size": len(rows),
                            "explanation": f"Foreign keys for '{fk_table_match}'."})
        except Exception as e:
            return jsonify({"error": str(e)})

    # --- SHOW INDEXES ---
    if cmd_lower in ("show indexes", "list indexes", "show index", "show indices"):
        if hasattr(adapter, 'get_indexes'):
            indexes = adapter.get_indexes()
            columns = ["Table", "Index Name", "Unique", "Columns"]
            rows = [[idx["table"], idx["index_name"], "YES" if idx["unique"] else "NO", ", ".join(idx["columns"])] for idx in indexes]
            if not rows:
                rows = [["No indexes found", "", "", ""]]
            return jsonify({"task": "SYSTEM", "columns": columns, "results": rows, "total_rows": len(rows), "page": 1, "page_size": len(rows),
                            "explanation": f"Found {len(indexes)} indexes."})

    # --- TABLE COUNTS ---
    if cmd_lower in ("show table counts", "show row counts", "count all tables", "table sizes"):
        try:
            tables = adapter.list_tables()
            columns = ["Table Name", "Row Count"]
            rows = []
            for t in tables:
                try:
                    _, cr = adapter.execute(f'SELECT COUNT(*) FROM "{t}"')
                    rows.append([t, cr[0][0] if cr else 0])
                except Exception:
                    rows.append([t, "Error"])
            session["last_read_sql"] = "-- Table Row Counts"
            session["last_read_columns"] = columns
            return jsonify({"task": "SYSTEM", "columns": columns, "results": rows, "total_rows": len(rows), "page": 1, "page_size": len(rows),
                            "explanation": f"Row counts for {len(tables)} tables."})
        except Exception as e:
            return jsonify({"error": str(e)})

    # --- CONSTRAINTS ---
    if cmd_lower in ("show constraints", "list constraints", "show all constraints"):
        if hasattr(adapter, 'get_constraints'):
            try:
                clist = adapter.get_constraints()
                columns = ["Table", "Constraint Type", "Details"]
                rows = [[c["table"], c["type"], c["details"]] for c in clist]
                if not rows:
                    rows = [["No constraints found", "", ""]]
                return jsonify({"task": "SYSTEM", "columns": columns, "results": rows, "total_rows": len(rows), "page": 1, "page_size": len(rows),
                                "explanation": "All constraints."})
            except Exception as e:
                return jsonify({"error": str(e)})

    # --- CREATE TABLE DDL ---
    create_table_match = None
    for prefix in ("show create table ", "show ddl ", "show sql "):
        if cmd_lower.startswith(prefix):
            create_table_match = user_cmd[len(prefix):].strip().strip(";").strip('"').strip("'")
            break
    if create_table_match and hasattr(adapter, 'get_create_table'):
        try:
            ddl = adapter.get_create_table(create_table_match)
            return jsonify({"task": "SYSTEM", "columns": ["CREATE TABLE Statement"], "results": [[ddl or "Not found"]],
                            "total_rows": 1, "page": 1, "page_size": 1, "explanation": f"DDL for '{create_table_match}'."})
        except Exception as e:
            return jsonify({"error": str(e)})

    # --- LIST TABLES ---
    if cmd_lower in ("list tables", "show tables", "list collections", "show collections"):
        if not is_allowed(role, "SYSTEM"):
            return jsonify({"error": "Permission denied."})
        tables = adapter.list_tables()
        label = "Collections" if adapter.is_nosql else "Tables"
        session["last_read_sql"] = "SHOW TABLES"
        session["last_read_columns"] = [label]
        return jsonify({"task": "SYSTEM", "columns": [label], "results": [[t] for t in tables],
                        "total_rows": len(tables), "page": 1, "page_size": len(tables)})

    # --- LLM Query Generation ---
    schema = adapter.get_schema()
    conversation_context = session.get("conversation_context", [])
    llm_provider = session.get("llm_provider", "mistral")

    query, explanation = generate_query_with_explanation(
        user_cmd, dialect, schema, llm_provider, history=conversation_context
    )

    conversation_context.append({"user": user_cmd, "assistant": query})
    if len(conversation_context) > 5:
        conversation_context.pop(0)
    session["conversation_context"] = conversation_context

    task = classify_query(query, dialect)
    safe_check = is_safe(query, dialect)

    effective_task = task
    if task == "UNKNOWN" and role in ("ADMIN", "EDITOR") and safe_check:
        effective_task = "READ"

    if not is_allowed(role, effective_task):
        return jsonify({"error": f"{role} not allowed to run {task}"})

    # READ / SYSTEM
    if task in ("READ", "SYSTEM") or (task == "UNKNOWN" and effective_task == "READ"):
        if not is_safe(query, dialect):
            return jsonify({"error": "Unsafe query blocked."})

        session["last_read_sql"] = query
        session["last_explanation"] = explanation

        try:
            if adapter.is_nosql:
                columns, rows = adapter.execute(query)
                total_rows = len(rows)
            elif is_system_query(query) or is_already_limited(query):
                columns, rows = adapter.execute(query)
                total_rows = len(rows)
            else:
                paginated = paginate_sql(query, 1)
                columns, rows = adapter.execute(paginated)
                total_rows = safe_count(adapter, query)
        except Exception as e:
            # Try AI Ask fallback
            if analysis_enabled:
                try:
                    from core.analyzer import ai_ask
                    db_name = session.get("active_db", "Unknown DB")
                    ai_result = ai_ask(user_cmd, schema, db_name, dialect=dialect)
                    if "error" not in ai_result:
                        return jsonify({"task": "READ", "ai_response": ai_result.get("answer", ""),
                                        "ai_suggestions": ai_result.get("suggested_queries", []),
                                        "sql": query, "explanation": f"SQL failed ({str(e)}), AI answered directly."})
                except Exception:
                    pass
            return jsonify({"error": f"Execution failed: {str(e)}", "sql": query, "explanation": explanation, "task": "READ"})

        session["last_read_columns"] = columns

        return jsonify({
            "task": task, "sql": query, "explanation": explanation,
            "columns": columns,
            "results": rows_to_list(rows) if rows and not isinstance(rows[0], list) else rows if rows else [],
            "page": 1, "page_size": PAGE_SIZE, "total_rows": total_rows,
        })

    # WRITE / SCHEMA -> needs review
    session["last_sql"] = query
    session["last_task"] = task
    session["last_explanation"] = explanation

    return jsonify({
        "needs_review": True, "sql": query, "explanation": explanation, "task": task,
    })


@api.route('/api/command/paginate', methods=['GET'])
def api_paginate():
    sql = session.get("last_read_sql")
    if not sql:
        return jsonify({"error": "No active query to paginate"})

    page = max(1, int(request.args.get("page", 1)))
    adapter = get_active_adapter()

    try:
        if adapter.is_nosql:
            columns, rows = adapter.execute(sql)
            total_rows = len(rows)
        else:
            paginated = paginate_sql(sql, page)
            columns, rows = adapter.execute(paginated)
            total_rows = safe_count(adapter, sql)
    except Exception as e:
        return jsonify({"error": f"Execution failed: {str(e)}"})

    return jsonify({
        "task": "READ", "sql": sql, "explanation": session.get("last_explanation"),
        "columns": columns,
        "results": rows_to_list(rows) if rows and not isinstance(rows[0], list) else rows if rows else [],
        "page": page, "page_size": PAGE_SIZE, "total_rows": total_rows,
    })


# ---------------------------------------------------
# Execute WRITE/SCHEMA
# ---------------------------------------------------
@api.route('/api/execute', methods=['POST'])
def api_execute():
    data = request.json or {}
    role = session.get("role")
    query = data.get("sql") or session.get("last_sql")
    task = session.get("last_task")

    adapter = get_active_adapter()
    dialect = adapter.dialect

    if not query or not is_allowed(role, task) or not is_safe(query, dialect):
        return jsonify({"success": False, "error": "Permission denied or unsafe query."})

    if task in ("WRITE", "SCHEMA"):
        take_snapshot(adapter, session.get("active_db", "Default SQLite"))

    try:
        adapter.execute(query)
        session.pop("last_sql", None)
        session.pop("last_task", None)
        return jsonify({"success": True, "message": "Query executed successfully."})
    except Exception as e:
        return jsonify({"success": False, "error": f"Execution failed: {str(e)}"})


# ---------------------------------------------------
# LLM Provider
# ---------------------------------------------------
@api.route('/api/set-provider', methods=['POST'])
def api_set_provider():
    data = request.json or {}
    provider = data.get("provider")
    if provider in ["mistral", "groq"]:
        session["llm_provider"] = provider
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Invalid provider"})


# ---------------------------------------------------
# Undo
# ---------------------------------------------------
@api.route('/api/undo', methods=['POST'])
def api_undo():
    if session.get("role") != "ADMIN":
        return jsonify({"success": False, "error": "Admin only"})
    adapter = get_active_adapter()
    if not adapter.supports_snapshot:
        return jsonify({"success": False, "error": "Undo not supported for this database"})
    try:
        undo(1, adapter, session.get("active_db", "Default SQLite"))
        return jsonify({"success": True, "message": "Undo successful"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ---------------------------------------------------
# Snapshots
# ---------------------------------------------------
@api.route('/api/snapshots', methods=['GET'])
def api_list_snapshots():
    return jsonify({"snapshots": list_snapshots()})


@api.route('/api/snapshots', methods=['POST'])
def api_create_snapshot():
    if session.get("role") != "ADMIN":
        return jsonify({"success": False, "error": "Admin only"})
    adapter = get_active_adapter()
    active_db = session.get("active_db", "Default SQLite")
    if take_snapshot(adapter, active_db):
        return jsonify({"success": True, "message": f"Snapshot created for {active_db}"})
    return jsonify({"success": False, "error": "Failed to create snapshot"})


@api.route('/api/snapshots/restore', methods=['POST'])
def api_restore_snapshot():
    if session.get("role") != "ADMIN":
        return jsonify({"success": False, "error": "Admin only"})
    data = request.json or {}
    snap_id = data.get("snap_id")
    conn_name = data.get("connection_name")
    try:
        adapter = get_adapter_for_connection(conn_name)
        if restore_snapshot(snap_id, adapter):
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Restore failed"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@api.route('/api/snapshots/<snap_id>', methods=['DELETE'])
def api_delete_snapshot(snap_id):
    if session.get("role") != "ADMIN":
        return jsonify({"success": False, "error": "Admin only"})
    if delete_snapshot(snap_id):
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Failed to delete"})


# ---------------------------------------------------
# Admin Metrics
# ---------------------------------------------------
@api.route('/api/admin/metrics', methods=['GET'])
def api_admin_metrics():
    if session.get("role") != "ADMIN":
        return jsonify({"error": "Unauthorized"}), 403
    summary = get_summary()
    llm_config = llm_manager.load_config()
    ollama_models = llm_manager.list_local_models()
    return jsonify({
        "summary": summary,
        "llm_config": llm_config,
        "ollama_models": ollama_models,
    })


# ---------------------------------------------------
# Dashboards (GET list + GET single)
# ---------------------------------------------------
@api.route('/api/dashboards', methods=['GET'])
def api_list_dashboards():
    return jsonify({"dashboards": list_dashboards()})


@api.route('/api/dashboards/<dash_id>', methods=['GET'])
def api_get_dashboard(dash_id):
    dash = get_dashboard(dash_id)
    if not dash:
        return jsonify({"error": "Dashboard not found"}), 404
    return jsonify(dash)


# ---------------------------------------------------
# Create Database
# ---------------------------------------------------
@api.route('/api/create-database', methods=['POST'])
def api_create_database():
    data = request.json or {}
    db_name = data.get("db_name", "").strip()
    db_type = data.get("db_type", "sqlite")
    tables = data.get("tables", [])

    if not db_name:
        return jsonify({"success": False, "error": "Database name required"})

    try:
        if db_type == "sqlite":
            import sqlite3
            path = f"db/{db_name}.db"
            os.makedirs("db/", exist_ok=True)
            conn = sqlite3.connect(path)
            try:
                for tbl in tables:
                    if tbl.get("columns"):
                        col_defs = []
                        pks = []
                        for col in tbl["columns"]:
                            d = f'"{col["name"]}" {col.get("type", "TEXT")}'
                            if col.get("not_null"):
                                d += " NOT NULL"
                            if col.get("pk"):
                                pks.append(col["name"])
                            col_defs.append(d)
                        if pks:
                            pk_str = ", ".join(f'"{p}"' for p in pks)
                            col_defs.append(f"PRIMARY KEY ({pk_str})")
                        conn.execute(f'CREATE TABLE IF NOT EXISTS "{tbl["name"]}" ({", ".join(col_defs)})')
                conn.commit()
            finally:
                conn.close()
            add_connection(db_name, "sqlite", {"db_path": path})
        else:
            # For non-SQLite, use existing connection infrastructure
            config = {k: data.get(k, "") for k in ["host", "port", "username", "password", "database", "service_name", "keyspace", "db_number"]}
            config["database"] = db_name
            add_connection(db_name, db_type, config)

        session["active_db"] = db_name
        return jsonify({"success": True, "message": f"Database '{db_name}' created!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
