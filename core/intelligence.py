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
        from core.llm import GROQ_API_KEY, GROQ_URL
        
        if self.llm_provider == "groq" and GROQ_API_KEY:
            # GROQ Implementation
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            data = {
                "model": "mixtral-8x7b-32768",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "response_format": {"type": "json_object"}
            }
            try:
                response = requests.post(GROQ_URL, headers=headers, json=data, timeout=10)
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
            {"intent": "List all tables", "task": "SYSTEM", "desc": "Explore database structure"},
            {"intent": "Show me the top 10 users", "task": "READ", "desc": "Standard data retrieval"},
            {"intent": "Add a new record to products", "task": "WRITE", "desc": "Data modification"},
            {"intent": "Remove table 'old_data'", "task": "SCHEMA", "desc": "Structural changes (DANGER)"},
        ]
