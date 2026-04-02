from datetime import datetime
from io import StringIO
import csv
import time
from flask import (
    Flask, render_template, request,
    session, redirect, url_for, Response, jsonify, send_file
)
import json

from werkzeug.security import generate_password_hash, check_password_hash

from core.validator import is_safe, classify_query
from core.snapshot import (
    take_snapshot, undo, has_snapshots, list_snapshots, 
    delete_snapshot, restore_snapshot
)
from core.llm import generate_query_with_explanation
from core.connection_manager import (
    list_connections, add_connection, delete_connection as rem_connection,
    get_adapter_for_connection, test_connection, test_new_connection,
    ensure_default_sqlite,
)
from core.adapters import DB_TYPES, DB_DISPLAY_NAMES, DB_CONNECTION_FIELDS
from core.metrics import get_summary
from core.dashboards import (
    list_dashboards, get_dashboard, create_dashboard, 
    delete_dashboard, add_widget, remove_widget
)
from core import llm_manager


import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------
# Flask App Setup
# ---------------------------------------------------
app = Flask(__name__)
app.secret_key = "dev-secret-key"
app.config["SESSION_PERMANENT"] = False

# Groq Data Analysis config
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
analysis_enabled = bool(GROQ_API_KEY)

PAGE_SIZE = 50

# Ensure default SQLite connection exists on startup
ensure_default_sqlite()


# ---------------------------------------------------
# Demo Users
# ---------------------------------------------------
USERS = {
    "viewer1": {
        "password": generate_password_hash("viewer123"),
        "role": "VIEWER"
    },
    "editor1": {
        "password": generate_password_hash("editor123"),
        "role": "EDITOR"
    },
    "admin1": {
        "password": generate_password_hash("admin123"),
        "role": "ADMIN"
    }
}


# ---------------------------------------------------
# Roles & Permissions
# ---------------------------------------------------
ROLE_VIEWER = "VIEWER"
ROLE_EDITOR = "EDITOR"
ROLE_ADMIN  = "ADMIN"

ROLE_PERMISSIONS = {
    ROLE_VIEWER: {"READ", "SYSTEM"},
    ROLE_EDITOR: {"READ", "WRITE", "SYSTEM"},
    ROLE_ADMIN:  {"READ", "WRITE", "SCHEMA", "SYSTEM"}
}


# ---------------------------------------------------
# Helpers
# ---------------------------------------------------
def rows_to_list(rows):
    return [list(r) for r in rows] if rows else []


def is_allowed(role, task):
    return task in ROLE_PERMISSIONS.get(role, set())


def is_system_query(sql):
    sql = sql.lower()
    return any(k in sql for k in ("sqlite_master", "pragma", "information_schema"))


def is_already_limited(sql):
    sql = sql.lower()
    return " limit " in sql or " offset " in sql


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


def add_to_history(query, sql, task, status):
    history = session.get("history", [])
    active_db = session.get("active_db", "Default SQLite")
    history.insert(0, {
        "query": query,
        "sql": sql,
        "task": task,
        "status": status,
        "user": session.get("username"),
        "db": active_db,
        "time": datetime.now().strftime("%H:%M")
    })
    session["history"] = history[:10]


def get_active_adapter():
    """Returns the adapter for the currently active database connection."""
    name = session.get("active_db", "Default SQLite")
    try:
        return get_adapter_for_connection(name)
    except Exception:
        # Fallback to default
        session["active_db"] = "Default SQLite"
        return get_adapter_for_connection("Default SQLite")


def get_active_db_info():
    """Returns info about the active database for template rendering."""
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
    return {
        "name": name,
        "db_type": "sqlite",
        "display_type": "SQLite",
        "is_nosql": False,
        "supports_snapshot": True,
    }


# ---------------------------------------------------
# AUTH GUARD
# ---------------------------------------------------
@app.before_request
def require_login():
    if request.path.startswith("/login"):
        return
    if request.path.startswith("/static") or request.path == "/favicon.ico":
        return
    if not session.get("logged_in"):
        return redirect(url_for("login"))


# ---------------------------------------------------
# Login / Logout
# ---------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        user = USERS.get(username)
        if not user or not check_password_hash(user["password"], password):
            return render_template("login.html", error="❌ Invalid credentials")

        session.clear()
        session["logged_in"] = True
        session["username"] = username
        session["role"] = user["role"]
        session["active_db"] = "Default SQLite"

        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------
