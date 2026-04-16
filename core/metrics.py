import json
import os
import time
from datetime import datetime

METRICS_FILE = "db/usage_metrics.json"

def log_call(provider, model, latency, prompt_tokens=0, completion_tokens=0):
    """Logs an LLM call to the persistent metrics file."""
    os.makedirs(os.path.dirname(METRICS_FILE), exist_ok=True)
    
    metrics = []
    if os.path.exists(METRICS_FILE):
        try:
            with open(METRICS_FILE, "r") as f:
                metrics = json.load(f)
        except (json.JSONDecodeError, IOError):
            metrics = []

    entry = {
        "timestamp": datetime.now().isoformat(),
        "provider": provider,
        "model": model,
        "latency": round(latency, 3),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens
    }
    
    metrics.append(entry)
    
    # Keep last 1000 entries for performance
    if len(metrics) > 1000:
        metrics = metrics[-1000:]
        
    with open(METRICS_FILE, "w") as f:
        json.dump(metrics, f, indent=2)

def get_summary():
    """Returns a summary of usage for the admin dashboard."""
    if not os.path.exists(METRICS_FILE):
        return {"total_calls": 0, "avg_latency": 0, "total_tokens": 0, "calls_by_provider": {}, "trends": {}}
    
    try:
        with open(METRICS_FILE, "r") as f:
            metrics = json.load(f)
    except Exception:
        return {"total_calls": 0, "avg_latency": 0, "total_tokens": 0, "calls_by_provider": {}, "trends": {}}
    
    if not metrics:
        return {"total_calls": 0, "avg_latency": 0, "total_tokens": 0, "calls_by_provider": {}, "trends": {}}
    
    total_calls = len(metrics)
    total_latency = sum(m.get("latency", 0) for m in metrics)
    total_tokens = sum(m.get("total_tokens", 0) for m in metrics)
    
    by_provider = {}
    for m in metrics:
        p = m.get("provider", "unknown")
        by_provider[p] = by_provider.get(p, 0) + 1
        
    # Build Trends (last 50 calls)
    recent = metrics[-50:]
    trends = {
        "labels": [m["timestamp"][11:19] for m in recent],
        "groq_tokens": [m["total_tokens"] if m["provider"] == "groq" else 0 for m in recent],
        "mistral_tokens": [m["total_tokens"] if m["provider"] == "mistral" else 0 for m in recent],
        "groq_latency": [m["latency"] if m["provider"] == "groq" else 0 for m in recent],
        "mistral_latency": [m["latency"] if m["provider"] == "mistral" else 0 for m in recent]
    }
        
    return {
        "total_calls": total_calls,
        "avg_latency": round(total_latency / total_calls, 3),
        "total_tokens": total_tokens,
        "calls_by_provider": by_provider,
        "trends": trends,
        "recent_history": metrics[-20:]
    }
