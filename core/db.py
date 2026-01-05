import sqlite3
import os

# ---------------------------------------------------
# Paths
# ---------------------------------------------------
DB_PATH = "db/main.db"
DB_DIR = "db"


# ---------------------------------------------------
# Connection
# ---------------------------------------------------
def get_connection():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------
# Execute SQL (ALWAYS returns columns, rows)
# ---------------------------------------------------
def execute_sql(sql):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(sql)

    # SELECT queries
    if cur.description:
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
    else:
        # INSERT / UPDATE / DELETE
        columns = []
        rows = []

    conn.commit()
    conn.close()

    return columns, rows


# ---------------------------------------------------
# List database files
# ---------------------------------------------------
def list_db_files():
    if not os.path.exists(DB_DIR):
        return []

    return [
        f for f in os.listdir(DB_DIR)
        if f.endswith(".db") or f.endswith(".sqlite")
    ]


# ---------------------------------------------------
# Schema Introspection
# ---------------------------------------------------
def get_schema():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type='table' AND name NOT LIKE 'sqlite_%';
    """)

    tables = cur.fetchall()
    schema = ""

    for row in tables:
        table_name = row[0]
        schema += f"\nTABLE {table_name}:\n"

        cur.execute(f"PRAGMA table_info({table_name});")
        cols = cur.fetchall()

        for col in cols:
            schema += f"  - {col[1]} ({col[2]})\n"

    conn.close()
    return schema


# ---------------------------------------------------
# List tables (SYSTEM-HANDLED)
# ---------------------------------------------------
def list_tables():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type='table' AND name NOT LIKE 'sqlite_%';
    """)

    tables = [row[0] for row in cur.fetchall()]
    conn.close()
    return tables


# ---------------------------------------------------
# Preview DELETE (row count) – SAFE & CORRECT
# ---------------------------------------------------
def preview_write(sql):
    """
    Safely preview number of rows affected by DELETE.
    Always returns an integer (0 or more) or None.
    """

    sql_clean = sql.strip().rstrip(";")

    if not sql_clean.lower().startswith("delete"):
        return None

    conn = get_connection()
    cur = conn.cursor()

    # DELETE → SELECT COUNT(*)
    count_sql = sql_clean.replace(
        "delete",
        "select count(*)",
        1
    )

    cur.execute(count_sql)
    row = cur.fetchone()

    conn.close()

    # 🔑 SAFETY: if no rows, return 0 instead of crashing
    if row is None:
        return 0

    return row[0]