# Main App
# ---------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    role = session.get("role", ROLE_VIEWER)
    db_info = get_active_db_info()
    connections = list_connections()
    llm_provider = session.get("llm_provider", "mistral")

    # ---------- POST ----------
    if request.method == "POST":
        user_cmd = request.form.get("command", "").strip()
        if not user_cmd:
            return render_template(
                "index.html",
                error="❌ Empty command.",
                history=session.get("history", []),
                db_info=db_info,
                connections=connections,
                llm_provider=llm_provider,
                analysis_enabled=analysis_enabled,
            )

        adapter = get_active_adapter()
        dialect = adapter.dialect
        cmd_lower = user_cmd.lower().strip()

        # =============================================================
        # HARDCODED DBMS COMMANDS (bypass LLM for reliability)
        # =============================================================

        # --- DESCRIBE TABLE ---
        describe_match = None
        for prefix in ("describe ", "desc ", "show structure ", "show columns ", "show schema "):
            if cmd_lower.startswith(prefix):
                describe_match = user_cmd[len(prefix):].strip().strip(";").strip('"').strip("'")
                break

        if describe_match and dialect == "sqlite":
            table_name = describe_match
            try:
                info = adapter.describe_table(table_name)
                # Build result columns and rows for display
                columns = ["Column", "Type", "Not Null", "Default", "Primary Key"]
                rows = []
                for c in info["columns"]:
                    rows.append([c["name"], c["type"], "YES" if c["not_null"] else "NO",
                                 c["default"] if c["default"] is not None else "",
                                 "YES" if c["primary_key"] else "NO"])

                # Add FK info as extra rows
                if info["foreign_keys"]:
                    rows.append(["", "", "", "", ""])
                    rows.append(["--- FOREIGN KEYS ---", "", "", "", ""])
                    for fk in info["foreign_keys"]:
                        rows.append([fk["from"], f"-> {fk['to_table']}.{fk['to_column']}", "", "", ""])

                if info["indexes"]:
                    rows.append(["", "", "", "", ""])
                    rows.append(["--- INDEXES ---", "", "", "", ""])
                    for idx in info["indexes"]:
                        rows.append([idx["name"], ", ".join(idx["columns"]),
                                     "UNIQUE" if idx["unique"] else "", "", ""])

                session["last_read_sql"] = f'PRAGMA table_info("{table_name}")'
                session["last_query"] = user_cmd
                session["last_explanation"] = f"Detailed structure of table '{table_name}' including columns, foreign keys, and indexes."
                session["last_read_columns"] = columns
                add_to_history(user_cmd, f"DESCRIBE {table_name}", "SYSTEM", "EXECUTED")

                return render_template(
                    "index.html", task="SYSTEM", columns=columns, results=rows,
                    page=1, page_size=len(rows), total_rows=len(rows),
                    sql=f'PRAGMA table_info("{table_name}")',
                    explanation=f"Table '{table_name}': {info['row_count']} rows, {len(info['columns'])} columns, {len(info['foreign_keys'])} foreign keys, {len(info['indexes'])} indexes.",
                    history=session.get("history", []), db_info=db_info,
                    connections=connections, llm_provider=llm_provider,
                    analysis_enabled=analysis_enabled,
                )
            except Exception as e:
                return render_template(
                    "index.html", error=f"Table '{table_name}' not found or error: {str(e)}",
                    history=session.get("history", []), db_info=db_info,
                    connections=connections, llm_provider=llm_provider,
                    analysis_enabled=analysis_enabled,
                )

        # --- SHOW FOREIGN KEYS ---
        if cmd_lower in ("show foreign keys", "list foreign keys", "show fk", "show fks",
                          "show relationships", "list relationships", "show refs", "show references"):
            if dialect == "sqlite" and hasattr(adapter, 'get_foreign_keys'):
                fks = adapter.get_foreign_keys()
                columns = ["From Table", "From Column", "To Table", "To Column"]
                rows = [[fk["from_table"], fk["from_column"], fk["to_table"], fk["to_column"]] for fk in fks]
                if not rows:
                    rows = [["No foreign keys found", "", "", ""]]

                session["last_read_sql"] = "-- Foreign Key Relationships"
                session["last_query"] = user_cmd
                session["last_explanation"] = "All foreign key relationships in the database."
                session["last_read_columns"] = columns
                add_to_history(user_cmd, "SHOW FOREIGN KEYS", "SYSTEM", "EXECUTED")

                return render_template(
                    "index.html", task="SYSTEM", columns=columns, results=rows,
                    page=1, page_size=len(rows), total_rows=len(rows),
                    explanation=f"Found {len(fks)} foreign key relationships across all tables.",
                    history=session.get("history", []), db_info=db_info,
                    connections=connections, llm_provider=llm_provider,
                    analysis_enabled=analysis_enabled,
                )

        # --- SHOW FOREIGN KEYS FOR specific table ---
        fk_table_match = None
        for prefix in ("show foreign keys for ", "show fk for ", "show fks for ",
                        "show references for ", "show refs for "):
            if cmd_lower.startswith(prefix):
                fk_table_match = user_cmd[len(prefix):].strip().strip(";").strip('"').strip("'")
                break

        if fk_table_match and dialect == "sqlite":
            table_name = fk_table_match
            try:
                conn = adapter.get_connection()
                cur = conn.cursor()
                cur.execute(f'PRAGMA foreign_key_list("{table_name}");')
                fk_rows = cur.fetchall()
                columns = ["From Column", "References Table", "References Column"]
                rows = [[fk[3], fk[2], fk[4]] for fk in fk_rows]
                if not rows:
                    rows = [["No foreign keys found for this table", "", ""]]
                adapter.disconnect()

                session["last_read_sql"] = f'PRAGMA foreign_key_list("{table_name}")'
                session["last_query"] = user_cmd
                session["last_read_columns"] = columns
                add_to_history(user_cmd, f"SHOW FK FOR {table_name}", "SYSTEM", "EXECUTED")

                return render_template(
                    "index.html", task="SYSTEM", columns=columns, results=rows,
                    page=1, page_size=len(rows), total_rows=len(rows),
                    explanation=f"Foreign keys for table '{table_name}'.",
                    history=session.get("history", []), db_info=db_info,
                    connections=connections, llm_provider=llm_provider,
                    analysis_enabled=analysis_enabled,
                )
            except Exception as e:
                return render_template(
                    "index.html", error=f"Error: {str(e)}",
                    history=session.get("history", []), db_info=db_info,
                    connections=connections, llm_provider=llm_provider,
                    analysis_enabled=analysis_enabled,
                )

        # --- SHOW INDEXES ---
        if cmd_lower in ("show indexes", "list indexes", "show index", "show indices"):
            if dialect == "sqlite" and hasattr(adapter, 'get_indexes'):
                indexes = adapter.get_indexes()
                columns = ["Table", "Index Name", "Unique", "Columns"]
                rows = [[idx["table"], idx["index_name"],
                         "YES" if idx["unique"] else "NO",
                         ", ".join(idx["columns"])] for idx in indexes]
                if not rows:
                    rows = [["No indexes found", "", "", ""]]

                session["last_read_sql"] = "-- All Indexes"
                session["last_query"] = user_cmd
                session["last_read_columns"] = columns
                add_to_history(user_cmd, "SHOW INDEXES", "SYSTEM", "EXECUTED")

                return render_template(
                    "index.html", task="SYSTEM", columns=columns, results=rows,
                    page=1, page_size=len(rows), total_rows=len(rows),
                    explanation=f"Found {len(indexes)} indexes across all tables.",
                    history=session.get("history", []), db_info=db_info,
                    connections=connections, llm_provider=llm_provider,
                    analysis_enabled=analysis_enabled,
                )

        # --- SHOW TABLE COUNT / SHOW ROW COUNTS ---
        if cmd_lower in ("show table counts", "show row counts", "count all tables", "table sizes"):
            try:
                tables = adapter.list_tables()
                columns = ["Table Name", "Row Count"]
                rows = []
                for t in tables:
                    try:
                        _, count_rows = adapter.execute(f'SELECT COUNT(*) FROM "{t}"')
                        rows.append([t, count_rows[0][0] if count_rows else 0])
                    except Exception:
                        rows.append([t, "Error"])

                session["last_read_sql"] = "-- Table Row Counts"
                session["last_query"] = user_cmd
                session["last_read_columns"] = columns
                add_to_history(user_cmd, "TABLE ROW COUNTS", "SYSTEM", "EXECUTED")

                return render_template(
                    "index.html", task="SYSTEM", columns=columns, results=rows,
                    page=1, page_size=len(rows), total_rows=len(rows),
                    explanation=f"Row counts for all {len(tables)} tables.",
                    history=session.get("history", []), db_info=db_info,
                    connections=connections, llm_provider=llm_provider,
                    analysis_enabled=analysis_enabled,
                )
            except Exception as e:
                return render_template(
                    "index.html", error=f"Error: {str(e)}",
                    history=session.get("history", []), db_info=db_info,
                    connections=connections, llm_provider=llm_provider,
                    analysis_enabled=analysis_enabled,
                )

        # --- SHOW CONSTRAINTS ---
        if cmd_lower in ("show constraints", "list constraints", "show all constraints"):
            if dialect == "sqlite":
                try:
                    tables = adapter.list_tables()
                    columns = ["Table", "Constraint Type", "Details"]
                    rows = []
                    conn = adapter.get_connection()
                    cur = conn.cursor()
                    for t in tables:
                        # Primary keys
                        cur.execute(f'PRAGMA table_info("{t}");')
                        for col in cur.fetchall():
                            if col[5]:
                                rows.append([t, "PRIMARY KEY", col[1]])
                        # Foreign keys
                        cur.execute(f'PRAGMA foreign_key_list("{t}");')
                        for fk in cur.fetchall():
                            rows.append([t, "FOREIGN KEY", f"{fk[3]} -> {fk[2]}.{fk[4]}"])
                        # NOT NULL
                        cur.execute(f'PRAGMA table_info("{t}");')
                        for col in cur.fetchall():
                            if col[3]:
                                rows.append([t, "NOT NULL", col[1]])
                        # Unique indexes
                        cur.execute(f'PRAGMA index_list("{t}");')
                        for idx in cur.fetchall():
                            if idx[2]:
                                cur.execute(f'PRAGMA index_info("{idx[1]}");')
                                idx_cols = [ic[2] for ic in cur.fetchall()]
                                rows.append([t, "UNIQUE", f"{idx[1]} ({', '.join(idx_cols)})"])
                    adapter.disconnect()

                    if not rows:
                        rows = [["No constraints found", "", ""]]

                    session["last_read_sql"] = "-- All Constraints"
                    session["last_query"] = user_cmd
                    session["last_read_columns"] = columns
                    add_to_history(user_cmd, "SHOW CONSTRAINTS", "SYSTEM", "EXECUTED")

                    return render_template(
                        "index.html", task="SYSTEM", columns=columns, results=rows,
                        page=1, page_size=len(rows), total_rows=len(rows),
                        explanation=f"All constraints (PK, FK, NOT NULL, UNIQUE) across all tables.",
                        history=session.get("history", []), db_info=db_info,
                        connections=connections, llm_provider=llm_provider,
                        analysis_enabled=analysis_enabled,
                    )
                except Exception as e:
                    return render_template(
                        "index.html", error=f"Error: {str(e)}",
                        history=session.get("history", []), db_info=db_info,
                        connections=connections, llm_provider=llm_provider,
                        analysis_enabled=analysis_enabled,
                    )

        # --- SHOW CREATE TABLE ---
        create_table_match = None
        for prefix in ("show create table ", "show ddl ", "show sql "):
            if cmd_lower.startswith(prefix):
                create_table_match = user_cmd[len(prefix):].strip().strip(";").strip('"').strip("'")
                break

        if create_table_match and dialect == "sqlite":
            table_name = create_table_match
            try:
                _, ddl_rows = adapter.execute(
                    f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'"
                )
                columns = ["CREATE TABLE Statement"]
                rows = [[ddl_rows[0][0]]] if ddl_rows and ddl_rows[0][0] else [["Table not found"]]

                session["last_read_sql"] = f"SELECT sql FROM sqlite_master WHERE name='{table_name}'"
                session["last_query"] = user_cmd
                session["last_read_columns"] = columns
                add_to_history(user_cmd, f"SHOW CREATE TABLE {table_name}", "SYSTEM", "EXECUTED")

                return render_template(
                    "index.html", task="SYSTEM", columns=columns, results=rows,
                    page=1, page_size=1, total_rows=1,
                    explanation=f"DDL (CREATE TABLE) statement for '{table_name}'.",
                    history=session.get("history", []), db_info=db_info,
                    connections=connections, llm_provider=llm_provider,
                    analysis_enabled=analysis_enabled,
                )
            except Exception as e:
                return render_template(
                    "index.html", error=f"Error: {str(e)}",
                    history=session.get("history", []), db_info=db_info,
                    connections=connections, llm_provider=llm_provider,
                    analysis_enabled=analysis_enabled,
                )

        # =============================================================
        # END HARDCODED COMMANDS
        # =============================================================

        # SYSTEM: list tables / show tables
        if cmd_lower in ("list tables", "show tables", "list collections", "show collections"):
            if not is_allowed(role, "SYSTEM"):
                return render_template(
                    "index.html",
                    error="Permission denied.",
                    history=session.get("history", []),
                    db_info=db_info,
                    connections=connections,
                    llm_provider=llm_provider,
                    analysis_enabled=analysis_enabled,
                )

            tables = adapter.list_tables()
            label = "Collections" if adapter.is_nosql else "Tables"

            # Metadata for PPT/Export
            session["last_read_sql"] = "SELECT name FROM sqlite_master WHERE type='table'" if dialect == "sqlite" else "SHOW TABLES"
            session["last_query"] = user_cmd
            session["last_explanation"] = "Listing all tables/collections in the database."
            session["last_read_columns"] = [label]

            add_to_history(user_cmd, "SHOW TABLES", "SYSTEM", "EXECUTED")

            return render_template(
                "index.html",
                task="SYSTEM",
                columns=[label],
                results=[[t] for t in tables],
                page=1,
                page_size=len(tables),
                total_rows=len(tables),
                history=session.get("history", []),
                db_info=db_info,
                connections=connections,
                llm_provider=llm_provider,
                analysis_enabled=analysis_enabled,
            )

        # LLM: Generate query
        schema = adapter.get_schema()
        conversation_context = session.get("conversation_context", [])
        
        query, explanation = generate_query_with_explanation(
            user_cmd, dialect, schema, llm_provider, history=conversation_context
        )
        
        # Update context (last 5 - pruned for performance)
        conversation_context.append({"user": user_cmd, "assistant": query})
        if len(conversation_context) > 5:
            conversation_context.pop(0)
        session["conversation_context"] = conversation_context
        
        task = classify_query(query, dialect)
        safe_check = is_safe(query, dialect)
        
        # Guard: Allow UNKNOWN for Admin/Editor if it's safe (fallback for complex introspection)
        effective_task = task
        if task == "UNKNOWN" and role in (ROLE_ADMIN, ROLE_EDITOR) and safe_check:
            effective_task = "READ" # Treat as READ for permission check

        if not is_allowed(role, effective_task):
            add_to_history(user_cmd, query, task, "BLOCKED (ROLE)")
            return render_template(
                "index.html",
                error=f"❌ {role} not allowed to run {task}",
                history=session.get("history", []),
                db_info=db_info,
                connections=connections,
                llm_provider=llm_provider,
                analysis_enabled=analysis_enabled,
            )

        # READ, SYSTEM, or safe UNKNOWN (as effective READ) → Execute directly
        if task in ("READ", "SYSTEM") or (task == "UNKNOWN" and effective_task == "READ"):
            if not is_safe(query, dialect):
                add_to_history(user_cmd, query, "READ", "BLOCKED")
                return render_template(
                    "index.html",
                    error="❌ Unsafe query blocked.",
                    history=session.get("history", []),
                    db_info=db_info,
                    connections=connections,
                    llm_provider=llm_provider,
                    analysis_enabled=analysis_enabled,
                )

            session["last_read_sql"] = query
            session["last_explanation"] = explanation
            session["last_query"] = user_cmd

            page = 1

            try:
                if adapter.is_nosql:
                    # NoSQL: execute directly, no pagination
                    columns, rows = adapter.execute(query)
                    total_rows = len(rows)
                    paginated_sql = query
                elif is_system_query(query) or is_already_limited(query):
                    paginated_sql = query
                    columns, rows = adapter.execute(query)
                    total_rows = len(rows)
                else:
                    paginated_sql = paginate_sql(query, page)
                    columns, rows = adapter.execute(paginated_sql)
                    total_rows = safe_count(adapter, query)
            except Exception as e:
                # If it's a "Safe Unknown" (plain text), or if the generated SQL fails,
                # try AI Ask as a fallback to answer the user's question directly
                if task == "UNKNOWN" and effective_task == "READ":
                    # Try AI Ask with Groq if available
                    if analysis_enabled:
                        try:
                            from core.analyzer import ai_ask
                            schema = adapter.get_schema()
                            db_name = session.get("active_db", "Unknown DB")
                            ai_result = ai_ask(user_cmd, schema, db_name)
                            if "error" not in ai_result:
                                columns = ["AI Response"]
                                rows = [[ai_result.get("answer", query)]]
                                total_rows = 1
                                paginated_sql = "N/A (AI Response)"
                                explanation = "Your question was answered by AI with full database context."

                                session["last_query"] = user_cmd
                                session["last_explanation"] = explanation
                                add_to_history(user_cmd, "AI_ASK", "READ", "EXECUTED")

                                return render_template(
                                    "index.html",
                                    sql=None,
                                    explanation=None,
                                    task="READ",
                                    ai_response=ai_result.get("answer", ""),
                                    ai_suggestions=ai_result.get("suggested_queries", []),
                                    history=session.get("history", []),
                                    db_info=db_info,
                                    connections=connections,
                                    llm_provider=llm_provider,
                                    analysis_enabled=analysis_enabled,
                                )
                        except Exception:
                            pass

                    # Fallback: show the raw LLM text
                    columns = ["Intelligence Response"]
                    rows = [[query]]
                    total_rows = 1
                    paginated_sql = "N/A (Non-SQL Response)"

                    session["last_query"] = user_cmd
                    session["last_explanation"] = explanation
                else:
                    # SQL execution genuinely failed - try AI Ask as a last resort
                    if analysis_enabled and "syntax" in str(e).lower() or "no such" in str(e).lower():
                        try:
                            from core.analyzer import ai_ask
                            schema = adapter.get_schema()
                            db_name = session.get("active_db", "Unknown DB")
                            ai_result = ai_ask(user_cmd, schema, db_name)
                            if "error" not in ai_result:
                                add_to_history(user_cmd, "AI_ASK (fallback)", "READ", "EXECUTED")
                                return render_template(
                                    "index.html",
                                    sql=query,
                                    explanation=f"The generated SQL failed ({str(e)}), so AI answered your question directly.",
                                    task="READ",
                                    ai_response=ai_result.get("answer", ""),
                                    ai_suggestions=ai_result.get("suggested_queries", []),
                                    history=session.get("history", []),
                                    db_info=db_info,
                                    connections=connections,
                                    llm_provider=llm_provider,
                                    analysis_enabled=analysis_enabled,
                                )
                        except Exception:
                            pass

                    return render_template(
                        "index.html",
                        sql=query,
                        explanation=explanation,
                        task="READ",
                        error=f"Execution failed: {str(e)}",
                        history=session.get("history", []),
                        db_info=db_info,
                        connections=connections,
                        llm_provider=llm_provider,
                        analysis_enabled=analysis_enabled,
                    )
            
            # Store column names (small) for CSV export & analysis
            # Do NOT store rows to avoid "Cookie too large"
            session["last_read_columns"] = columns

            add_to_history(user_cmd, query, task, "EXECUTED")
            
            return render_template(
                "index.html",
                sql=paginated_sql,
                explanation=explanation,
                task=task,
                columns=columns,
                results=rows_to_list(rows) if rows and not isinstance(rows[0], list) else rows if rows else [],
                page=page,
                page_size=PAGE_SIZE,
                total_rows=total_rows,
                history=session.get("history", []),
                db_info=db_info,
                connections=connections,
                llm_provider=llm_provider,
                analysis_enabled=analysis_enabled,
            )

        # WRITE / SCHEMA → Review page
        add_to_history(user_cmd, query, task, "PENDING REVIEW")
        session["last_sql"] = query
        session["last_task"] = task
        session["last_explanation"] = explanation

        return render_template(
            "review.html",
            sql=query,
            explanation=explanation,
            task=task,
            history=session.get("history", []),
            db_info=db_info,
            connections=connections,
        )

    # ---------- GET (Pagination) ----------
    page = request.args.get("page")
    if page and session.get("last_read_sql"):
        adapter = get_active_adapter()
        sql = session["last_read_sql"]
        explanation = session.get("last_explanation")
        page = max(1, int(page))
        page_task = "READ"

        try:
            if adapter.is_nosql:
                columns, rows = adapter.execute(sql)
                total_rows = len(rows)
                paginated_sql = sql
            else:
                paginated_sql = paginate_sql(sql, page)
                columns, rows = adapter.execute(paginated_sql)
                total_rows = safe_count(adapter, sql)
        except Exception as e:
            return render_template(
                "index.html",
                sql=sql,
                explanation=explanation,
                task=page_task,
                error=f"❌ Execution failed: {str(e)}",
                history=session.get("history", []),
                db_info=db_info,
                connections=connections,
                analysis_enabled=analysis_enabled,
            )

        return render_template(
            "index.html",
            sql=paginated_sql,
            explanation=explanation,
            task=page_task,
            columns=columns,
            results=rows_to_list(rows) if rows and not isinstance(rows[0], list) else rows if rows else [],
            page=page,
            page_size=PAGE_SIZE,
            total_rows=total_rows,
            history=session.get("history", []),
            db_info=db_info,
            connections=connections,
            analysis_enabled=analysis_enabled,
        )

    return render_template(
        "index.html",
        message=session.pop("message", None),
        error=session.pop("error", None),
        history=session.get("history", []),
        db_info=db_info,
        connections=connections,
        analysis_enabled=analysis_enabled,
    )


