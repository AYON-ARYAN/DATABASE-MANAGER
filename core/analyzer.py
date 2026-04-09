import os
import json
import re
import time
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Initialize Groq client
# This requires GROQ_API_KEY environment variable to be set
try:
    GROQ_CLIENT = Groq(api_key=os.environ.get("GROQ_API_KEY"))
except Exception:
    GROQ_CLIENT = None

# ---------------------------------------------------
# Full Database Analysis — Job Tracking
# ---------------------------------------------------
_analysis_jobs = {}  # job_id -> {status, progress, step, total_steps, result, created_at}
_jobs_lock = threading.Lock()


def analyze_data(columns: list, rows: list, user_hint: str = "") -> dict:
    """
    Sends tabular data to Groq and returns analysis + chart config.
    """
    if not GROQ_CLIENT:
        return {
            "error": "Groq API key not configured. Please set the GROQ_API_KEY environment variable."
        }

    if not columns or not rows:
        return {"error": "No data available to analyze."}

    # Format data as markdown table for the LLM
    # Limit rows to prevent massive token usage on large datasets
    max_rows = 100
    display_rows = rows[:max_rows]
    
    header = "| " + " | ".join(str(c) for c in columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    
    table_lines = [header, separator]
    for row in display_rows:
        # Ensure row is a list/tuple even if it's a single value
        if not isinstance(row, (list, tuple)):
            row = [row]
        table_lines.append("| " + " | ".join(str(val) for val in row) + " |")
        
    data_str = "\n".join(table_lines)
    if len(rows) > max_rows:
        data_str += f"\n\n*(Note: Data truncated to first {max_rows} rows for analysis)*"

    hint_str = f"User Request/Hint: {user_hint}\n\n" if user_hint else ""

    prompt = f"""You are an expert data analyst. Read the following data and provide insights and a visualization configuration.

{hint_str}DATA:
{data_str}

OUTPUT FORMAT:
You MUST respond with ONLY a raw JSON object and nothing else. Do not use markdown code blocks (like ```json). Do not add any explanatory text outside the JSON.

The JSON object must have this exact structure:
{{
    "summary": "A detailed, insightful summary of the data. If the user provided a hint with questions or requests for suggestions, answer them comprehensively here in beautifully formatted text.",
    "chart": {{
        "type": "pie", 
        "title": "Title of the chart",
        "labels": ["Label1", "Label2"],
        "datasets": [
            {{
                "label": "Dataset Label",
                "data": [10, 20]
            }}
        ]
    }}
}}

RULES FOR CHART:
- "type" MUST be one of: "pie", "bar", "line", "doughnut", "area", "scatter"
- "labels" should be an array of strings (e.g., categories, dates, or X-axis values)
- "data" should be an array of numbers corresponding to the labels
- For "scatter": "data" should be an array of numerical values, and "labels" should also contain numerical values representing the X-axis.
- SMART RECOMMENDATION:
    - "pie" / "doughnut": For parts of a whole (percentage distribution).
    - "bar": For simple categorical vs numerical comparisons.
    - "line": For trends over time or sequences.
    - "area": For volume trends over time (stacked or singular).
    - "scatter": For identifying correlations between two numerical variables.
    - Choose the chart type that BEST represents the data shape provided.
"""

    try:
        response = GROQ_CLIENT.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a data analysis engine that outputs strict JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            response_format={"type": "json_object"}
        )

        result_text = response.choices[0].message.content.strip()
        
        # In case the model still wrapped it in markdown
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
            
        return json.loads(result_text)

    except Exception as e:
        return {"error": f"Analysis failed: {str(e)}"}


