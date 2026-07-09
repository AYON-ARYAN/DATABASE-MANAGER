import json
import os
import requests

from core.paths import db_path

LLM_CONFIG_FILE = db_path("llm_config.json")

# Provider endpoints are env-overridable so tests can point the app at a
# Specmatic stub (service virtualization) instead of the real Groq/Ollama.
# In production these env vars are unset, so the real endpoints are used.
GROQ_URL = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")
OLLAMA_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate")

DEFAULT_CONFIG = {
    "active_provider": "mistral", # mistral (ollama) or groq
    "providers": {
        "groq": {
            "api_key": os.getenv("GROQ_API_KEY", ""),
            "model": "llama-3.3-70b-versatile",
            "url": GROQ_URL
        },
        "mistral": {
            "model": "mistral",
            "url": OLLAMA_URL
        }
    }
}

def _apply_env_overrides(config):
    """Let GROQ_API_URL / OLLAMA_API_URL / GROQ_API_KEY override config at runtime.
    Enables pointing the LLM calls at a Specmatic stub during tests."""
    try:
        providers = config.setdefault("providers", {})
        if os.getenv("GROQ_API_URL"):
            providers.setdefault("groq", {})["url"] = os.getenv("GROQ_API_URL")
        if os.getenv("GROQ_API_KEY"):
            providers.setdefault("groq", {})["api_key"] = os.getenv("GROQ_API_KEY")
        if os.getenv("OLLAMA_API_URL"):
            providers.setdefault("mistral", {})["url"] = os.getenv("OLLAMA_API_URL")
    except Exception:
        pass
    return config

def load_config():
    if not os.path.exists(LLM_CONFIG_FILE):
        return _apply_env_overrides(json.loads(json.dumps(DEFAULT_CONFIG)))
    try:
        with open(LLM_CONFIG_FILE, "r") as f:
            return _apply_env_overrides(json.load(f))
    except Exception:
        return _apply_env_overrides(json.loads(json.dumps(DEFAULT_CONFIG)))

def save_config(config):
    LLM_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
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
