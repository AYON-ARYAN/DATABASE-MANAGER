"""
Command Intelligence Module
Provides semantic understanding of user intents and command categorization.
"""

import json
from core.llm_manager import load_config
import requests # Fallback if direct LLM call is needed

class CommandIntelligence:
    def __init__(self, llm_provider="mistral"):
        self.llm_provider = llm_provider

    def explain_intent(self, user_cmd, dialect="sqlite"):
        """
        Uses the LLM to explain the semantic meaning, task type, and 
        permission requirements for a natural language command.
        """
        prompt = f"""
        Analyze the following data command intent: "{user_cmd}"
        Database Dialect: {dialect}

        Provide a JSON response with:
        1. "summary": A 1-sentence explanation of what this command will do.
        2. "task": The technical category (READ, WRITE, SCHEMA, or SYSTEM).
        3. "impact": "LOW", "MEDIUM", or "HIGH" risk.
        4. "permissions": Which user roles (VIEWER, EDITOR, ADMIN) should have access?
        5. "sql_pattern": A generic example of the SQL it might generate.

        Output ONLY pure JSON.
        """
        
        # Use existing LLM generation logic
        from core.llm import GROQ_API_KEY, GROQ_API_URL

        if self.llm_provider == "groq" and GROQ_API_KEY:
            # GROQ Implementation
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            data = {
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "response_format": {"type": "json_object"}
            }
            try:
                response = requests.post(GROQ_API_URL, headers=headers, json=data, timeout=10)
                res_json = response.json()
                content = res_json['choices'][0]['message']['content']
                return json.loads(content)
            except Exception as e:
                return {"error": f"Intelligence lookup failed: {str(e)}"}
        else:
            # Ollama / Mistral Implementation (Local)
            try:
                # Assuming Ollama is running locally
                data = {
                    "model": "mistral",
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                }
                response = requests.post("http://localhost:11434/api/generate", json=data, timeout=15)
                res_json = response.json()
                return json.loads(res_json["response"])
            except Exception as e:
                return {
                    "summary": f"Categorized as a {dialect} operation.",
                    "task": "UNKNOWN",
                    "impact": "MEDIUM",
                    "permissions": "ADMIN",
                    "sql_pattern": "N/A"
                }

    def get_canonical_commands(self):
        """Returns a list of common command patterns for the guide."""
        return [
            # Hardcoded commands (bypass LLM - always work)
            {"intent": "show tables", "task": "SYSTEM", "desc": "List all tables in the database (hardcoded - no LLM needed)"},
            {"intent": "describe <table_name>", "task": "SYSTEM", "desc": "Show columns, types, PKs, FKs, and indexes for a table (hardcoded)"},
            {"intent": "show foreign keys", "task": "SYSTEM", "desc": "List all foreign key relationships across all tables (hardcoded)"},
            {"intent": "show foreign keys for <table>", "task": "SYSTEM", "desc": "Show FK relationships for a specific table (hardcoded)"},
            {"intent": "show indexes", "task": "SYSTEM", "desc": "List all indexes across all tables (hardcoded)"},
            {"intent": "show constraints", "task": "SYSTEM", "desc": "Show all PKs, FKs, NOT NULLs, and UNIQUE constraints (hardcoded)"},
            {"intent": "show table counts", "task": "SYSTEM", "desc": "Show row count for every table (hardcoded)"},
            {"intent": "show create table <name>", "task": "SYSTEM", "desc": "Show the DDL/CREATE TABLE statement (hardcoded)"},
            # AI-powered commands
            {"intent": "Show me the top 10 customers", "task": "READ", "desc": "AI generates SELECT with LIMIT (uses LLM)"},
            {"intent": "Join orders with customers", "task": "READ", "desc": "AI generates JOIN query using FK relationships (uses LLM)"},
            {"intent": "Count records grouped by category", "task": "READ", "desc": "AI generates GROUP BY with COUNT (uses LLM)"},
            {"intent": "Find duplicate emails", "task": "READ", "desc": "AI generates GROUP BY + HAVING COUNT > 1 (uses LLM)"},
            {"intent": "Add a new record to products", "task": "WRITE", "desc": "AI generates INSERT statement - requires review (uses LLM)"},
            {"intent": "Update prices by 10%", "task": "WRITE", "desc": "AI generates UPDATE statement - requires review (uses LLM)"},
        ]