# ---------------------------------------------------
# CSV Export
# ---------------------------------------------------
@app.route("/export")
def export_csv():
    sql = session.get("last_read_sql")

    if not sql:
        return redirect(url_for("index"))

    adapter = get_active_adapter()
    columns, rows = adapter.execute(sql)

    if not columns:
        return redirect(url_for("index"))

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    for r in rows:
        writer.writerow(r if isinstance(r, list) else list(r))

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=results.csv"}
    )


# ---------------------------------------------------
# Execute WRITE / SCHEMA
# ---------------------------------------------------
@app.route("/dry-run", methods=["POST"])
def dry_run_route():
    data = request.json or {}
    query = data.get("sql") or session.get("last_sql")
    
    if not query:
        return jsonify({"success": False, "status": "No query provided"})
    
    adapter = get_active_adapter()
    try:
        result = adapter.dry_run(query)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "status": f"Dry run error: {str(e)}"})


@app.route("/refine", methods=["POST"])
def refine_query():
    data = request.json or {}
    feedback = data.get("feedback")
    current_sql = data.get("current_sql")
    
    if not feedback:
        return jsonify({"success": False, "error": "Feedback required"})
    
    adapter = get_active_adapter()
    dialect = adapter.dialect
    schema = adapter.get_schema()
    llm_provider = session.get("llm_provider", "mistral")
    
    # We construct a new prompt that includes the current SQL and the refinement feedback
    refine_prompt = f"REFINE THIS QUERY:\n{current_sql}\n\nUSER FEEDBACK: {feedback}"
    
    try:
        from core.llm import generate_query_with_explanation
        # We pass the refinement as if it were a new command, but with context
        new_sql, explanation = generate_query_with_explanation(
            refine_prompt, dialect, schema, llm_provider, 
            history=session.get("conversation_context", []),
            system_prompt="""- Use ONLY tables and columns shown above
- Output ONLY valid SQL for the current database engine
- NEVER output plain text, lists, or conversational responses.
- Even if you know the answer from the schema, GENERATE THE SQL to fetch it.
- For SELECT queries: always include LIMIT 50 unless user specifies otherwise
- No markdown, no explanation, no code fences
"""
        )
        
        # Update session with new query for potential execution
        session["last_sql"] = new_sql
        session["last_explanation"] = explanation

        conversation_context = session.get("conversation_context", [])
        conversation_context.append({"user": feedback, "assistant": new_sql})
        if len(conversation_context) > 5:
            conversation_context.pop(0)
        session["conversation_context"] = conversation_context
        
        return jsonify({
            "success": True,
            "sql": new_sql,
            "explanation": explanation
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/execute", methods=["POST"])
def execute():
    role = session.get("role")
    # Get SQL from form (if edited by human) or fallback to session
    query = request.form.get("sql") or session.get("last_sql")
    task = session.get("last_task")

    adapter = get_active_adapter()
    dialect = adapter.dialect

    if not query or not is_allowed(role, task) or not is_safe(query, dialect):
        session["error"] = "❌ Permission denied or unsafe query."
        return redirect(url_for("index"))

    if task in ("WRITE", "SCHEMA"):
        take_snapshot(adapter, session.get("active_db", "Default SQLite"))

    try:
        if query.lower().startswith("delete"):
            adapter.preview_delete(query)

        adapter.execute(query)
        session["message"] = "✅ Query executed successfully."
    except Exception as e:
        session["error"] = f"❌ Execution failed: {str(e)}"

    session.pop("last_sql", None)
    session.pop("last_task", None)
    session.pop("last_explanation", None)

    return redirect(url_for("index"))

# ---------------------------------------------------
# LLM Provider Management
# ---------------------------------------------------
@app.route("/set_llm_provider", methods=["POST"])
def set_llm_provider():
    provider = request.form.get("provider")
    if provider in ["mistral", "groq"]:
        session["llm_provider"] = provider
        session["message"] = f"LLM Provider set to {'Groq (Cloud API)' if provider == 'groq' else 'Mistral (Local)'}."
    else:
        session["error"] = "Invalid LLM provider."
    return redirect(url_for("index"))


# ---------------------------------------------------
# LLM Administration & Analytics
# ---------------------------------------------------
@app.route("/admin")
def admin():
    if session.get("role") != "ADMIN" and session.get("role") != ROLE_ADMIN:
        session["error"] = "❌ Access denied. Admin only."
        return redirect(url_for("index"))
    
    summary = get_summary()
    llm_config = llm_manager.load_config()
    ollama_models = llm_manager.list_local_models()
    return render_template("admin.html", 
                           summary=summary, 
                           llm_config=llm_config,
                           ollama_models=ollama_models)


@app.route("/admin/llm/config", methods=["POST"])
def update_llm_config():
    if session.get("role") != "ADMIN" and session.get("role") != ROLE_ADMIN:
        return jsonify({"error": "Unauthorized"}), 403
    
    data = request.json
    config = llm_manager.load_config()
    
    # Update active provider
    if "active_provider" in data:
        config["active_provider"] = data["active_provider"]
    
    # Update specific provider fields
    if "providers" in data:
        for p_name, p_data in data["providers"].items():
            if p_name in config["providers"]:
                config["providers"][p_name].update(p_data)
            else:
                config["providers"][p_name] = p_data
    
    llm_manager.save_config(config)
    return jsonify({"success": True, "config": config})


@app.route("/admin/ollama/pull", methods=["POST"])
def pull_model():
    if session.get("role") != "ADMIN" and session.get("role") != ROLE_ADMIN:
        return jsonify({"error": "Unauthorized"}), 403
    
    model_name = request.json.get("model")
    if not model_name:
        return jsonify({"error": "Model name required"}), 400
    
    success = llm_manager.pull_ollama_model(model_name)
    return jsonify({"success": success})


@app.route("/admin/test_llm", methods=["POST"])
def admin_test_llm():
    if session.get("role") != ROLE_ADMIN:
        return jsonify({"error": "Unauthorized"}), 403
        
    prompt = request.form.get("prompt", "")
    provider = request.form.get("provider", "mistral")
    
    from core.llm import generate_query
    # We use a dummy schema for testing
    result = generate_query(prompt, "sqlite", "TEST_TABLE(col_a, col_b)", provider)
    
    return jsonify({
        "provider": provider,
        "input": prompt,
        "output": result
    })


@app.route("/dashboards")
def dashboards_page():
    all_dashboards = list_dashboards()
    return render_template("dashboards.html", dashboards=all_dashboards)


@app.route("/api/dashboards", methods=["POST"])
def api_create_dashboard():
    name = request.json.get("name", "New Dashboard")
    dash = create_dashboard(name)
    return jsonify(dash)


@app.route("/api/dashboards/<dash_id>", methods=["DELETE"])
def api_delete_dashboard(dash_id):
    delete_dashboard(dash_id)
    return jsonify({"success": True})


@app.route("/api/dashboards/<dash_id>/widgets", methods=["POST"])
def api_add_widget(dash_id):
    data = request.json
    widget = add_widget(
        dash_id, 
        data.get("title"), 
        data.get("query"), 
        data.get("chart_type", "table"),
        data.get("db_name", "Default SQLite")
    )
    return jsonify(widget)


@app.route("/api/dashboards/<dash_id>/widgets/<widget_id>", methods=["DELETE"])
def api_remove_widget(dash_id, widget_id):
    remove_widget(dash_id, widget_id)
    return jsonify({"success": True})


@app.route("/api/query", methods=["POST"])
def api_query_data():
    """Returns raw JSON data for dashboard widgets or charts."""
    query = request.json.get("query")
    db_name = request.json.get("db_name", "Default SQLite")
    
    if not query:
        return jsonify({"error": "Query required"}), 400
        
    try:
        adapter = get_adapter_for_connection(db_name)
        columns, rows = adapter.execute(query)
        return jsonify({
            "success": True,
            "columns": columns,
            "rows": rows_to_list(rows)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dashboards/auto-generate", methods=["POST"])
def api_auto_generate_dashboard():
    prompt = request.json.get("prompt", "")
    if not prompt:
        return jsonify({"error": "Prompt is required"}), 400

    active_db = session.get("active_db", "Default SQLite")
    adapter = get_active_adapter()
    schema = adapter.get_schema()

    # Collect table stats for better context
    table_stats = ""
    try:
        tables = adapter.list_tables()
        for t in tables:
            try:
                _, cr = adapter.execute(f'SELECT COUNT(*) FROM "{t}"')
                table_stats += f"  - {t}: {cr[0][0]} rows\n"
            except Exception:
                table_stats += f"  - {t}: ? rows\n"
    except Exception:
        pass

    # Use Groq directly for reliable JSON generation
    if analysis_enabled:
        try:
            from groq import Groq
            client = Groq(api_key=GROQ_API_KEY)
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You generate dashboard widget configurations as strict JSON."},
                    {"role": "user", "content": f"""Based on this database schema and the user's request, generate 4-6 dashboard widgets.

DATABASE: {active_db}
SCHEMA:
{schema}

TABLE STATS:
{table_stats}

USER REQUEST: {prompt}

Return a JSON object with this structure:
{{
    "name": "Dashboard title based on the request",
    "widgets": [
        {{"title": "Widget title", "query": "SELECT ...", "chart_type": "bar"}},
        {{"title": "Widget title", "query": "SELECT ...", "chart_type": "pie"}},
        {{"title": "Data table", "query": "SELECT ...", "chart_type": "table"}}
    ]
}}

RULES:
- All SQL must be valid for the schema above (use real table/column names)
- chart_type must be one of: bar, line, pie, doughnut, table
- For charts, the SELECT must return exactly 2 columns: a label column and a numeric column
- For tables, SELECT can return any columns
- Include a mix of chart types
- Make queries analytical and insightful (use JOINs, GROUP BY, ORDER BY, aggregates)
"""}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content.strip())
            widgets = result.get("widgets", [])
            dash_name = result.get("name", f"AI: {prompt[:30]}")

        except Exception as e:
            return jsonify({"error": f"AI generation failed: {str(e)}"}), 500
    else:
        return jsonify({"error": "Groq API key required for AI dashboard generation. Set GROQ_API_KEY in .env."}), 400

    # Create dashboard and add widgets
    dash = create_dashboard(dash_name)
    added = 0
    for w in widgets:
        if w.get("query"):
            add_widget(
                dash["id"],
                w.get("title", "Insight"),
                w.get("query"),
                w.get("chart_type", "table"),
                active_db
            )
            added += 1

    dash["widget_count"] = added
    return jsonify(dash)


@app.route("/dashboards/<dash_id>")
def view_dashboard(dash_id):
    dash = get_dashboard(dash_id)
    if not dash:
        return redirect(url_for("dashboards_page"))
    return render_template("dashboard_view.html", dashboard=dash)


# ---------------------------------------------------
# Undo (ADMIN ONLY) -> Legacy route from index Action Bar
# ---------------------------------------------------
@app.route("/undo", methods=["POST"])
def undo_last():
    if session.get("role") != ROLE_ADMIN:
        session["error"] = "❌ Only ADMIN can undo."
        return redirect(url_for("index"))

    adapter = get_active_adapter()
    if not adapter.supports_snapshot:
        session["error"] = "❌ Undo is only available for supported databases."
        return redirect(url_for("index"))

    try:
        undo(1, adapter, session.get("active_db", "Default SQLite"))
        session["message"] = "⏪ Undo successful."
    except Exception as e:
        session["error"] = f"❌ {str(e)}"

    return redirect(url_for("index"))


# ---------------------------------------------------
# Snapshots Management
# ---------------------------------------------------
@app.route("/snapshots")
def snapshots_page():
    if not session.get("username"): return redirect(url_for("login"))
    
    active_db = session.get("active_db", "Default SQLite")
    db_info = get_active_db_info()
    connections = list_connections()
    
    all_snapshots = list_snapshots()
    
    return render_template(
        "snapshots.html",
        snapshots=all_snapshots,
        active_db=active_db,
        db_info=db_info,
        connections=connections,
        message=session.pop("message", None),
        error=session.pop("error", None),
        analysis_enabled=analysis_enabled
    )

@app.route("/snapshots/create", methods=["POST"])
def create_snapshot():
    if session.get("role") != ROLE_ADMIN:
        session["error"] = "❌ Only ADMIN can create snapshots."
        return redirect(url_for("snapshots_page"))

    active_db = session.get("active_db", "Default SQLite")
    adapter = get_active_adapter()
    
    if take_snapshot(adapter, active_db):
        session["message"] = f"📸 Snapshot created for {active_db}."
    else:
        session["error"] = f"❌ Failed to create snapshot for {active_db}. Not supported or CLI tool missing."
        
    return redirect(url_for("snapshots_page"))

@app.route("/snapshots/restore", methods=["POST"])
def apply_snapshot():
    if session.get("role") != ROLE_ADMIN:
        session["error"] = "❌ Only ADMIN can restore snapshots."
        return redirect(url_for("snapshots_page"))

    snap_id = request.form.get("snap_id")
    connection_name = request.form.get("connection_name")
    
    # Needs the adapter for the specific connection the snapshot belongs to
    try:
        adapter = get_adapter_for_connection(connection_name)
        if restore_snapshot(snap_id, adapter):
            session["message"] = f"⏪ Snapshot restored successfully."
        else:
            session["error"] = f"❌ Failed to restore snapshot. CLI tool might be missing."
    except Exception as e:
        session["error"] = f"❌ Error restoring snapshot: {str(e)}"

    return redirect(url_for("snapshots_page"))

@app.route("/snapshots/delete", methods=["POST"])
def remove_snapshot():
    if session.get("role") != ROLE_ADMIN:
        session["error"] = "❌ Only ADMIN can delete snapshots."
        return redirect(url_for("snapshots_page"))

    snap_id = request.form.get("snap_id")
    if delete_snapshot(snap_id):
        session["message"] = "🗑️ Snapshot deleted."
    else:
        session["error"] = "❌ Failed to delete snapshot."
        
    return redirect(url_for("snapshots_page"))


@app.route("/export/ppt")
def export_ppt():
    sql = session.get("last_read_sql")
    explanation = session.get("last_explanation")
    analysis = session.get("last_analysis")
    user_query = session.get("last_query", "Custom Analysis")

    if not sql:
        session["error"] = "No query results to export. Please run a query first."
        return redirect(url_for("index"))

    # Re-fetch data on demand to keep session cookie small
    try:
        adapter = get_active_adapter()
        # Limit to 10 rows for PPT summary table
        if not (adapter.is_nosql or is_system_query(sql) or is_already_limited(sql)):
            fetch_sql = paginate_sql(sql, 1)
        else:
            fetch_sql = sql

        columns, rows = adapter.execute(fetch_sql)
        results = rows_to_list(rows)[:10]
    except Exception as e:
        session["error"] = f"Error fetching data for PPT: {str(e)}"
        return redirect(url_for("index"))

    from core.ppt_generator import PPTGenerator
    gen = PPTGenerator(title="Meridian Data Insight Report")

    # 1. Title Slide
    gen.add_title_slide(subtitle=f"Query: {user_query}")

    # 2. Schema slide (shows DB structure for context)
    try:
        schema = adapter.get_schema()
        if schema:
            gen.add_schema_slide(schema)
    except Exception:
        pass

    # 3. SQL Slide
    gen.add_text_slide("Generated SQL", sql or "N/A")

    # 4. Explanation Slide
    if explanation:
        gen.add_text_slide("AI Logic Explanation", explanation)

    # 5. Data Table Slide
    if columns and results:
        gen.add_table_slide("Query Results (Top 10)", columns, results)

    # 6. Analysis & Chart Slide (if available)
    if analysis and isinstance(analysis, dict) and "summary" in analysis:
        gen.add_text_slide("AI Data Insights", analysis["summary"])
        if "chart" in analysis and analysis["chart"]:
            gen.add_chart_slide("Data Visualization", analysis["chart"])

    try:
        ppt_file = gen.save()
        return send_file(
            ppt_file,
            mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            as_attachment=True,
            download_name=f"meridian_report_{int(time.time())}.pptx"
        )
    except Exception as e:
        session["error"] = f"PPT generation failed: {str(e)}"
        return redirect(url_for("index"))

# ---------------------------------------------------
# Command Intelligence & Guide
# ---------------------------------------------------
@app.route("/command-guide")
def command_guide():
    from core.intelligence import CommandIntelligence
    intel = CommandIntelligence()
    canonical = intel.get_canonical_commands()
    return render_template("command_guide.html", canonical=canonical)

@app.route("/api/intelligence/explain", methods=["POST"])
def explain_command():
    user_cmd = request.json.get("command")
    if not user_cmd:
        return jsonify({"error": "Command required"}), 400
    
    adapter = get_active_adapter()
    from core.intelligence import CommandIntelligence
    intel = CommandIntelligence(llm_provider=session.get("llm_provider", "mistral"))
    
    explanation = intel.explain_intent(user_cmd, adapter.dialect)
    return jsonify(explanation)

# ---------------------------------------------------
# Database Management
# ---------------------------------------------------
@app.route("/databases")
def databases_page():
    connections = list_connections()
    active_db = session.get("active_db", "Default SQLite")
    db_info = get_active_db_info()

    return render_template(
        "databases.html",
        connections=connections,
        active_db=active_db,
        db_types=DB_TYPES,
        db_display_names=DB_DISPLAY_NAMES,
        db_fields=DB_CONNECTION_FIELDS,
        db_info=db_info,
        message=session.pop("message", None),
        error=session.pop("error", None),
        analysis_enabled=analysis_enabled,
    )


@app.route("/databases/add", methods=["POST"])
def add_db():
    name = request.form.get("conn_name", "").strip()
    db_type = request.form.get("db_type", "sqlite")

    # Collect config fields based on DB type
    fields = DB_CONNECTION_FIELDS.get(db_type, [])
    config = {}
    for field in fields:
        val = request.form.get(field["name"], "")
        config[field["name"]] = val

    result = add_connection(name, db_type, config)

    if result["success"]:
        session["message"] = result["message"]
    else:
        session["error"] = result["message"]

    return redirect(url_for("databases_page"))


@app.route("/databases/delete", methods=["POST"])
def delete_db():
    name = request.form.get("conn_name", "")

    if name == "Default SQLite":
        session["error"] = "❌ Cannot delete the default SQLite connection."
        return redirect(url_for("databases_page"))

    # If deleting the active connection, switch to default
    if session.get("active_db") == name:
        session["active_db"] = "Default SQLite"

    result = rem_connection(name)
    if result["success"]:
        session["message"] = result["message"]
    else:
        session["error"] = result["message"]

    return redirect(url_for("databases_page"))


@app.route("/databases/test", methods=["POST"])
def test_db():
    name = request.form.get("conn_name", "")
    result = test_connection(name)
    return jsonify(result)


@app.route("/databases/test-new", methods=["POST"])
def test_new_db():
    db_type = request.form.get("db_type", "sqlite")
    fields = DB_CONNECTION_FIELDS.get(db_type, [])
    config = {}
    for field in fields:
        config[field["name"]] = request.form.get(field["name"], "")

    result = test_new_connection(db_type, config)
    return jsonify(result)


@app.route("/databases/select", methods=["POST"])
def select_db():
    name = request.form.get("conn_name", "")
    connections = list_connections()
    names = [c["name"] for c in connections]

    if name in names:
        session["active_db"] = name
        session["message"] = f"🔄 Switched to database: {name}"
        # Clear cached query state when switching DBs
        session.pop("last_read_sql", None)
        session.pop("last_read_columns", None)
        session.pop("last_sql", None)
        session.pop("last_task", None)
        session.pop("last_explanation", None)
    else:
        session["error"] = f"❌ Connection '{name}' not found."

    return redirect(url_for("index"))


# ---------------------------------------------------
# Data Analysis & Chart Generation (Groq)
# ---------------------------------------------------

@app.route("/analysis")
def show_analysis_page():
    if not session.get("username"):
        return redirect(url_for("login"))
    db_info = get_active_db_info()
    return render_template("analysis.html", analysis_enabled=analysis_enabled, db_info=db_info)


@app.route("/insights")
def show_insights_page():
    if not session.get("username"):
        return redirect(url_for("login"))
    
    db_info = get_active_db_info()
    return render_template("insights.html", analysis_enabled=analysis_enabled, db_info=db_info)


@app.route("/api/insights", methods=["POST"])
def generate_insights():
    if not analysis_enabled:
        return jsonify({"error": "Analysis not enabled."})
        
    try:
        adapter = get_active_adapter()
        schema = adapter.get_schema()
        db_name = session.get("active_db", "Unknown DB")
        from core.analyzer import analyze_schema
        result = analyze_schema(schema, db_name)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/analyze", methods=["POST"])
def analyze():
    sql = session.get("last_read_sql")
    columns = session.get("last_read_columns")
    user_hint = request.form.get("hint", "")

    if not sql:
        return jsonify({"error": "No query results to analyze. Please run a query first."})

    try:
        adapter = get_active_adapter()
        # Ensure we only analyze a reasonable chunk (analyzer cuts off at 100 rows anyway)
        paginated_sql = paginate_sql(sql, 1) if not (adapter.is_nosql or is_system_query(sql) or is_already_limited(sql)) else sql
        fetched_columns, rows = adapter.execute(paginated_sql)

        # Use fetched columns if session columns are missing
        use_columns = columns or fetched_columns

        from core.analyzer import analyze_data
        result = analyze_data(use_columns, rows, user_hint)

        # Store analysis in session so PPT export can use it
        if "error" not in result:
            session["last_analysis"] = result

        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/analyze-csv", methods=["POST"])
def analyze_csv():
    file = request.files.get("csv_file")
    user_hint = request.form.get("hint", "")

    if not file or file.filename == "":
        return jsonify({"error": "No file uploaded."})

    try:
        from core.csv_parser import parse_csv
        content = file.read().decode("utf-8", errors="replace")
        columns, rows = parse_csv(content)
        
        from core.analyzer import analyze_data
        result = analyze_data(columns, rows, user_hint)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)})