def ai_ask(question: str, schema: str, db_name: str, table_stats: list = None,
           dialect: str = "sqlite", fk_info: list = None) -> dict:
    """
    General-purpose AI Q&A with full database context.
    Answers any question about the database using Groq.
    Returns {"answer": "...", "suggested_queries": [...]}
    """
    if not GROQ_CLIENT:
        return {"error": "Groq API key not configured. Set GROQ_API_KEY in .env file."}

    stats_str = ""
    if table_stats:
        stats_str = "\n\nTABLE STATISTICS:\n"
        for ts in table_stats:
            stats_str += f"  - {ts['table']}: {ts['rows']} rows\n"

    fk_str = ""
    if fk_info:
        fk_str = "\n\nFOREIGN KEY RELATIONSHIPS:\n"
        for fk in fk_info:
            fk_str += f"  - {fk['from_table']}.{fk['from_column']} -> {fk['to_table']}.{fk['to_column']}\n"

    dialect_map = {
        "sqlite": "SQLite", "postgresql": "PostgreSQL", "mysql": "MySQL",
        "mssql": "Microsoft SQL Server (T-SQL)", "oracle": "Oracle PL/SQL",
        "mongodb": "MongoDB", "cassandra": "Cassandra CQL", "redis": "Redis",
    }
    dialect_name = dialect_map.get(dialect, dialect)

    prompt = f"""You are an expert DBMS teaching assistant and database analyst.
You have full access to the following database schema, including column types, primary keys, foreign keys, indexes, and sample data for every table.

DATABASE: {db_name}
SQL DIALECT: {dialect_name}

FULL SCHEMA (includes columns, types, PKs, FKs, indexes, and sample data):
{schema}
{stats_str}{fk_str}

USER QUESTION: {question}

CRITICAL RULES:
- You MUST generate SQL that is valid for {dialect_name} syntax only
- Use the EXACT table and column names from the schema above
- The schema includes SAMPLE DATA rows — use them to understand the data format and give accurate answers
- If the user asks about actual data values, counts, or patterns, write a SQL query to answer it
- Every SQL query you write should be executable as-is against this database

INSTRUCTIONS:
- Answer the question thoroughly and helpfully using the full schema context
- If the question is about SQL concepts (JOINs, normalization, indexes, etc.), explain with examples from THIS database
- If the question is about the data, provide specific executable SQL queries
- If they ask "what can I do" or "help", give a comprehensive overview and suggest interesting queries
- Format your answer in clean Markdown with headers, bullet points, and code blocks for SQL
- At the end, suggest 3 follow-up SQL queries they might want to try (as a JSON array in a special section)

RESPONSE FORMAT:
Start with your detailed answer in Markdown.
Then at the very end, add this exact section:
---SUGGESTED_QUERIES---
["query1", "query2", "query3"]
"""

    try:
        response = GROQ_CLIENT.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": f"You are a helpful DBMS teaching assistant specializing in {dialect_name}. You explain database concepts clearly and provide practical, executable SQL examples from the user's actual database schema and data."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )

        raw = response.choices[0].message.content.strip()

        # Parse out suggested queries
        answer = raw
        suggested = []
        if "---SUGGESTED_QUERIES---" in raw:
            parts = raw.split("---SUGGESTED_QUERIES---")
            answer = parts[0].strip()
            try:
                suggested = json.loads(parts[1].strip())
            except Exception:
                suggested = []

        return {"answer": answer, "suggested_queries": suggested}

    except Exception as e:
        return {"error": f"AI Ask failed: {str(e)}"}


