"""
LLM Integration — Dialect-Aware
Sends natural language + database schema to Ollama (Mistral)
and receives generated queries (SQL, CQL, MongoDB JSON, Redis commands).
"""

import os
import requests
import time
from dotenv import load_dotenv
from core.metrics import log_call

load_dotenv()

OLLAMA_URL = "http://localhost:11434/api/generate"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


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
- NEVER output plain text, lists, or conversational responses.
- Even if you know the answer from the schema, GENERATE THE SQL to fetch it.
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
- NEVER output plain text, lists, or conversational responses.
- Even if you know the answer from the schema, GENERATE THE SQL to fetch it.
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
- NEVER output plain text, lists, or conversational responses.
- Even if you know the answer from the schema, GENERATE THE SQL to fetch it.
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


def clean_sql(text: str) -> str:
    """Strips markdown code fences, backticks, and unnecessary whitespace from LLM output."""
    text = text.strip()
    
    # Remove triple backticks
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) > 2 and lines[0].startswith("```"):
            text = "\n".join(lines[1:-1])
        else:
            text = text.replace("```sql", "").replace("```", "")
            
    # Aggressively remove single backticks and other formatting debris from ends
    text = text.strip("` \n\t")
        
    return text.strip().strip(";")

def _get_system_prompt(dialect: str, schema: str) -> str:
    """Build the system prompt for a given dialect and schema."""
    template = PROMPT_TEMPLATES.get(dialect, PROMPT_TEMPLATES["sqlite"])
    return template.format(schema=f"DATABASE SCHEMA:\n{schema}")


# ---------------------------------------------------
# Core generation
# ---------------------------------------------------
def generate_query(user_command: str, dialect: str = "sqlite", schema: str = "", provider: str = None, history: list = None, system_prompt: str = None, options: dict = None) -> str:
    """
    Given a natural language command, generate a query
    appropriate for the database dialect using specified provider.
    """
    from core import llm_manager
    managed_provider, p_config = llm_manager.get_active_config()
    
    # Use override provider if passed, otherwise use managed one
    provider = provider or managed_provider
    if provider != managed_provider:
        # If we are overriding, we need to load that provider's config too
        full_config = llm_manager.load_config()
        p_config = full_config["providers"].get(provider, p_config)

    history = history or []
    context = system_prompt or _get_system_prompt(dialect, schema)
    
    # Format history for prompt injection (Ollama)
    history_str = ""
    for msg in history:
        history_str += f"USER: {msg['user']}\nASSISTANT: {msg['assistant']}\n"
    
    full_prompt = context + f"\nCONVERSATION HISTORY:\n{history_str}" + f"\nUSER COMMAND:\n{user_command}"

    start_time = time.time()
    latency = 0
    prompt_tokens = 0
    completion_tokens = 0

    if provider == "groq":
        api_key = p_config.get("api_key")
        model = p_config.get("model", "llama-3.3-70b-versatile")
        url = p_config.get("url", GROQ_API_URL)

        if api_key:
            messages = [{"role": "system", "content": context}]
            for msg in history:
                messages.append({"role": "user", "content": msg["user"]})
                messages.append({"role": "assistant", "content": msg["assistant"]})
            messages.append({"role": "user", "content": f"USER COMMAND:\n{user_command}"})
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.1
            }
            try:
                res = requests.post(url, headers=headers, json=payload, timeout=60)
                res.raise_for_status()
                data = res.json()
                latency = time.time() - start_time
                
                # Extract usage info
                usage = data.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                
                log_call("groq", data.get("model", model), latency, prompt_tokens, completion_tokens)
                return clean_sql(data["choices"][0]["message"]["content"])
            except Exception as e:
                print(f"Groq API Error: {e}")
                # Don't return yet, fall through to Ollama if this fails

    # Default / Fallback: Ollama Local
    ollama_config = p_config if provider == "mistral" else llm_manager.load_config()["providers"]["mistral"]
    ollama_url = ollama_config.get("url", OLLAMA_URL)
    ollama_model = ollama_config.get("model", "mistral")

    # Resource Optimization: Default to 4 threads if not specified, and reasonable context
    # This reduces CPU spike and RAM thrashing
    default_options = {
        "num_thread": 4,
        "num_ctx": 2048,
        "temperature": 0.1
    }
    if options:
        default_options.update(options)

    try:
        res = requests.post(
            ollama_url,
            json={
                "model": ollama_model,
                "prompt": full_prompt,
                "stream": False,
                "options": default_options
            },
            timeout=60,
        )
        latency = time.time() - start_time
        data = res.json()
        
        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)
        
        log_call("mistral", ollama_model, latency, prompt_tokens, completion_tokens)
        return clean_sql(data["response"])
    except Exception as e:
        print(f"Ollama Error: {e}")
        return "ERROR: Connection failed"


def generate_query_with_explanation(
    user_command: str,
    dialect: str = "sqlite",
    schema: str = "",
    provider: str = "mistral",
    history: list = None,
    system_prompt: str = None
) -> tuple:
    """
    Returns:
    - query (str) — SQL / CQL / JSON
    - explanation (str) — human-readable explanation
    
    OPTIMIZATION: Merges query and explanation into a single LLM call.
    """
    context = system_prompt or _get_system_prompt(dialect, schema)
    
    # Refined prompt for single-call output
    merged_prompt = f"""
{context}

USER COMMAND: {user_command}

RESPONSE FORMAT:
Provide the response in the following structured format:
QUERY: <the_raw_query_only>
EXPLANATION: <short_bulleted_explanation_without_tech_jargon>
"""
    
    # 1. Get raw merged response
    raw_response = generate_query(
        user_command="", # We embed the command in system_prompt for precision
        dialect=dialect,
        schema=schema,
        provider=provider,
        history=history,
        system_prompt=merged_prompt,
        options={"num_predict": 512} # Limit length to save resources
    )

    # 2. Parse results
    query = ""
    explanation = "No explanation generated."
    
    # Try case-insensitive partition
    raw_lower = raw_response.lower()
    if "query:" in raw_lower and "explanation:" in raw_lower:
        try:
            # Flexible parsing: finds the first occurrence regardless of case
            q_start = raw_lower.find("query:") + len("query:")
            e_idx = raw_lower.find("explanation:")
            
            query_raw = raw_response[q_start:e_idx].strip()
            explanation_raw = raw_response[e_idx + len("explanation:"):].strip()
            
            query = clean_sql(query_raw)
            explanation = explanation_raw
        except Exception:
            query = clean_sql(raw_response)
    else:
        # Fallback if structure failed: assume the whole thing might be the query
        # But if it's very long, it might just be a failed structured response
        query = clean_sql(raw_response)

    return query, explanation


# ---------------------------------------------------
# Backward compatibility
# ---------------------------------------------------
def generate_sql(user_command: str, provider: str = "mistral") -> str:
    """Legacy. Calls generate_query with SQLite defaults."""
    from core.db import get_schema, list_db_files
    schema = get_schema()
    return generate_query(user_command, "sqlite", schema, provider)


def generate_sql_with_explanation(user_command: str, provider: str = "mistral") -> tuple:
    """Legacy. Calls generate_query_with_explanation with SQLite defaults."""
    from core.db import get_schema
    schema = get_schema()
    return generate_query_with_explanation(user_command, "sqlite", schema, provider)