# ---------------------------------------------------
# Direct Analysis (fetches data from DB itself)
# ---------------------------------------------------
@app.route("/api/analyze-direct", methods=["POST"])
def analyze_direct():
    """Analyze data directly from a table or custom SQL query. Read-only."""
    if not analysis_enabled:
        return jsonify({"error": "Groq API not configured. Set GROQ_API_KEY in .env."})

    data = request.json or {}
    source = data.get("source", "")  # table name or "custom"
    custom_sql = data.get("sql", "")
    hint = data.get("hint", "")

    adapter = get_active_adapter()

    try:
        if source == "custom" and custom_sql:
            # Validate: only allow SELECT
            sql_lower = custom_sql.strip().lower()
            if not sql_lower.startswith("select"):
                return jsonify({"error": "Only SELECT queries are allowed for analysis."})
            sql = custom_sql.rstrip(";")
        elif source:
            # Fetch from table directly
            sql = f'SELECT * FROM "{source}" LIMIT 200'
        else:
            return jsonify({"error": "Provide a table name or custom SQL query."})

        columns, rows = adapter.execute(sql)

        if not columns or not rows:
            return jsonify({"error": "Query returned no data."})

        from core.analyzer import analyze_data
        result = analyze_data(columns, rows_to_list(rows), hint)

        if "error" not in result:
            session["last_analysis"] = result
            session["last_read_sql"] = sql
            session["last_read_columns"] = columns

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": f"Analysis failed: {str(e)}"})


