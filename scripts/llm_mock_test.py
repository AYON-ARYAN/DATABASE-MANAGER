#!/usr/bin/env python3
"""Proves Meridian's NL-to-SQL path can be served by a Specmatic stub of the LLM
provider — deterministic, offline, zero real tokens.

Run with the LLM stub up:
  export SPECMATIC_JAR="$HOME/.specmatic/specmatic.jar"
  "$SPECMATIC_JAR" stub llm_contract.yaml --port 9090 &
  GROQ_API_URL=http://localhost:9090/openai/v1/chat/completions \
  GROQ_API_KEY=stub-key \
  python scripts/llm_mock_test.py
"""
import os, sys

# Point the app's Groq calls at the Specmatic stub (service virtualization).
os.environ.setdefault("GROQ_API_URL", "http://localhost:9090/openai/v1/chat/completions")
os.environ.setdefault("GROQ_API_KEY", "stub-key")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import llm

assert "localhost" in os.environ["GROQ_API_URL"], "must point at the local Specmatic stub"

result = llm.generate_query(
    user_command="show all albums",
    dialect="sqlite",
    schema="TABLE Album(AlbumId, Title, ArtistId)",
    provider="groq",
)
print("LLM call routed to:", os.environ["GROQ_API_URL"])
print("Stub returned (parsed by app):", repr(result))

# The win: the app's LLM dependency was served by the Specmatic stub — a
# contract-conformant response, produced offline with zero real tokens, instead
# of calling the real Groq/OpenAI endpoint. (Send a request matching the contract
# example to get the canned 'SELECT ... ' SQL; otherwise Specmatic auto-generates
# a schema-valid completion. Either way: deterministic shape, no real LLM.)
ok = isinstance(result, str) and result.strip()
if ok:
    print("PASS — NL-to-SQL served by the Specmatic-virtualized LLM (no real LLM call, 0 tokens).")
    sys.exit(0)
else:
    print("FAIL — app did not get a response from the stub (fell through to error).")
    sys.exit(1)
