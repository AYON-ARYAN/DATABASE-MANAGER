import json
import os
import requests

LLM_CONFIG_FILE = "db/llm_config.json"

DEFAULT_CONFIG = {
    "active_provider": "mistral", # mistral (ollama) or groq
    "providers": {
        "groq": {
            "api_key": os.getenv("GROQ_API_KEY", ""),
            "model": "llama-3.3-70b-versatile",
            "url": "https://api.groq.com/openai/v1/chat/completions"
        },
        "mistral": {
            "model": "mistral",
            "url": "http://localhost:11434/api/generate"
        }
    }
}

def load_config():
    if not os.path.exists(LLM_CONFIG_FILE):
        return DEFAULT_CONFIG
    try:
        with open(LLM_CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_CONFIG

def save_config(config):
    os.makedirs(os.path.dirname(LLM_CONFIG_FILE), exist_ok=True)
    with open(LLM_CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

def get_active_config():
    config = load_config()
    provider = config["active_provider"]
    return provider, config["providers"].get(provider, {})

# Ollama Specific
def list_local_models():
    try:
        res = requests.get("http://localhost:11434/api/tags", timeout=5)
        if res.ok:
            return res.json().get("models", [])
    except Exception:
        pass
    return []

def pull_ollama_model(model_name):
    # This is a streaming response typically, but for simplicity we'll just trigger it
    try:
        res = requests.post("http://localhost:11434/api/pull", json={"name": model_name, "stream": False}, timeout=300)
        return res.ok
    except Exception:
        return False
