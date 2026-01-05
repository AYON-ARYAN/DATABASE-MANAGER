FORBIDDEN = ["drop database", "attach", "pragma"]

def split_sql(sql):
    return [s.strip() for s in sql.split(";") if s.strip()]

def is_safe(sql):
    # 1. SQL must exist
    if not sql or not isinstance(sql, str):
        return False

    sql_clean = sql.strip()
    sql_lower = sql_clean.lower()

    # 2. Block truly dangerous operations
    forbidden = [
        "drop database",
        "attach database",
        "pragma",
        "vacuum",
    ]

    for word in forbidden:
        if word in sql_lower:
            return False

    # 3. Allow ONLY one SQL statement
    statements = [s for s in sql_clean.split(";") if s.strip()]
    if len(statements) != 1:
        return False

    # 4. Explicitly ALLOW SELECT / INSERT / UPDATE / DELETE / CREATE / ALTER
    allowed_starts = (
        "select",
        "insert",
        "update",
        "delete",
        "create",
        "alter",
    )

    if not sql_lower.startswith(allowed_starts):
        return False

    return True



def is_write(sql):
    return sql.strip().lower().startswith(
        ("insert", "update", "delete", "create", "alter")
    )
def classify_sql(sql):
    s = sql.strip().lower()
    if s.startswith(("select",)):
        return "READ"
    if s.startswith(("insert", "update", "delete")):
        return "WRITE"
    if s.startswith(("create", "alter", "drop")):
        return "SCHEMA"
    return "UNKNOWN"
