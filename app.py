from flask import (
    Flask,
    render_template,
    request,
    session,
    redirect,
    url_for
)

from core.llm import generate_sql
from core.validator import is_safe, classify_sql
from core.snapshot import take_snapshot, undo
from core.db import execute_sql, list_tables, preview_write

# ---------------------------------------------------
# Flask App Setup
# ---------------------------------------------------
app = Flask(__name__)
app.secret_key = "dev-secret-key"   # change in production
app.config["SESSION_PERMANENT"] = False


# ---------------------------------------------------
# Home / Command Input
# ---------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        user_cmd = request.form["command"]
        user_cmd_lower = user_cmd.lower()

        # -------------------------------------------
        # SYSTEM-HANDLED TASKS (NO LLM)
        # -------------------------------------------
        if (
            "list all tables" in user_cmd_lower
            or "show tables" in user_cmd_lower
            or "list tables" in user_cmd_lower
        ):
            tables = list_tables()
            return render_template(
                "index.html",
                result=tables,
                message="📋 Tables listed successfully."
            )

        # -------------------------------------------
        # LLM-HANDLED TASKS
        # -------------------------------------------
        sql = generate_sql(user_cmd)

        # store SQL in session for execution step
        session["last_sql"] = sql

        return render_template("review.html", sql=sql)

    # -------------------------------------------
    # GET request (after redirect)
    # -------------------------------------------
    result = session.pop("last_result", None)
    return render_template("index.html", **(result or {}))


# ---------------------------------------------------
# Execute SQL (POST → REDIRECT → GET)
# ---------------------------------------------------
@app.route("/execute", methods=["POST"])
def execute():
    sql = session.get("last_sql")

    if not sql:
        session["last_result"] = {
            "message": "❌ No SQL to execute. Generate SQL first."
        }
        return redirect(url_for("index"))

    if not is_safe(sql):
        session["last_result"] = {
            "message": "❌ Unsafe SQL blocked."
        }
        session.pop("last_sql", None)
        return redirect(url_for("index"))

    task = classify_sql(sql)

    # snapshot for WRITE / SCHEMA
    if task in ("WRITE", "SCHEMA"):
        take_snapshot()

    # optional delete preview
    preview = None
    if sql.strip().lower().startswith("delete"):
        preview = preview_write(sql)

    columns, rows = execute_sql(sql)

    # clear SQL after execution
    session.pop("last_sql", None)

    # store execution result for redirect
    session["last_result"] = {
    "columns": columns,
    "rows": rows_to_list(rows),  # 🔥 FIX HERE
    "row_count": len(rows),
    "preview": preview,
    "message": "✅ Query executed successfully."
}


    return redirect(url_for("index"))


# ---------------------------------------------------
# Undo Last Change
# ---------------------------------------------------
@app.route("/undo")
def undo_last():
    undo(1)
    session["last_result"] = {
        "message": "⏪ Undo successful. Database restored."
    }
    return redirect(url_for("index"))
def rows_to_list(rows):
    return [list(row) for row in rows]


# ---------------------------------------------------
# Run App
# ---------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