@app.route("/api/tables-list", methods=["GET"])
def api_tables_list():
    """Returns list of tables with row counts for the analysis page."""
    try:
        adapter = get_active_adapter()
        tables = adapter.list_tables()
        result = []
        for t in tables:
            try:
                _, count_rows = adapter.execute(f'SELECT COUNT(*) FROM "{t}"')
                count = count_rows[0][0] if count_rows else 0
            except Exception:
                count = 0
            result.append({"name": t, "rows": count})
        return jsonify({"tables": result, "db_name": session.get("active_db", "Unknown")})
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/api/table-preview", methods=["POST"])
def api_table_preview():
    """Returns first 10 rows of a table for preview."""
    data = request.json or {}
    source = data.get("source", "")
    custom_sql = data.get("sql", "")

    adapter = get_active_adapter()

    try:
        if source == "custom" and custom_sql:
            sql_lower = custom_sql.strip().lower()
            if not sql_lower.startswith("select"):
                return jsonify({"error": "Only SELECT queries allowed."})
            sql = custom_sql.rstrip(";")
            if "limit" not in sql_lower:
                sql += " LIMIT 10"
        elif source:
            sql = f'SELECT * FROM "{source}" LIMIT 10'
        else:
            return jsonify({"error": "Provide a table name or SQL."})

        columns, rows = adapter.execute(sql)
        return jsonify({"columns": columns, "rows": rows_to_list(rows)})
    except Exception as e:
        return jsonify({"error": str(e)})


