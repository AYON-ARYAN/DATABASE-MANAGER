#!/usr/bin/env python3
"""Cross-platform launcher for the Specmatic-testing app instance.

The README's testing command sets env vars with `VAR=value command` shell
syntax (`API_BEARER_TOKEN=... ENABLE_ACTUATOR=1 ... python -m flask ...`).
That only works on bash/zsh — on Windows cmd.exe or PowerShell it silently
does nothing, so ENABLE_ACTUATOR/API_BEARER_TOKEN never reach the process.
Symptom: Specmatic reports "Actuator Not Available" and every bearer-gated
endpoint (e.g. /api/execute, /api/undo) 401s instead of returning its real
status — found by reproducing exactly this locally after Saachi reported it.

This script sets the same env vars in Python instead, so it behaves
identically on every OS/shell.

Run:
    python scripts/run_for_specmatic_testing.py
Then, in another terminal, the `specmatic test ...` commands from the README.
Override any default by setting the real env var before running this script
(os.environ.setdefault below only fills in what isn't already set).
"""
import os
import sys

os.environ.setdefault("API_BEARER_TOKEN", "specmatic-ci-token")
os.environ.setdefault("ENABLE_ACTUATOR", "1")
os.environ.setdefault("GROQ_API_URL", "http://localhost:9090/openai/v1/chat/completions")
os.environ.setdefault("GROQ_API_KEY", "ci-stub-key")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app  # noqa: E402  (import after env vars are set, matches app.py's own style)

if __name__ == "__main__":
    port = int(os.environ.get("TEST_APP_PORT", "5001"))
    app.run(port=port)
