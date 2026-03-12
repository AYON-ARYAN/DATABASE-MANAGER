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
- "type" MUST be one of: "pie", "bar", "line", "doughnut"
- "labels" should be an array of strings (e.g., categories, dates)
- "data" should be an array of numbers corresponding to the labels
- Choose the chart type that best represents the data (e.g., pie/doughnut for parts of a whole, bar for comparisons, line for trends)
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