# ---------------------------------------------------
# AI Ask (General Q&A with full DB context)
# ---------------------------------------------------
@app.route("/api/ask", methods=["POST"])
def ai_ask_endpoint():
    if not analysis_enabled:
        return jsonify({"error": "Groq API key not configured. Set GROQ_API_KEY in .env."})

    question = request.json.get("question", "").strip()
    if not question:
        return jsonify({"error": "Question is required."})

    try:
        adapter = get_active_adapter()
        schema = adapter.get_schema()
        db_name = session.get("active_db", "Unknown DB")

        # Get table stats for context
        table_stats = []
        try:
            tables = adapter.list_tables()
            for t in tables:
                try:
                    _, count_rows = adapter.execute(f'SELECT COUNT(*) FROM "{t}"')
                    table_stats.append({"table": t, "rows": count_rows[0][0] if count_rows else 0})
                except Exception:
                    table_stats.append({"table": t, "rows": "?"})
        except Exception:
            pass

        from core.analyzer import ai_ask
        result = ai_ask(question, schema, db_name, table_stats)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)})


# ---------------------------------------------------
# Database Overview Dashboard
# ---------------------------------------------------
@app.route("/overview")
def overview_page():
    db_info = get_active_db_info()
    connections = list_connections()
    return render_template(
        "overview.html",
        db_info=db_info,
        connections=connections,
        analysis_enabled=analysis_enabled,
    )


