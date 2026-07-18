#!/usr/bin/env python3
"""Fault-injection test for core/llm.py — proves the app fails CLEANLY when the
LLM provider returns empty or malformed responses, instead of treating the
failure text as a generated query (the bug Naresh Jain flagged after the
founder-round call: "LLM can give empty response, please take a look").

Runs a tiny local HTTP server that serves deliberately broken response bodies
on demand, points GROQ_API_URL/OLLAMA_API_URL at it, and calls
core.llm.generate_query() directly for each broken-response case. No real LLM
call, no Specmatic — this isolates and exercises the app's own handling code.

Run:
    python scripts/llm_fault_injection_test.py
"""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CASES = [
    ("empty_choices", json.dumps({
        "id": "x", "object": "chat.completion", "model": "m",
        "choices": [],
        "usage": {"prompt_tokens": 1, "completion_tokens": 0, "total_tokens": 1},
    }).encode()),
    ("blank_content", json.dumps({
        "id": "x", "object": "chat.completion", "model": "m",
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant", "content": "   "}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 0, "total_tokens": 1},
    }).encode()),
    ("malformed_json", b"{not valid json"),
    ("missing_choices_key", json.dumps({
        "id": "x", "object": "chat.completion", "model": "m",
    }).encode()),
]

_current = {"body": b"{}"}


class FaultHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(_current["body"])

    def log_message(self, *args):
        pass


def run_case(name, body):
    _current["body"] = body
    from core import llm
    result = llm.generate_query(
        user_command="show all albums",
        dialect="sqlite",
        schema="TABLE Album(AlbumId, Title, ArtistId)",
        provider="groq",
    )
    if result is not None:
        print(f"FAIL [{name}]: expected None (clean failure), got {result!r}")
        return False
    print(f"PASS [{name}]: provider failure returned None, not treated as a query")
    return True


def main():
    server = HTTPServer(("localhost", 9091), FaultHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    os.environ["GROQ_API_URL"] = "http://localhost:9091/openai/v1/chat/completions"
    os.environ["GROQ_API_KEY"] = "fault-injection-key"
    # Point Ollama at the same broken server too, so BOTH providers in the
    # fallback chain fail for every case (proves the total-failure path, not
    # just one provider's retry-the-other-one behavior).
    os.environ["OLLAMA_API_URL"] = "http://localhost:9091/api/generate"

    results = [run_case(name, body) for name, body in CASES]
    server.shutdown()

    passed = sum(results)
    print(f"\n{passed}/{len(results)} fault-injection cases degraded cleanly.")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
