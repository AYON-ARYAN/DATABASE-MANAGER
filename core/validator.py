FORBIDDEN = ["drop database", "attach", "pragma"]

def split_sql(sql):
    return [s.strip() for s in sql.split(";") if s.strip()]

def is_safe(sql: str) -> bool:
    sql_lower = sql.lower().strip()

    # -------------------------
    # Always allow READ queries
    # -------------------------
    if sql_lower.startswith("select"):
        return True

    # -------------------------
    # Block dangerous keywords
    # -------------------------
    dangerous = [
        "drop ",
        "truncate ",
        "alter ",
        "shutdown",
        "attach ",
        "detach ",
        "pragma ",
        "--",
        "/*",
        "*/"
    ]

    for keyword in dangerous:
        if keyword in sql_lower:
            return False

    # -------------------------
    # Allow INSERT / UPDATE / DELETE
    # (snapshot already protects)
    # -------------------------
    if sql_lower.startswith(("insert", "update", "delete")):
        return True

    return False




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
