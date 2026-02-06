from flask import (
    Flask, render_template, request,
    session, redirect, url_for, Response
)
from datetime import datetime
from io import StringIO
import csv

from werkzeug.security import generate_password_hash, check_password_hash

from core.validator import is_safe, classify_sql
from core.snapshot import take_snapshot, undo
from core.db import execute_sql, list_tables, preview_write
from core.llm import generate_sql_with_explanation


# ---------------------------------------------------
# Flask App Setup
# ---------------------------------------------------
app = Flask(__name__)
app.secret_key = "dev-secret-key"
app.config["SESSION_PERMANENT"] = False

PAGE_SIZE = 50


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


def safe_count(sql):
    if is_system_query(sql) or is_already_limited(sql):
        return None
    try:
        _, rows = execute_sql(f"SELECT COUNT(*) FROM ({sql.rstrip(';')}) AS subq")
        return rows[0][0] if rows else 0
    except Exception:
        return None


def add_to_history(query, sql, task, status):
    history = session.get("history", [])
    history.insert(0, {
        "query": query,
        "sql": sql,
        "task": task,
        "status": status,
        "user": session.get("username"),
        "time": datetime.now().strftime("%H:%M")
    })
    session["history"] = history[:10]


# ---------------------------------------------------
# AUTH GUARD (FIXED & STABLE)
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

    # ---------- POST ----------
    if request.method == "POST":
        user_cmd = request.form.get("command", "").strip()
        if not user_cmd:
            return render_template("index.html", error="❌ Empty command.", history=session.get("history", []))

        # SYSTEM
        if user_cmd.lower() in ("list tables", "show tables"):
            if not is_allowed(role, "SYSTEM"):
                return render_template("index.html", error="❌ Permission denied.", history=session.get("history", []))

            tables = list_tables()
            add_to_history(user_cmd, "SHOW TABLES", "SYSTEM", "EXECUTED")

            return render_template(
                "index.html",
                task="SYSTEM",
                columns=["Tables"],
                results=[[t] for t in tables],
                page=1,
                page_size=len(tables),
                total_rows=len(tables),
                history=session.get("history", [])
            )

        # LLM
        sql, explanation = generate_sql_with_explanation(user_cmd)
        task = classify_sql(sql)

        if not is_allowed(role, task):
            add_to_history(user_cmd, sql, task, "BLOCKED (ROLE)")
            return render_template(
                "index.html",
                error=f"❌ {role} not allowed to run {task}",
                history=session.get("history", [])
            )

        # READ
        if task == "READ":
            if not is_safe(sql):
                add_to_history(user_cmd, sql, "READ", "BLOCKED")
                return render_template("index.html", error="❌ Unsafe SQL blocked.", history=session.get("history", []))

            session["last_read_sql"] = sql
            session["last_explanation"] = explanation

            page = 1
            if is_system_query(sql) or is_already_limited(sql):
                paginated_sql = sql
                columns, rows = execute_sql(sql)
                total_rows = len(rows)
            else:
                paginated_sql = paginate_sql(sql, page)
                columns, rows = execute_sql(paginated_sql)
                total_rows = safe_count(sql)

            session["last_read_columns"] = columns
            add_to_history(user_cmd, sql, "READ", "EXECUTED")

            return render_template(
                "index.html",
                sql=paginated_sql,
                explanation=explanation,
                task="READ",
                columns=columns,
                results=rows_to_list(rows),
                page=page,
                page_size=PAGE_SIZE,
                total_rows=total_rows,
                history=session.get("history", [])
            )

        # WRITE / SCHEMA
        add_to_history(user_cmd, sql, task, "PENDING REVIEW")
        session["last_sql"] = sql
        session["last_task"] = task
        session["last_explanation"] = explanation

        return render_template(
            "review.html",
            sql=sql,
            explanation=explanation,
            task=task,
            history=session.get("history", [])
        )

    # ---------- GET (Pagination) ----------
    page = request.args.get("page")
    if page and session.get("last_read_sql"):
        sql = session["last_read_sql"]
        explanation = session.get("last_explanation")
        page = max(1, int(page))

        paginated_sql = paginate_sql(sql, page)
        columns, rows = execute_sql(paginated_sql)
        total_rows = safe_count(sql)

        return render_template(
            "index.html",
            sql=paginated_sql,
            explanation=explanation,
            task="READ",
            columns=columns,
            results=rows_to_list(rows),
            page=page,
            page_size=PAGE_SIZE,
            total_rows=total_rows,
            history=session.get("history", [])
        )

    return render_template(
        "index.html",
        message=session.pop("message", None),
        error=session.pop("error", None),
        history=session.get("history", [])
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

    _, rows = execute_sql(sql)

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    for r in rows:
        writer.writerow(r)

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
    sql = session.get("last_sql")
    task = session.get("last_task")

    if not sql or not is_allowed(role, task) or not is_safe(sql):
        session["error"] = "❌ Permission denied or unsafe SQL."
        return redirect(url_for("index"))

    if task in ("WRITE", "SCHEMA"):
        take_snapshot()

    if sql.lower().startswith("delete"):
        preview_write(sql)

    execute_sql(sql)

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

    undo(1)
    session["message"] = "⏪ Undo successful."
    return redirect(url_for("index"))


# ---------------------------------------------------
# Run
# ---------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
