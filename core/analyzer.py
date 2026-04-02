import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Initialize Groq client
# This requires GROQ_API_KEY environment variable to be set
try:
    GROQ_CLIENT = Groq(api_key=os.environ.get("GROQ_API_KEY"))
except Exception:
    GROQ_CLIENT = None


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


def ai_ask(question: str, schema: str, db_name: str, table_stats: list = None) -> dict:
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

    prompt = f"""You are an expert DBMS teaching assistant and database analyst.
You have full access to the following database schema.

DATABASE: {db_name}

SCHEMA:
{schema}
{stats_str}

USER QUESTION: {question}

INSTRUCTIONS:
- Answer the question thoroughly and helpfully
- If the question is about SQL concepts (JOINs, normalization, indexes, etc.), explain with examples from THIS database
- If the question is about the data, suggest specific SQL queries they can run
- If they ask "what can I do" or "help", give a comprehensive overview of the database and suggest interesting queries
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
                {"role": "system", "content": "You are a helpful DBMS teaching assistant. You explain database concepts clearly and provide practical SQL examples from the user's actual database."},
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


def get_table_overview(schema: str, db_name: str, table_stats: list) -> dict:
    """
    Generates a complete database overview with charts data for the overview dashboard.
    Returns {"summary": "...", "charts": [...]}
    """
    if not GROQ_CLIENT:
        return {"error": "Groq API key not configured."}

    stats_str = "\n".join([f"  - {ts['table']}: {ts['rows']} rows" for ts in table_stats])

    prompt = f"""You are a database analytics engine. Analyze this database and return a JSON overview report.

DATABASE: {db_name}

SCHEMA:
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

RULES:
- All SQL must be valid for the actual schema shown above
- Use real table and column names from the schema
- suggested_queries should be 4-6 interesting analytical queries
- table_size_chart should include ALL tables sorted by size
- relationship_map should include ALL foreign key relationships
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