def get_table_overview(schema: str, db_name: str, table_stats: list,
                       dialect: str = "sqlite") -> dict:
    """
    Generates a complete database overview with charts data for the overview dashboard.
    Returns {"summary": "...", "charts": [...]}
    """
    if not GROQ_CLIENT:
        return {"error": "Groq API key not configured."}

    dialect_map = {
        "sqlite": "SQLite", "postgresql": "PostgreSQL", "mysql": "MySQL",
        "mssql": "Microsoft SQL Server (T-SQL)", "oracle": "Oracle PL/SQL",
        "mongodb": "MongoDB", "cassandra": "Cassandra CQL", "redis": "Redis",
    }
    dialect_name = dialect_map.get(dialect, dialect)

    stats_str = "\n".join([f"  - {ts['table']}: {ts['rows']} rows" for ts in table_stats])

    prompt = f"""You are a database analytics engine. Analyze this database and return a JSON overview report.

DATABASE: {db_name}
SQL DIALECT: {dialect_name}

FULL SCHEMA (includes columns, types, PKs, FKs, indexes, and sample data):
{schema}

TABLE STATISTICS:
{stats_str}

Return ONLY a raw JSON object with this structure:
{{
    "summary": "A 2-3 paragraph executive summary of this database - what it stores, key relationships, and notable patterns.",
    "highlights": [
        {{"label": "Total Tables", "value": "N"}},
        {{"label": "Total Rows", "value": "N"}},
        {{"label": "Foreign Keys", "value": "N"}},
        {{"label": "Largest Table", "value": "tablename (N rows)"}}
    ],
    "table_size_chart": {{
        "labels": ["table1", "table2"],
        "data": [100, 200]
    }},
    "relationship_map": [
        {{"from": "Orders", "to": "Customers", "via": "CustomerID"}},
        {{"from": "OrderDetails", "to": "Products", "via": "ProductID"}}
    ],
    "suggested_queries": [
        {{"title": "Top customers by order count", "query": "SELECT ...", "chart_type": "bar"}},
        {{"title": "Revenue by category", "query": "SELECT ...", "chart_type": "pie"}}
    ]
}}

CRITICAL RULES:
- All SQL MUST be valid {dialect_name} syntax — do not use syntax from other dialects
- Use EXACT table and column names from the schema above
- The schema includes SAMPLE DATA and FOREIGN KEYS — use them to understand the data
- suggested_queries should be 4-6 interesting analytical queries that will actually run
- table_size_chart should include ALL tables sorted by size
- relationship_map should include ALL foreign key relationships from the schema
"""

    try:
        response = GROQ_CLIENT.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a database analytics engine that outputs strict JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            response_format={"type": "json_object"}
        )

        result_text = response.choices[0].message.content.strip()
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
        return json.loads(result_text)

    except Exception as e:
        return {"error": f"Overview generation failed: {str(e)}"}


def analyze_schema(schema: str, db_name: str) -> dict:
    """
    Analyzes the raw schema of a database and returns high-level business intelligence insights.
    """
    if not GROQ_CLIENT:
        return {"error": "Groq API key not configured."}

    prompt = f"""You are an expert Data Architect and Business Intelligence Analyst.
Analyze the following database schema for a database named '{db_name}'.

SCHEMA:
{schema}

Provide a comprehensive, beautifully formatted Markdown report containing:
1. **Executive Overview**: What is the primary purpose of this database? (e.g., E-commerce, HR, Inventory).
2. **Key Entities & Relationships**: A brief summary of the most important tables and how they conceptually link.
3. **Data Quality & Schema Observations**: Any interesting notes on data types, potential missing foreign keys, or structural patterns.
4. **Top 5 Business Questions**: List the top 5 most valuable analytical questions a business owner could ask this database (e.g. "What is the lifetime value of customers?").

Format the output strictly as Markdown text. Make it look highly professional and polished. Do not return JSON. Just return the raw markdown string.
"""

    try:
        response = GROQ_CLIENT.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You provide extremely professional, deep-dive database schema analyses formatted in clean Markdown."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        return {"markdown": response.choices[0].message.content.strip()}
    except Exception as e:
        return {"error": f"Analysis failed: {str(e)}"}


