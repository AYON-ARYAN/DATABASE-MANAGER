from flask import (
    Flask, render_template, request,
    session, redirect, url_for, Response, jsonify
)
from datetime import datetime
from io import StringIO
import csv

from werkzeug.security import generate_password_hash, check_password_hash

from core.validator import is_safe, classify_query
from core.snapshot import take_snapshot, undo, has_snapshots
from core.llm import generate_query_with_explanation
from core.connection_manager import (
    list_connections, add_connection, delete_connection,
    get_adapter_for_connection, test_connection, test_new_connection,
    ensure_default_sqlite,
)
from core.adapters import DB_TYPES, DB_DISPLAY_NAMES, DB_CONNECTION_FIELDS


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
                analysis_enabled=analysis_enabled,
            )

        adapter = get_active_adapter()
        dialect = adapter.dialect

        # SYSTEM: list tables / show tables
        if user_cmd.lower() in ("list tables", "show tables", "list collections", "show collections"):
            if not is_allowed(role, "SYSTEM"):
                return render_template(
                    "index.html",
                    error="❌ Permission denied.",
                    history=session.get("history", []),
                    db_info=db_info,
                    connections=connections,
                )

            tables = adapter.list_tables()
            label = "Collections" if adapter.is_nosql else "Tables"
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
                analysis_enabled=analysis_enabled,
            )

        # LLM: Generate query
        schema = adapter.get_schema()
        query, explanation = generate_query_with_explanation(user_cmd, dialect, schema)
        task = classify_query(query, dialect)

        if not is_allowed(role, task):
            add_to_history(user_cmd, query, task, "BLOCKED (ROLE)")
            return render_template(
                "index.html",
                error=f"❌ {role} not allowed to run {task}",
                history=session.get("history", []),
                db_info=db_info,
                connections=connections,
                analysis_enabled=analysis_enabled,
            )

        # READ
        if task == "READ":
            if not is_safe(query, dialect):
                add_to_history(user_cmd, query, "READ", "BLOCKED")
                return render_template(
                    "index.html",
                    error="❌ Unsafe query blocked.",
                    history=session.get("history", []),
                    db_info=db_info,
                    connections=connections,
                    analysis_enabled=analysis_enabled,
                )

            session["last_read_sql"] = query
            session["last_explanation"] = explanation

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
                return render_template(
                    "index.html",
                    sql=query,
                    explanation=explanation,
                    task="READ",
                    error=f"❌ Execution failed: {str(e)}",
                    history=session.get("history", []),
                    db_info=db_info,
                    connections=connections,
                    analysis_enabled=analysis_enabled,
                )

            session["last_read_columns"] = columns
            add_to_history(user_cmd, query, "READ", "EXECUTED")

            return render_template(
                "index.html",
                sql=paginated_sql,
                explanation=explanation,
                task="READ",
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
                task="READ",
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
            task="READ",
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
    columns = session.get("last_read_columns")

    if not sql or not columns:
        return redirect(url_for("index"))

    adapter = get_active_adapter()
    _, rows = adapter.execute(sql)

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
@app.route("/execute", methods=["POST"])
def execute():
    role = session.get("role")
    query = session.get("last_sql")
    task = session.get("last_task")

    adapter = get_active_adapter()
    dialect = adapter.dialect

    if not query or not is_allowed(role, task) or not is_safe(query, dialect):
        session["error"] = "❌ Permission denied or unsafe query."
        return redirect(url_for("index"))

    if task in ("WRITE", "SCHEMA"):
        take_snapshot(adapter)

    if query.lower().startswith("delete"):
        adapter.preview_delete(query)

    adapter.execute(query)

    session.pop("last_sql", None)
    session.pop("last_task", None)
    session.pop("last_explanation", None)

    session["message"] = "✅ Query executed successfully."
    return redirect(url_for("index"))


# ---------------------------------------------------
# Undo (ADMIN ONLY)
# ---------------------------------------------------
@app.route("/undo", methods=["POST"])
def undo_last():
    if session.get("role") != ROLE_ADMIN:
        session["error"] = "❌ Only ADMIN can undo."
        return redirect(url_for("index"))

    adapter = get_active_adapter()
    if not adapter.supports_snapshot:
        session["error"] = "❌ Undo is only available for SQLite databases."
        return redirect(url_for("index"))

    undo(1, adapter)
    session["message"] = "⏪ Undo successful."
    return redirect(url_for("index"))


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

    result = delete_connection(name)
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
    return render_template("analysis.html", analysis_enabled=analysis_enabled)


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

    if not sql or not columns:
        return jsonify({"error": "No query results to analyze. Please run a query first."})

    try:
        adapter = get_active_adapter()
        # Ensure we only analyze a reasonable chunk (analyzer cuts off at 100 rows anyway)
        paginated_sql = paginate_sql(sql, 1) if not (adapter.is_nosql or is_system_query(sql) or is_already_limited(sql)) else sql
        _, rows = adapter.execute(paginated_sql)

        from core.analyzer import analyze_data
        result = analyze_data(columns, rows, user_hint)
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
# Run
# ---------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
