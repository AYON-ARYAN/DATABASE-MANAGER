"""
LLM Integration — Dialect-Aware
Sends natural language + database schema to Ollama (Mistral)
and receives generated queries (SQL, CQL, MongoDB JSON, Redis commands).
"""

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"


# ---------------------------------------------------
# Dialect-specific system prompts
# ---------------------------------------------------
PROMPT_TEMPLATES = {
    "sqlite": """
SYSTEM CONTEXT:
Database engine: SQLite
{schema}

IMPORTANT RULES:
- Use ONLY tables and columns shown above
- Output ONLY valid SQLite SQL
- DO NOT generate SELECT * queries to list tables
- Schema inspection is handled by the system
- For SELECT queries: always include LIMIT 50 unless user specifies otherwise
- No markdown, no explanation, no code fences
""",

    "mysql": """
SYSTEM CONTEXT:
Database engine: MySQL
{schema}

IMPORTANT RULES:
- Use ONLY tables and columns shown above
- Output ONLY valid MySQL SQL
- Use MySQL syntax (e.g., backticks for identifiers, LIMIT clause)
- DO NOT generate SHOW TABLES or DESCRIBE queries
- For SELECT queries: always include LIMIT 50 unless user specifies otherwise
- No markdown, no explanation, no code fences
""",

    "postgresql": """
SYSTEM CONTEXT:
Database engine: PostgreSQL
{schema}

IMPORTANT RULES:
- Use ONLY tables and columns shown above
- Output ONLY valid PostgreSQL SQL
- Use PostgreSQL syntax (e.g., double quotes for identifiers, :: for casts)
- DO NOT generate \\dt or information_schema queries
- For SELECT queries: always include LIMIT 50 unless user specifies otherwise
- No markdown, no explanation, no code fences
""",

    "mssql": """
SYSTEM CONTEXT:
Database engine: Microsoft SQL Server (T-SQL)
{schema}

IMPORTANT RULES:
- Use ONLY tables and columns shown above
- Output ONLY valid T-SQL
- Use TOP N instead of LIMIT (e.g., SELECT TOP 50 ...)
- Use [] for identifiers with spaces
- DO NOT generate sp_tables or sys.tables queries
- For SELECT queries: always include TOP 50 unless user specifies otherwise
- No markdown, no explanation, no code fences
""",

    "oracle": """
SYSTEM CONTEXT:
Database engine: Oracle Database
{schema}

IMPORTANT RULES:
- Use ONLY tables and columns shown above
- Output ONLY valid Oracle SQL
- Use FETCH FIRST N ROWS ONLY for limiting (Oracle 12c+)
- DO NOT generate USER_TABLES or ALL_TABLES queries
- For SELECT queries: always include FETCH FIRST 50 ROWS ONLY unless user specifies otherwise
- No markdown, no explanation, no code fences
""",

    "mongodb": """
SYSTEM CONTEXT:
Database engine: MongoDB
{schema}

IMPORTANT RULES:
- Output ONLY a valid JSON object with the following structure:
  {{
      "operation": "<find|aggregate|count|insertOne|insertMany|updateOne|updateMany|deleteOne|deleteMany>",
      "collection": "<collection_name>",
      "filter": {{}},
      "projection": {{}},
      "sort": {{}},
      "limit": 50,
      "document": {{}},
      "documents": [],
      "update": {{}},
      "pipeline": []
  }}
- Use ONLY the collections and fields shown above
- Include only fields relevant to the operation
- For find queries: always include "limit": 50 unless user specifies otherwise
- No markdown, no explanation, no code fences
- Output MUST be valid parseable JSON
""",

    "cassandra": """
SYSTEM CONTEXT:
Database engine: Apache Cassandra (CQL)
{schema}

IMPORTANT RULES:
- Use ONLY tables and columns shown above
- Output ONLY valid CQL (Cassandra Query Language)
- CQL is similar to SQL but limited (no JOINs, no subqueries)
- Use LIMIT for row limits
- For SELECT queries: always include LIMIT 50 unless user specifies otherwise
- No markdown, no explanation, no code fences
""",

    "redis": """
SYSTEM CONTEXT:
Database engine: Redis
{schema}

IMPORTANT RULES:
- Output ONLY a valid JSON object with the following structure:
  For a single command:
  {{
      "command": "<REDIS_COMMAND>",
      "args": ["arg1", "arg2"]
  }}

  For multiple commands:
  {{
      "commands": [
          {{"command": "SET", "args": ["key", "value"]}},
          {{"command": "GET", "args": ["key"]}}
      ]
  }}
- Use standard Redis commands (GET, SET, HGET, HSET, LPUSH, LRANGE, SMEMBERS, KEYS, etc.)
- Use ONLY keys / patterns shown in the schema above
- No markdown, no explanation, no code fences
- Output MUST be valid parseable JSON
""",
}


def _get_system_prompt(dialect: str, schema: str) -> str:
    """Build the system prompt for a given dialect and schema."""
    template = PROMPT_TEMPLATES.get(dialect, PROMPT_TEMPLATES["sqlite"])
    return template.format(schema=f"DATABASE SCHEMA:\n{schema}")


# ---------------------------------------------------
# Core generation
# ---------------------------------------------------
def generate_query(user_command: str, dialect: str = "sqlite", schema: str = "") -> str:
    """
    Given a natural language command, generate a query
    appropriate for the database dialect.
    """
    context = _get_system_prompt(dialect, schema)
    prompt = context + f"\nUSER COMMAND:\n{user_command}"

    res = requests.post(
        OLLAMA_URL,
        json={
            "model": "mistral",
            "prompt": prompt,
            "stream": False,
        },
        timeout=60,
    )

    return res.json()["response"].strip()


def generate_query_with_explanation(
    user_command: str,
    dialect: str = "sqlite",
    schema: str = "",
) -> tuple:
    """
    Returns:
    - query (str) — SQL / CQL / JSON
    - explanation (str) — human-readable explanation
    """
    # 1. Generate the query
    query = generate_query(user_command, dialect, schema)

    # 2. Ask LLM to explain it
    if dialect in ("mongodb", "redis"):
        explain_prompt = f"""
Explain the following {dialect.upper()} query in simple, clear steps.
Do NOT mention technical syntax.
Do NOT add code blocks.
Use bullet points.

Query:
{query}
"""
    else:
        explain_prompt = f"""
Explain the following SQL query in simple, clear steps.
Do NOT mention SQL keywords.
Do NOT add code blocks.
Use bullet points.

SQL:
{query}
"""

    explanation_context = ""
    explanation_full_prompt = explanation_context + explain_prompt

    res = requests.post(
        OLLAMA_URL,
        json={
            "model": "mistral",
            "prompt": explanation_full_prompt,
            "stream": False,
        },
        timeout=60,
    )

    explanation = res.json()["response"].strip()
    return query, explanation


# ---------------------------------------------------
# Backward compatibility
# ---------------------------------------------------
def generate_sql(user_command: str) -> str:
    """Legacy. Calls generate_query with SQLite defaults."""
    from core.db import get_schema, list_db_files
    schema = get_schema()
    return generate_query(user_command, "sqlite", schema)


def generate_sql_with_explanation(user_command: str) -> tuple:
    """Legacy. Calls generate_query_with_explanation with SQLite defaults."""
    from core.db import get_schema
    schema = get_schema()
    return generate_query_with_explanation(user_command, "sqlite", schema)