# ---------------------------------------------------
# Full Database Analysis — Query Generation (LLM Call 1)
# ---------------------------------------------------
def generate_analytical_queries(schema: str, db_name: str, table_stats: list,
                                fk_info: list = None, dialect: str = "sqlite") -> dict:
    """
    Given full DB context, asks the LLM to produce 6-10 analytical SELECT queries.
    Returns {"queries": [{"title": "...", "sql": "...", "chart_type": "bar"}, ...]}
    """
    if not GROQ_CLIENT:
        return {"error": "Groq API key not configured."}

    dialect_map = {
        "sqlite": "SQLite", "postgresql": "PostgreSQL", "mysql": "MySQL",
        "mssql": "Microsoft SQL Server (T-SQL)", "oracle": "Oracle PL/SQL",
        "mongodb": "MongoDB", "cassandra": "Cassandra CQL", "redis": "Redis",
    }
    dialect_name = dialect_map.get(dialect, dialect)

    stats_str = "\n".join([f"  - {ts['table']}: {ts['rows']} rows" for ts in table_stats])

    fk_str = ""
    if fk_info:
        fk_str = "\n\nFOREIGN KEY RELATIONSHIPS:\n"
        for fk in fk_info:
            fk_str += f"  - {fk['from_table']}.{fk['from_column']} -> {fk['to_table']}.{fk['to_column']}\n"

    prompt = f"""You are an expert data analyst. You have access to a database and must generate the most insightful analytical queries to understand it.

DATABASE: {db_name}
SQL DIALECT: {dialect_name}

FULL SCHEMA (includes columns, types, PKs, FKs, indexes, and sample data):
{schema}

TABLE STATISTICS:
{stats_str}
{fk_str}

Generate 6-10 analytical SELECT queries that would provide the most valuable insights about this database. Cover these categories:
- Distribution analysis (how data is spread across categories)
- Top-N rankings (best/worst performers)
- Aggregations and summaries (totals, averages, counts)
- Cross-table joins (relationships between entities)
- Time-based trends (if date/time columns exist)
- Anomaly detection (outliers, nulls, unusual patterns)

CRITICAL RULES:
- ALL queries MUST be valid {dialect_name} syntax
- ALL queries MUST be SELECT statements (read-only)
- ALL queries MUST include LIMIT 500
- Use the EXACT table and column names from the schema
- Each query should reveal something genuinely interesting about the data
- Vary the chart types to create a visually diverse report

Return ONLY a raw JSON object:
{{
    "queries": [
        {{
            "title": "Short descriptive title",
            "sql": "SELECT ... LIMIT 500",
            "chart_type": "bar"
        }}
    ]
}}

"chart_type" must be one of: "pie", "bar", "line", "doughnut", "area", "scatter"
"""

    try:
        response = GROQ_CLIENT.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a data analysis query generator that outputs strict JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        result_text = response.choices[0].message.content.strip()
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
        parsed = json.loads(result_text)
        # Cap at 10 queries
        if "queries" in parsed:
            parsed["queries"] = parsed["queries"][:10]
        return parsed
    except Exception as e:
        return {"error": f"Query generation failed: {str(e)}"}


