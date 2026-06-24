#!/usr/bin/env python3
"""Tiny Gemini helper: reads a prompt from stdin, prints model text to stdout.
Usage: echo "prompt" | python3 gemini.py [model]
Default model: gemini-2.5-pro
"""
import os, sys, json, urllib.request

API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
if not API_KEY:
    sys.stderr.write("GEMINI ERROR: set GEMINI_API_KEY (or GOOGLE_API_KEY) in your environment\n")
    sys.exit(1)
model = sys.argv[1] if len(sys.argv) > 1 else "gemini-2.5-pro"
prompt = sys.stdin.read()

url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={API_KEY}"
body = {
    "contents": [{"parts": [{"text": prompt}]}],
    "generationConfig": {"temperature": 0.4, "maxOutputTokens": 8192},
}
req = urllib.request.Request(url, data=json.dumps(body).encode(),
                            headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read())
    parts = data["candidates"][0]["content"]["parts"]
    print("".join(p.get("text", "") for p in parts))
except Exception as e:
    sys.stderr.write(f"GEMINI ERROR: {e}\n")
    sys.exit(1)
