import requests
from core.db import get_schema, list_db_files

OLLAMA_URL = "http://localhost:11434/api/generate"

def generate_sql(user_command):
    db_files = list_db_files()
    schema = get_schema()

    context = f"""
SYSTEM CONTEXT:
Database engine: SQLite
Available database files: {db_files}

DATABASE SCHEMA:
{schema}

IMPORTANT RULES:
- You manage ONLY the existing SQLite database
- There is NO create database
- Use ONLY tables and columns shown above
- DO NOT generate SELECT * queries to list tables
- Schema inspection (list tables, describe tables) is handled by the system
- Output ONLY SQL
- SQLite syntax only
For SELECT queries:
- Always include LIMIT 50 unless user specifies otherwise
- No markdown
- No explanation
"""


    prompt = context + f"\nUSER COMMAND:\n{user_command}"

    res = requests.post(
        OLLAMA_URL,
        json={
            "model": "mistral",
            "prompt": prompt,
            "stream": False
        },
        timeout=60
    )

    return res.json()["response"].strip()