# ---------------------------------------------------
# Full Database Analysis — Report Generation (LLM Call 2)
# ---------------------------------------------------
def generate_full_report(schema: str, db_name: str, table_stats: list,
                         fk_info: list, query_results: list,
                         dialect: str = "sqlite") -> dict:
    """
    Given DB context and executed query results, generates a full analytical report.
    Returns {"executive_summary": "markdown", "insights": [{"title", "markdown", "chart", "sql"}, ...]}
    """
    if not GROQ_CLIENT:
        return {"error": "Groq API key not configured."}

    dialect_map = {
        "sqlite": "SQLite", "postgresql": "PostgreSQL", "mysql": "MySQL",
        "mssql": "Microsoft SQL Server (T-SQL)", "oracle": "Oracle PL/SQL",
        "mongodb": "MongoDB", "cassandra": "Cassandra CQL", "redis": "Redis",
    }
    dialect_name = dialect_map.get(dialect, dialect)

    stats_str = "\n".join([f"  - {ts['table']}: {ts['rows']} rows" for ts in table_stats])

    # Format each query result as a section
    results_sections = []
    for i, qr in enumerate(query_results):
        section = f"\n--- QUERY {i+1}: {qr['title']} ---\nSQL: {qr['sql']}\n"
        if qr.get("error"):
            section += f"ERROR: {qr['error']}\n"
        elif qr.get("columns") and qr.get("rows"):
            cols = qr["columns"]
            rows = qr["rows"][:50]  # Truncate to 50 rows for token budget
            header = "| " + " | ".join(str(c) for c in cols) + " |"
            sep = "| " + " | ".join("---" for _ in cols) + " |"
            section += header + "\n" + sep + "\n"
            for row in rows:
                if not isinstance(row, (list, tuple)):
                    row = [row]
                section += "| " + " | ".join(str(v) for v in row) + " |\n"
            if len(qr["rows"]) > 50:
                section += f"*(Showing 50 of {len(qr['rows'])} rows)*\n"
        else:
            section += "No data returned.\n"
        results_sections.append(section)

    all_results = "\n".join(results_sections)

    prompt = f"""You are an expert data analyst creating a comprehensive database intelligence report.

DATABASE: {db_name}
SQL DIALECT: {dialect_name}

TABLE STATISTICS:
{stats_str}

The following analytical queries were executed against the database. Analyze ALL results together and produce a cohesive report.

{all_results}

Return ONLY a raw JSON object with this structure:
{{
    "executive_summary": "A comprehensive 3-5 paragraph executive summary in Markdown. Cover: what the database is about, key metrics and totals, most important findings across all queries, notable patterns or anomalies, and actionable recommendations.",
    "insights": [
        {{
            "title": "Insight title matching the query",
            "markdown": "2-3 paragraph analysis of this specific result in Markdown. Include key numbers, comparisons, and what this means for the business.",
            "chart": {{
                "type": "bar",
                "title": "Chart title",
                "labels": ["Label1", "Label2"],
                "datasets": [
                    {{
                        "label": "Dataset Label",
                        "data": [10, 20]
                    }}
                ]
            }}
        }}
    ]
}}

RULES:
- Generate one insight per successfully executed query (skip errored queries)
- "chart.type" must be one of: "pie", "bar", "line", "doughnut", "area", "scatter"
- Chart labels and data must come from the ACTUAL query results shown above
- Keep chart labels short (truncate long strings to ~20 chars)
- For pie/doughnut charts, limit to top 10 categories max (group rest as "Other")
- Make the executive_summary synthesize findings ACROSS all queries, not just repeat them
"""

    try:
        response = GROQ_CLIENT.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a database intelligence report generator that outputs strict JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        result_text = response.choices[0].message.content.strip()
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
        parsed = json.loads(result_text)

        # Attach the original SQL to each insight
        insights = parsed.get("insights", [])
        for i, insight in enumerate(insights):
            if i < len(query_results):
                insight["sql"] = query_results[i].get("sql", "")

        return parsed
    except Exception as e:
        return {"error": f"Report generation failed: {str(e)}"}


# ---------------------------------------------------
# Full Database Analysis — Background Pipeline
# ---------------------------------------------------
def _update_job(job_id, **kwargs):
    with _jobs_lock:
        if job_id in _analysis_jobs:
            _analysis_jobs[job_id].update(kwargs)


def _gc_old_jobs():
    """Remove jobs older than 10 minutes."""
    cutoff = time.time() - 600
    with _jobs_lock:
        stale = [jid for jid, j in _analysis_jobs.items() if j.get("created_at", 0) < cutoff]
        for jid in stale:
            del _analysis_jobs[jid]


def get_job_status(job_id: str) -> dict:
    with _jobs_lock:
        job = _analysis_jobs.get(job_id)
        if not job:
            return {"status": "not_found", "error": "Job not found or expired."}
        return {
            "status": job["status"],
            "progress": job.get("progress", ""),
            "step": job.get("step", 0),
            "total_steps": job.get("total_steps", 0),
            "result": job.get("result"),
        }


def _ensure_limit(sql: str, limit: int = 500) -> str:
    """Inject LIMIT clause if missing from a SQL query."""
    sql_lower = sql.strip().lower()
    if "limit" not in sql_lower:
        sql = sql.rstrip(";") + f" LIMIT {limit}"
    return sql