@app.route("/api/overview", methods=["POST"])
def api_overview():
    """Generates a full database overview with AI-powered analysis."""
    adapter = get_active_adapter()
    db_name = session.get("active_db", "Unknown DB")

    # Collect table stats
    table_stats = []
    try:
        tables = adapter.list_tables()
        for t in tables:
            try:
                _, count_rows = adapter.execute(f'SELECT COUNT(*) FROM "{t}"')
                table_stats.append({"table": t, "rows": count_rows[0][0] if count_rows else 0})
            except Exception:
                table_stats.append({"table": t, "rows": 0})
    except Exception as e:
        return jsonify({"error": f"Failed to get tables: {str(e)}"})

    # Collect FK info
    fk_list = []
    if hasattr(adapter, 'get_foreign_keys'):
        try:
            fk_list = adapter.get_foreign_keys()
        except Exception:
            pass

    # If Groq is available, get AI analysis
    if analysis_enabled:
        try:
            schema = adapter.get_schema()
            from core.analyzer import get_table_overview
            ai_result = get_table_overview(schema, db_name, table_stats)
            if "error" not in ai_result:
                # Merge FK data in case AI didn't capture all
                if not ai_result.get("relationship_map") and fk_list:
                    ai_result["relationship_map"] = [
                        {"from": fk["from_table"], "to": fk["to_table"], "via": fk["from_column"]}
                        for fk in fk_list
                    ]
                return jsonify(ai_result)
        except Exception:
            pass

    # Fallback: return raw stats without AI
    total_rows = sum(ts["rows"] for ts in table_stats if isinstance(ts["rows"], int))
    return jsonify({
        "summary": f"Database '{db_name}' contains {len(table_stats)} tables with {total_rows:,} total rows.",
        "highlights": [
            {"label": "Total Tables", "value": str(len(table_stats))},
            {"label": "Total Rows", "value": f"{total_rows:,}"},
            {"label": "Foreign Keys", "value": str(len(fk_list))},
            {"label": "Largest Table", "value": max(table_stats, key=lambda x: x["rows"] if isinstance(x["rows"], int) else 0)["table"] if table_stats else "N/A"},
        ],
        "table_size_chart": {
            "labels": [ts["table"] for ts in sorted(table_stats, key=lambda x: x["rows"] if isinstance(x["rows"], int) else 0, reverse=True)],
            "data": [ts["rows"] for ts in sorted(table_stats, key=lambda x: x["rows"] if isinstance(x["rows"], int) else 0, reverse=True)],
        },
        "relationship_map": [
            {"from": fk["from_table"], "to": fk["to_table"], "via": fk["from_column"]}
            for fk in fk_list
        ],
        "suggested_queries": [],
    })


@app.route("/api/overview/query", methods=["POST"])
def api_overview_query():
    """Execute a suggested query from the overview and return results."""
    query = request.json.get("query", "")
    if not query:
        return jsonify({"error": "Query required"}), 400

    try:
        adapter = get_active_adapter()
        columns, rows = adapter.execute(query)
        return jsonify({
            "success": True,
            "columns": columns,
            "rows": rows_to_list(rows)[:50]
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ---------------------------------------------------
# Run
# ---------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