def run_full_analysis_pipeline(job_id: str, connection_name: str, dialect: str):
    """
    Background pipeline: collect schema → generate queries → execute → generate report.
    Updates _analysis_jobs[job_id] with progress at each step.
    """
    from core.connection_manager import get_adapter_for_connection
    from core.validator import classify_query, is_safe

    try:
        # Step 1: Collect schema
        _update_job(job_id, status="collecting_schema", progress="Collecting database schema...", step=1)
        adapter = get_adapter_for_connection(connection_name)
        schema = adapter.get_schema()
        tables = adapter.list_tables()

        if not tables:
            _update_job(job_id, status="error", result={"error": "Database has no tables to analyze."})
            return

        # Collect row counts
        table_stats = []
        for t in tables:
            try:
                _, count_rows = adapter.execute(f'SELECT COUNT(*) FROM "{t}"')
                count = count_rows[0][0] if count_rows else 0
            except Exception:
                count = 0
            table_stats.append({"table": t, "rows": count})

        # Collect FK info
        fk_info = []
        try:
            fk_info = adapter.get_foreign_keys()
        except Exception:
            pass

        # Step 2: Generate queries
        _update_job(job_id, status="generating_queries", progress="AI is generating analytical queries...", step=2)
        gen_result = generate_analytical_queries(schema, connection_name, table_stats, fk_info, dialect)

        if "error" in gen_result:
            _update_job(job_id, status="error", result=gen_result)
            return

        queries = gen_result.get("queries", [])
        if not queries:
            _update_job(job_id, status="error", result={"error": "AI generated no queries."})
            return

        total_steps = 2 + len(queries) + 1  # schema + gen + N executions + report
        _update_job(job_id, total_steps=total_steps)

        # Step 3..N: Execute queries
        query_results = []
        executor = ThreadPoolExecutor(max_workers=1)

        for i, q in enumerate(queries):
            step_num = 3 + i
            title = q.get("title", f"Query {i+1}")
            sql = q.get("sql", "")
            _update_job(job_id, status="executing_query",
                        progress=f"Running query {i+1}/{len(queries)}: {title}",
                        step=step_num)

            result_entry = {"title": title, "sql": sql, "columns": None, "rows": None, "error": None}

            # Safety validation
            task_type = classify_query(sql, dialect)
            if task_type != "READ":
                result_entry["error"] = f"Skipped — not a read query (classified as {task_type})"
                query_results.append(result_entry)
                continue

            if not is_safe(sql, dialect):
                result_entry["error"] = "Skipped — query flagged as unsafe"
                query_results.append(result_entry)
                continue

            # Ensure LIMIT
            if dialect not in ("mongodb", "redis"):
                sql = _ensure_limit(sql)
                result_entry["sql"] = sql

            # Execute with timeout
            try:
                future = executor.submit(adapter.execute, sql)
                columns, rows = future.result(timeout=30)
                # Convert rows to plain lists
                result_entry["columns"] = columns
                result_entry["rows"] = [list(r) if isinstance(r, (list, tuple)) else [r] for r in rows]
            except FuturesTimeoutError:
                result_entry["error"] = "Query timed out (>30s)"
            except Exception as e:
                result_entry["error"] = str(e)

            query_results.append(result_entry)

        executor.shutdown(wait=False)

        # Check if any queries succeeded
        successful = [qr for qr in query_results if not qr.get("error")]
        if not successful:
            # Still try to generate a schema-only report
            pass

        # Step N+1: Generate report
        report_step = 3 + len(queries)
        _update_job(job_id, status="generating_report",
                    progress="AI is generating the full report...",
                    step=report_step)

        report = generate_full_report(schema, connection_name, table_stats, fk_info, query_results, dialect)

        if "error" in report:
            _update_job(job_id, status="error", result=report)
            return

        _update_job(job_id, status="complete", step=total_steps, progress="Analysis complete!", result=report)

    except Exception as e:
        _update_job(job_id, status="error", result={"error": f"Pipeline failed: {str(e)}"})


def start_full_analysis(connection_name: str, dialect: str) -> str:
    """
    Creates a job and starts the full analysis pipeline in a background thread.
    Returns the job_id.
    """
    _gc_old_jobs()
    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _analysis_jobs[job_id] = {
            "status": "starting",
            "progress": "Initializing...",
            "step": 0,
            "total_steps": 4,  # Will be updated once query count is known
            "result": None,
            "created_at": time.time(),
        }
    thread = threading.Thread(target=run_full_analysis_pipeline, args=(job_id, connection_name, dialect), daemon=True)
    thread.start()
    return job_id
