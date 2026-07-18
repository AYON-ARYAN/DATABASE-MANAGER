# Founder-Round Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the four issues Naresh Jain flagged after the founder-round call: LLM responses that fail silently instead of erroring cleanly, actuator invisible on a normal run, contract coverage limited to 6 of 52 `/api` endpoints, and a local setup that requires running backend/frontend/LLM separately.

**Architecture:** Four independent-ish workstreams against the existing `DATABASE-MANAGER` Flask + React app at `/Volumes/BLACK_SHARK/MINOR_PROJECT` (branch `react_build`). No new frameworks — Flask stays Flask, existing Specmatic contract-testing setup is extended rather than replaced, existing Ollama support in `core/llm_manager.py` (already the default provider) is exposed via Docker rather than rebuilt.

**Tech Stack:** Python 3.11 (Flask, requests), Specmatic (contract testing), Docker Compose, Ollama.

## Global Constraints

- No new Python dependencies (no PyYAML — generate YAML via plain string templates, matching how `api_contract.yaml`/`contract_public.yaml` are already hand-maintained as plain text).
- No framework migration — Flask stays Flask.
- No retry/backoff logic for LLM calls — fail-clean only, matching the approved spec's explicit out-of-scope note.
- Every verification step must be run against the actually-running app/stack, not asserted from reading code.
- Task 1 and Task 2 both modify `app.py` in different regions — run them **sequentially**, Task 1 first, each committed before the next starts. Task 3 and Task 4 are independent of 1, 2, and each other, and can run in parallel or any order.

---

### Task 1: LLM resilience — fail clean instead of leaking a fake query

**Files:**
- Modify: `core/llm.py:210-296` (`_call_groq`, `_call_ollama`, `generate_query`)
- Modify: `core/llm.py:299-363` (`generate_query_with_explanation`)
- Modify: `app.py:637-638` (first call site, in `index()`)
- Modify: `app.py:951-953` (second call site, in `refine_query()`)
- Modify: `api_routes.py:369-371` (third call site)
- Modify: `scripts/llm_mock_test.py:37` (dead-code cleanup — the string it checks for no longer exists)
- Create: `scripts/llm_fault_injection_test.py`

**Interfaces:**
- Produces: `generate_query(...) -> str | None` (was `str`, always non-None even on total failure — now `None` signals "every provider failed or returned unusable output").
- Produces: `generate_query_with_explanation(...) -> tuple[str | None, str]` — when generation fails, returns `(None, "<user-facing explanation>")` instead of attempting to parse the failure text as `QUERY:`/`EXPLANATION:`.
- Consumes (by app.py/api_routes.py call sites): must branch on `if query is None:` immediately after calling `generate_query_with_explanation`, before passing `query` to `classify_query()`/`is_safe()`.

- [ ] **Step 1: Read the current call sites to confirm exact line numbers before editing**

Run: `grep -n "generate_query_with_explanation(" app.py api_routes.py`
Expected output (three matches):
```
app.py:637:        query, explanation = generate_query_with_explanation(
app.py:951:        new_sql, explanation = generate_query_with_explanation(
api_routes.py:369:    query, explanation = generate_query_with_explanation(
```
If line numbers differ from this plan, use the actual ones — the surrounding code shown in each step below is what to search for, not the line number.

- [ ] **Step 2: Write the fault-injection script FIRST, confirm it fails against the current (unpatched) code**

Create `scripts/llm_fault_injection_test.py`:

```python
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
```

- [ ] **Step 3: Run it against the CURRENT (unpatched) code to confirm it fails**

Run: `cd /Volumes/BLACK_SHARK/MINOR_PROJECT && ./venv/bin/python scripts/llm_fault_injection_test.py`
Expected: every case prints `FAIL [...]: expected None (clean failure), got 'ERROR: all providers failed (...)'` and the script exits with code 1. This confirms the bug is real before fixing it.

- [ ] **Step 4: Fix `_call_groq` and `_call_ollama` to validate response shape**

In `core/llm.py`, replace the body of `_call_groq` (currently ends with `return clean_sql(data["choices"][0]["message"]["content"])`):

```python
def _call_groq(context, history, user_command, p_config):
    """Try Groq. Returns cleaned SQL string on success, raises on failure
    (including an empty/malformed response — never returns silently-bad output)."""
    api_key = p_config.get("api_key")
    model = p_config.get("model", "llama-3.3-70b-versatile")
    url = p_config.get("url", GROQ_API_URL)
    if not api_key:
        raise RuntimeError("No GROQ_API_KEY configured")

    messages = [{"role": "system", "content": context}]
    for msg in history or []:
        messages.append({"role": "user", "content": msg["user"]})
        messages.append({"role": "assistant", "content": msg["assistant"]})
    messages.append({"role": "user", "content": f"USER COMMAND:\n{user_command}"})

    start = time.time()
    res = requests.post(url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "messages": messages, "temperature": 0.1},
        timeout=60)
    res.raise_for_status()
    data = res.json()
    choices = data.get("choices")
    if not choices:
        raise ValueError("Groq response had no choices")
    content = (choices[0].get("message") or {}).get("content", "")
    if not content or not content.strip():
        raise ValueError("Groq response had empty content")
    usage = data.get("usage", {})
    log_call("groq", data.get("model", model), time.time() - start,
             usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
    return clean_sql(content)
```

Replace the body of `_call_ollama` (currently ends with `return clean_sql(data["response"])`):

```python
def _call_ollama(full_prompt, p_config, options=None):
    """Try Ollama. Returns cleaned SQL string on success, raises on failure
    (including an empty/malformed response — never returns silently-bad output)."""
    ollama_url = p_config.get("url", OLLAMA_URL)
    ollama_model = p_config.get("model", "mistral")
    default_options = {"num_thread": 4, "num_ctx": 2048, "temperature": 0.1}
    if options:
        default_options.update(options)

    start = time.time()
    res = requests.post(ollama_url,
        json={"model": ollama_model, "prompt": full_prompt,
              "stream": False, "options": default_options},
        timeout=60)
    res.raise_for_status()
    data = res.json()
    content = data.get("response", "")
    if not content or not content.strip():
        raise ValueError("Ollama response was empty")
    log_call("mistral", ollama_model, time.time() - start,
             data.get("prompt_eval_count", 0), data.get("eval_count", 0))
    return clean_sql(content)
```

- [ ] **Step 5: Change `generate_query`'s total-failure return from a fake-looking string to `None`**

In `core/llm.py`, find the end of `generate_query`:
```python
    return f"ERROR: all providers failed ({'; '.join(errors)})"
```
Replace with:
```python
    print(f"[LLM] all providers failed — {'; '.join(errors)}")
    return None
```
(The per-provider `print(f"[LLM] {name} failed — {e}")` inside the loop stays as-is — this new line just also logs the combined failure once, since the old return string previously carried that summary for anyone reading the response; now the response is `None` so the summary has to go to the log instead.)

- [ ] **Step 6: Update `generate_query_with_explanation` to short-circuit on `None`**

In `core/llm.py`, find:
```python
    # 1. Get raw merged response
    raw_response = generate_query(
        user_command="", # We embed the command in system_prompt for precision
        dialect=dialect,
        schema=schema,
        provider=provider,
        history=history,
        system_prompt=merged_prompt,
        options={"num_predict": 512} # Limit length to save resources
    )

    # 2. Parse results
    query = ""
    explanation = "No explanation generated."
```
Replace with:
```python
    # 1. Get raw merged response
    raw_response = generate_query(
        user_command="", # We embed the command in system_prompt for precision
        dialect=dialect,
        schema=schema,
        provider=provider,
        history=history,
        system_prompt=merged_prompt,
        options={"num_predict": 512} # Limit length to save resources
    )

    if raw_response is None:
        return None, "Could not generate a query — the AI provider(s) returned no usable response. Please try again or rephrase."

    # 2. Parse results
    query = ""
    explanation = "No explanation generated."
```

- [ ] **Step 7: Rerun the fault-injection script — confirm it now passes**

Run: `cd /Volumes/BLACK_SHARK/MINOR_PROJECT && ./venv/bin/python scripts/llm_fault_injection_test.py`
Expected: all four cases print `PASS [...]` and the script exits 0 with `4/4 fault-injection cases degraded cleanly.`

- [ ] **Step 8: Update the three call sites to handle `query is None`**

In `app.py`, find (inside `index()`):
```python
        query, explanation = generate_query_with_explanation(
            user_cmd, dialect, schema, llm_provider, history=conversation_context
        )
        
        # Update context (last 5 - pruned for performance)
```
Replace with:
```python
        query, explanation = generate_query_with_explanation(
            user_cmd, dialect, schema, llm_provider, history=conversation_context
        )

        if query is None:
            return render_template(
                "index.html",
                error=explanation,
                history=session.get("history", []),
                db_info=db_info,
                connections=connections,
                llm_provider=llm_provider,
                analysis_enabled=analysis_enabled,
            )

        # Update context (last 5 - pruned for performance)
```

In `app.py`, find (inside `refine_query()`):
```python
        new_sql, explanation = generate_query_with_explanation(
            refine_prompt, dialect, schema, llm_provider, 
            history=session.get("conversation_context", []),
            system_prompt="""- Use ONLY tables and columns shown above
- Output ONLY valid SQL for the current database engine
- NEVER output plain text, lists, or conversational responses.
- Even if you know the answer from the schema, GENERATE THE SQL to fetch it.
- For SELECT queries: always include LIMIT 50 unless user specifies otherwise
- No markdown, no explanation, no code fences
"""
        )
        
        # Update session with new query for potential execution
```
Replace with:
```python
        new_sql, explanation = generate_query_with_explanation(
            refine_prompt, dialect, schema, llm_provider, 
            history=session.get("conversation_context", []),
            system_prompt="""- Use ONLY tables and columns shown above
- Output ONLY valid SQL for the current database engine
- NEVER output plain text, lists, or conversational responses.
- Even if you know the answer from the schema, GENERATE THE SQL to fetch it.
- For SELECT queries: always include LIMIT 50 unless user specifies otherwise
- No markdown, no explanation, no code fences
"""
        )

        if new_sql is None:
            return jsonify({"success": False, "error": explanation})

        # Update session with new query for potential execution
```

In `api_routes.py`, find:
```python
    query, explanation = generate_query_with_explanation(
        user_cmd, dialect, schema, llm_provider, history=conversation_context
    )

    conversation_context.append({"user": user_cmd, "assistant": query})
```
Replace with:
```python
    query, explanation = generate_query_with_explanation(
        user_cmd, dialect, schema, llm_provider, history=conversation_context
    )

    if query is None:
        return jsonify({"error": explanation})

    conversation_context.append({"user": user_cmd, "assistant": query})
```

- [ ] **Step 9: Clean up the now-dead string check in the existing mock test**

In `scripts/llm_mock_test.py`, find:
```python
ok = isinstance(result, str) and result.strip() and not result.startswith("ERROR: all providers failed")
```
Replace with:
```python
ok = isinstance(result, str) and result.strip()
```
(The old check was defending against the "ERROR: all providers failed" string, which no longer exists — `generate_query` now returns `None` on total failure, which already fails `isinstance(result, str)`.)

- [ ] **Step 10: Live-verify the happy path still works, then verify the clean-failure path through the real app**

Ensure the LLM stub and app are running in testing mode (reuse the pattern already established this session: stub on :9090, app on :5001 with `API_BEARER_TOKEN`/`ENABLE_ACTUATOR`/`GROQ_API_URL`/`GROQ_API_KEY` set). Then:

```bash
cd /Volumes/BLACK_SHARK/MINOR_PROJECT && ./venv/bin/python scripts/llm_mock_test.py
```
Expected: `PASS — NL-to-SQL served by the Specmatic-virtualized LLM (no real LLM call, 0 tokens).`

```bash
cd /Volumes/BLACK_SHARK/MINOR_PROJECT && ./venv/bin/python scripts/llm_fault_injection_test.py
```
Expected: `4/4 fault-injection cases degraded cleanly.`

- [ ] **Step 11: Commit**

```bash
cd /Volumes/BLACK_SHARK/MINOR_PROJECT
git add core/llm.py app.py api_routes.py scripts/llm_mock_test.py scripts/llm_fault_injection_test.py
git commit -m "$(cat <<'EOF'
Fail clean on empty/malformed LLM responses instead of executing the failure text as a query

generate_query() previously returned the literal string "ERROR: all providers
failed (...)" when every provider failed, and nothing downstream checked for
it — app.py and api_routes.py fed it straight into classify_query()/is_safe()/
the query executor as if it were real SQL. Now it returns None, and all three
call sites render a clean user-facing message instead.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Actuator on by default for local/dev runs

**Files:**
- Modify: `app.py:2858-2859` (the `if __name__ == "__main__":` block)
- Modify: `app.py` (add a context processor, near the actuator route definitions around line 118)
- Modify: `templates/base.html:95-97` (add a footer block)

**Interfaces:**
- Produces: Jinja global `actuator_enabled` (bool), available in every template via Flask's `app.context_processor`.
- Consumes: none from Task 1.

**Note:** this task runs AFTER Task 1 is committed (both touch `app.py`, different regions — avoid stacking uncommitted edits across two tasks in the same file).

- [ ] **Step 1: Confirm actuator is currently invisible on a plain run**

```bash
cd /Volumes/BLACK_SHARK/MINOR_PROJECT
pkill -f "python app.py" 2>/dev/null; sleep 1
ENABLE_ACTUATOR= ./venv/bin/python app.py > /tmp/plain_run_before.log 2>&1 &
sleep 3
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5001/actuator
```
Expected: `404` (confirms the bug — an evaluator running `python app.py` normally never sees actuator).

- [ ] **Step 2: Default `ENABLE_ACTUATOR` on for the dev entrypoint**

In `app.py`, find:
```python
if __name__ == "__main__":
    app.run(debug=True, port=5001)
```
Replace with:
```python
if __name__ == "__main__":
    # Actuator is opt-in for production (gunicorn/Docker never hits this block),
    # but a plain `python app.py` dev run should show it without needing to
    # remember an env var — mirrors FastAPI's automatic /docs being just-there.
    os.environ.setdefault("ENABLE_ACTUATOR", "1")
    app.run(debug=True, port=5001)
```

- [ ] **Step 3: Verify actuator is now visible on a plain run**

```bash
cd /Volumes/BLACK_SHARK/MINOR_PROJECT
pkill -f "python app.py" 2>/dev/null; sleep 1
./venv/bin/python app.py > /tmp/plain_run_after.log 2>&1 &
sleep 3
curl -s http://localhost:5001/actuator
```
Expected: JSON body with `_links.self` and `_links.mappings` (200, not 404).

- [ ] **Step 4: Add a context processor so templates know whether actuator is enabled**

In `app.py`, find:
```python
@app.route("/actuator/mappings")
def actuator_mappings():
    if not _actuator_enabled():
        return jsonify({"error": "Not found"}), 404
    return jsonify(_actuator_mappings())
```
Add immediately after it:
```python


@app.context_processor
def inject_actuator_flag():
    return {"actuator_enabled": _actuator_enabled()}
```

- [ ] **Step 5: Add a footer link in the shared base template**

In `templates/base.html`, find:
```
{% block body %}
{% block content %}{% endblock %}
{% endblock %}

{% block scripts %}{% endblock %}
```
Replace with:
```
{% block body %}
{% block content %}{% endblock %}
{% endblock %}

{% if actuator_enabled %}
<footer style="text-align:center; padding:12px; font-size:0.7rem; color:var(--text-dim);">
    <a href="/actuator" style="color:inherit;">/actuator</a> — live route map (this deployment only; opt-in via ENABLE_ACTUATOR)
</footer>
{% endif %}

{% block scripts %}{% endblock %}
```

- [ ] **Step 6: Verify the footer renders when actuator is on, and is absent when it's off**

With the app still running from Step 3 (actuator on):
```bash
curl -s http://localhost:5001/login | grep -o '/actuator.*route map' | head -1
```
Expected: the footer text is present.

```bash
pkill -f "python app.py" 2>/dev/null; sleep 1
ENABLE_ACTUATOR= ./venv/bin/python -m flask --app app run --port 5001 > /tmp/plain_run_off.log 2>&1 &
sleep 3
curl -s http://localhost:5001/login | grep -c "/actuator"
pkill -f "flask --app app run" 2>/dev/null
```
Expected: `0` (footer correctly absent when actuator is off — `flask run` doesn't hit the `__main__` block's `setdefault`, so this simulates the production/gunicorn path).

- [ ] **Step 7: Commit**

```bash
cd /Volumes/BLACK_SHARK/MINOR_PROJECT
git add app.py templates/base.html
git commit -m "$(cat <<'EOF'
Enable actuator by default on local dev runs, link it from the UI footer

ENABLE_ACTUATOR was opt-in and undocumented-at-a-glance, so a plain `python
app.py` run (what an evaluator would do) never showed it. Now on by default
for the dev entrypoint only (production/gunicorn stays opt-in), and linked
from the footer so it's discoverable without reading docs.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Full API contract — cover all ~52 `/api` endpoints, not just 6

**Files:**
- Create: `scripts/generate_full_contract.py`
- Create (generated by the script, not hand-written): `full_api_contract.yaml`
- Modify: `specmatic.yaml` (add `full_api_contract.yaml` as a spec + securityScheme)
- Modify: `CONTRACT_SCOPE.md` (document the two-tier contract rationale)
- Modify: `readme.md` (add the new test command)

**Interfaces:**
- Produces: `full_api_contract.yaml` at the repo root, one OpenAPI document covering every `/api/*` route except the 6 already governed by `api_contract.yaml`.
- Consumes: `app.url_map` (Flask's route table) — same introspection technique `_actuator_mappings()` in `app.py` already uses.

- [ ] **Step 1: Write the generator script**

Create `scripts/generate_full_contract.py`:

```python
#!/usr/bin/env python3
"""Auto-generates full_api_contract.yaml — an OpenAPI 3.0 contract covering
every real /api route in the app, not just the 6 hand-curated ones in
api_contract.yaml.

Broad coverage, not deep fidelity: request bodies are permissive (any JSON
object) and only the two response shapes the app's own auth guard actually
guarantees are asserted — 401 Unauthorized (exact schema; every /api route
enforces this identically via app.py's require_login()) and 200 (permissive
schema, since real body shapes vary per endpoint and this layer trades
per-endpoint fidelity for full route breadth). See CONTRACT_SCOPE.md for the
two-tier rationale — api_contract.yaml stays the deep, hand-curated layer for
the 6 endpoints external consumers actually depend on.

Run:
    python scripts/generate_full_contract.py
Writes: full_api_contract.yaml (repo root)
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("GROQ_API_KEY", "contract-generation-placeholder")

from app import app  # noqa: E402  (import after sys.path/env setup, matches app.py's own style)

# Exact paths only — do NOT use startswith, "/api/command" is a prefix of
# "/api/command-center/execute-raw" which must NOT be excluded.
GOVERNED_PATHS = {
    "/api/auth/login",
    "/api/auth/session",
    "/api/connections",
    "/api/command",
    "/api/execute",
    "/api/undo",
}


def flask_path_to_openapi(rule):
    return re.sub(r"<(?:[^:<>]+:)?([^<>]+)>", r"{\1}", rule)


def collect_routes():
    routes = {}
    for rule in app.url_map.iter_rules():
        if not rule.rule.startswith("/api"):
            continue
        path = flask_path_to_openapi(rule.rule)
        if path in GOVERNED_PATHS:
            continue
        methods = sorted(m for m in (rule.methods or set()) if m not in ("HEAD", "OPTIONS"))
        routes.setdefault(path, set()).update(methods)
    return dict(sorted(routes.items()))


def path_params(path):
    return re.findall(r"\{([^}]+)\}", path)


def emit_operation(method, path):
    lines = [f"    {method.lower()}:"]
    lines.append(f'      summary: "{method} {path}"')
    params = path_params(path)
    if params:
        lines.append("      parameters:")
        for p in params:
            lines.append(f"        - name: {p}")
            lines.append("          in: path")
            lines.append("          required: true")
            lines.append("          schema: { type: string }")
    if method in ("POST", "PUT", "DELETE", "PATCH"):
        lines.append("      requestBody:")
        lines.append("        required: false")
        lines.append("        content:")
        lines.append("          application/json:")
        lines.append("            schema:")
        lines.append("              type: object")
    lines.append("      responses:")
    lines.append('        "200":')
    lines.append("          description: Success (shape varies by endpoint — see api_contract.yaml for hand-curated deep contracts)")
    lines.append('        "401":')
    lines.append("          description: Unauthorized (no or invalid credentials)")
    lines.append("          content:")
    lines.append("            application/json:")
    lines.append("              schema:")
    lines.append("                type: object")
    lines.append("                required: [error]")
    lines.append("                properties:")
    lines.append("                  error: { type: string }")
    return "\n".join(lines)


def main():
    routes = collect_routes()

    out = []
    out.append("openapi: 3.0.3")
    out.append("info:")
    out.append("  title: Meridian Data — Full API Surface (auto-generated)")
    out.append('  version: "1.0.0"')
    out.append("  description: >")
    out.append("    Auto-generated from the live Flask route table (app.url_map) by")
    out.append("    scripts/generate_full_contract.py. Covers every /api route so contract")
    out.append("    testing exercises the FULL attack surface, not just the 6 hand-curated")
    out.append("    endpoints in api_contract.yaml. Broad coverage, not deep fidelity — see")
    out.append("    CONTRACT_SCOPE.md for the two-tier rationale. Regenerate after adding or")
    out.append("    removing routes: python scripts/generate_full_contract.py")
    out.append("security:")
    out.append("  - bearerAuth: []")
    out.append("paths:")
    for path, methods in routes.items():
        out.append(f"  {path}:")
        for method in sorted(methods):
            out.append(emit_operation(method, path))
    out.append("components:")
    out.append("  securitySchemes:")
    out.append("    bearerAuth:")
    out.append("      type: http")
    out.append("      scheme: bearer")

    text = "\n".join(out) + "\n"
    out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "full_api_contract.yaml")
    with open(out_path, "w") as f:
        f.write(text)
    op_count = sum(len(m) for m in routes.values())
    print(f"Wrote {out_path} — {len(routes)} paths, {op_count} operations")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it and sanity-check the output**

```bash
cd /Volumes/BLACK_SHARK/MINOR_PROJECT && ./venv/bin/python scripts/generate_full_contract.py
```
Expected: `Wrote .../full_api_contract.yaml — 46 paths, N operations` (46 paths matches `CONTRACT_SCOPE.md`'s documented "46 Missing in Spec" count; N will be somewhat higher since a few paths have both GET and POST).

```bash
./venv/bin/python -c "
import re
text = open('full_api_contract.yaml').read()
assert '/api/execute:' not in text, 'governed path leaked into the full contract'
assert '/api/command:' not in text, 'governed path leaked into the full contract'
assert '/api/command-center/execute-raw:' in text, 'a real endpoint is missing'
print('OK — governed paths excluded, other real paths present')
"
```
Expected: `OK — governed paths excluded, other real paths present`

- [ ] **Step 3: Wire `full_api_contract.yaml` into `specmatic.yaml`**

In `specmatic.yaml`, find:
```yaml
            specs:
              - contract_public.yaml
              - api_contract.yaml
```
Replace with:
```yaml
            specs:
              - contract_public.yaml
              - api_contract.yaml
              - full_api_contract.yaml
```

Then find:
```yaml
        specs:
          - spec:
              id: api_contract.yaml
              securitySchemes:
                bearerAuth:
                  type: bearer
                  token: ${API_BEARER_TOKEN:specmatic-ci-token}
```
Replace with:
```yaml
        specs:
          - spec:
              id: api_contract.yaml
              securitySchemes:
                bearerAuth:
                  type: bearer
                  token: ${API_BEARER_TOKEN:specmatic-ci-token}
          - spec:
              id: full_api_contract.yaml
              securitySchemes:
                bearerAuth:
                  type: bearer
                  token: ${API_BEARER_TOKEN:specmatic-ci-token}
```

- [ ] **Step 4: Live-verify — run the new contract test against the running app**

Ensure the LLM stub (`:9090`) and the app in testing mode (`:5001`, `API_BEARER_TOKEN=specmatic-ci-token`, `ENABLE_ACTUATOR=1`) are running (same pattern used earlier this session). Then:

```bash
cd /Volumes/BLACK_SHARK/MINOR_PROJECT
TEST_APP_PORT=5001 java -jar ${SPECMATIC_JAR:-specmatic.jar} test full_api_contract.yaml --host localhost --port 5001 2>&1 | tail -40
```
Expected: the run completes (not a crash/exception from Specmatic itself) and prints a `Tests run: N, Successes: X, Failures: Y` summary along with an API coverage table listing the ~46 new operations. Report the actual X/Y numbers honestly — do not assume 100%; the permissive-schema design means some endpoints may fail their 200-path assertion on body-shape grounds, which is expected and documented, not a regression.

- [ ] **Step 5: Update `CONTRACT_SCOPE.md` to document the two-tier contract**

In `CONTRACT_SCOPE.md`, find the line:
```
## What is intentionally out of scope (the 46 "Missing in Spec")
```
Replace with:
```
## Two-tier contract coverage (2026-07-18)

The 46 endpoints below are no longer untested — `full_api_contract.yaml`
(auto-generated by `scripts/generate_full_contract.py` from the live Flask
route table) now covers all of them, run via Specmatic alongside
`api_contract.yaml`. It trades per-endpoint fidelity for full breadth: request
bodies are permissive and only the auth boundary (401 without credentials,
200 with them) is asserted, rather than hand-verified request/response shapes.
That boundary is real and uniform — every `/api/*` route enforces it
identically via `app.py`'s `require_login()` — so this is a meaningful
"a hacker can't get past the front door on any of the 52 endpoints" guarantee,
not a rubber-stamp. `api_contract.yaml` remains the deep, hand-curated layer
for the 6 endpoints external consumers actually depend on.

Regenerate `full_api_contract.yaml` after adding or removing routes:
`python scripts/generate_full_contract.py`.

## Why the original 6 stayed hand-curated (historical context below)
```

- [ ] **Step 6: Add the new test command to `readme.md`**

In `readme.md`, find:
```
**Terminal 3 again — the full API contract test:**
```bash
TEST_APP_PORT=5001 java -jar ${SPECMATIC_JAR:-specmatic.jar} test api_contract.yaml --examples examples_api --host localhost --port 5001
```

Both report **100% API coverage**, actuator enabled (actual, not just matched, coverage). The same four commands run in CI on every push — see [`.github/workflows/contract.yml`](.github/workflows/contract.yml). HTML reports land in `build/reports/specmatic/test/html/`; committed snapshots are in [`reports/`](reports/).
```
Replace with:
```
**Terminal 3 again — the full API contract test:**
```bash
TEST_APP_PORT=5001 java -jar ${SPECMATIC_JAR:-specmatic.jar} test api_contract.yaml --examples examples_api --host localhost --port 5001
```

**Terminal 3 again — the full-surface contract test (all ~52 `/api` endpoints, auto-generated):**
```bash
TEST_APP_PORT=5001 java -jar ${SPECMATIC_JAR:-specmatic.jar} test full_api_contract.yaml --host localhost --port 5001
```

The first two report **100% API coverage** on the 6 hand-curated endpoints (actuator enabled — actual, not just matched, coverage). The third exercises every other `/api` route the app exposes — see [`CONTRACT_SCOPE.md`](./CONTRACT_SCOPE.md) for what it does and doesn't assert. All commands run in CI on every push — see [`.github/workflows/contract.yml`](.github/workflows/contract.yml). HTML reports land in `build/reports/specmatic/test/html/`; committed snapshots are in [`reports/`](reports/).
```

- [ ] **Step 7: Commit**

```bash
cd /Volumes/BLACK_SHARK/MINOR_PROJECT
git add scripts/generate_full_contract.py full_api_contract.yaml specmatic.yaml CONTRACT_SCOPE.md readme.md
git commit -m "$(cat <<'EOF'
Add auto-generated full API contract covering all ~52 /api endpoints

api_contract.yaml only governs 6 hand-curated endpoints. A hacker (or a
generative Specmatic test run) doesn't stop at those 6, so
full_api_contract.yaml — generated from the live Flask route table — now
covers the other 46, asserting the one guarantee that's uniform across all of
them: unauthenticated requests get a clean 401 everywhere.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Docker Compose brings up backend + frontend + local Ollama in one command

**Files:**
- Modify: `docker-compose.yml`
- Modify: `readme.md` (Docker section)

**Interfaces:**
- No code interfaces — pure infra. Relies on `core/llm_manager.py`'s existing `DEFAULT_CONFIG["active_provider"] = "mistral"` (already Ollama-first by default — confirmed in codebase, no application code change needed) and `OLLAMA_API_URL` env-var override (already read by `core/llm_manager.py::_apply_env_overrides`).

- [ ] **Step 1: Add the `ollama` service and a one-shot model-pull init container**

In `docker-compose.yml`, find:
```yaml
  frontend:
    build:
      context: ./meridian-frontend
      dockerfile: Dockerfile
    container_name: meridian-frontend
    restart: unless-stopped
    depends_on:
      - backend
    ports:
      - "8080:80"
    networks:
      - meridian-net

networks:
  meridian-net:
    driver: bridge

volumes:
  meridian-db:
    driver: local
```
Replace with:
```yaml
  frontend:
    build:
      context: ./meridian-frontend
      dockerfile: Dockerfile
    container_name: meridian-frontend
    restart: unless-stopped
    depends_on:
      - backend
    ports:
      - "8080:80"
    networks:
      - meridian-net

  ollama:
    image: ollama/ollama:latest
    container_name: meridian-ollama
    restart: unless-stopped
    volumes:
      - ollama-data:/root/.ollama
    expose:
      - "11434"
    networks:
      - meridian-net
    healthcheck:
      test: ["CMD", "ollama", "list"]
      interval: 5s
      timeout: 5s
      retries: 10
      start_period: 10s

  ollama-pull:
    image: ollama/ollama:latest
    container_name: meridian-ollama-pull
    depends_on:
      ollama:
        condition: service_healthy
    environment:
      - OLLAMA_HOST=ollama:11434
    entrypoint: ["ollama", "pull", "mistral"]
    networks:
      - meridian-net
    restart: "no"

networks:
  meridian-net:
    driver: bridge

volumes:
  meridian-db:
    driver: local
  ollama-data:
    driver: local
```

Then find (in the `backend` service — confirmed via the current file that `backend` has no `depends_on` key today, only `frontend` does):
```yaml
  backend:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: meridian-backend
    restart: unless-stopped
    environment:
      - GROQ_API_KEY=${GROQ_API_KEY:-}
      - FLASK_ENV=production
      - PYTHONUNBUFFERED=1
    volumes:
      - meridian-db:/app/db
    expose:
      - "5001"
    ports:
      - "5001:5001"
    networks:
      - meridian-net
```
Replace with:
```yaml
  backend:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: meridian-backend
    restart: unless-stopped
    environment:
      - GROQ_API_KEY=${GROQ_API_KEY:-}
      - OLLAMA_API_URL=http://ollama:11434/api/generate
      - FLASK_ENV=production
      - PYTHONUNBUFFERED=1
    depends_on:
      - ollama
    volumes:
      - meridian-db:/app/db
    expose:
      - "5001"
    ports:
      - "5001:5001"
    networks:
      - meridian-net
```

- [ ] **Step 2: Bring the stack up from a clean state and verify**

```bash
cd /Volumes/BLACK_SHARK/MINOR_PROJECT
docker compose down -v 2>&1 | tail -5
docker compose up -d --build
```
Expected: all four containers (`meridian-backend`, `meridian-frontend`, `meridian-ollama`, `meridian-ollama-pull`) start; `meridian-ollama-pull` exits 0 after pulling.

```bash
docker compose ps
```
Expected: `backend`, `frontend`, `ollama` show `Up` / `healthy`; `ollama-pull` shows `Exited (0)`.

```bash
timeout 300 docker compose logs -f ollama-pull 2>&1 | grep -m1 "success\|Exited" || docker compose ps ollama-pull
```
(Model pull can take a few minutes on first run — this waits for it.)

```bash
docker compose exec ollama ollama list
```
Expected: `mistral` appears in the list.

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5001/
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/
```
Expected: both `200` (or `302` for backend if it redirects to login — either confirms the server is up).

- [ ] **Step 3: End-to-end verify the AI path actually goes through the containerized Ollama, not a host install**

```bash
docker compose exec backend sh -c "python -c \"
import os
os.environ.setdefault('OLLAMA_API_URL', 'http://ollama:11434/api/generate')
from core.llm import generate_query
print(generate_query('show all albums', 'sqlite', 'TABLE Album(AlbumId, Title, ArtistId)', provider='mistral'))
\""
```
Expected: a real SQL string comes back (e.g. `SELECT * FROM Album LIMIT 50`), proving the query went backend-container → `ollama` service → mistral model → back, entirely inside Docker, with no host-level Ollama install involved.

- [ ] **Step 4: Update `readme.md`'s Docker section**

In `readme.md`, find:
```
Or the whole stack in one command via Docker:
```bash
python start.py
```
Opens **http://localhost:8080**. Stop it with `python start.py --stop`.
```
Replace with:
```
Or the whole stack in one command via Docker — backend, frontend, **and a local
Ollama LLM** (`mistral`, auto-pulled on first run — no cloud API key needed to
see the AI features work):
```bash
python start.py
```
Opens **http://localhost:8080**. First run pulls the Ollama model in the
background (a few minutes, ~4GB) — the app is usable immediately for the
hardcoded DBMS commands, and AI query generation works as soon as the pull
finishes. Stop it with `python start.py --stop`. Set `GROQ_API_KEY` in `.env`
first if you'd rather use Groq's cloud API instead of (or as a fallback to)
the bundled local Ollama.
```

- [ ] **Step 5: Commit**

```bash
cd /Volumes/BLACK_SHARK/MINOR_PROJECT
git add docker-compose.yml readme.md
git commit -m "$(cat <<'EOF'
Bundle a local Ollama LLM into docker-compose — one command, nothing else to run

Local setup previously needed backend, frontend, and (for AI features) an LLM
provider run/configured separately. docker-compose (already wrapped by
`python start.py`) now also brings up an Ollama container and auto-pulls
mistral on first run, so the AI query path works out of the box with no cloud
API key and no host-level installs — core/llm_manager.py already defaults to
the mistral/Ollama provider, this just makes it reachable in the container
network.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Final integration check (after all four tasks are committed)

- [ ] **Step 1: Push the branch**

```bash
cd /Volumes/BLACK_SHARK/MINOR_PROJECT
git push origin react_build
```

- [ ] **Step 2: Confirm CI picks up the changes**

```bash
gh run list --branch react_build --limit 3
```
Expected: a new run triggered by the push; note the run ID for the email summary (don't block on it finishing if it's slow — report what's observed).

- [ ] **Step 3: Draft and send the summary email to Saachi**

Only after Tasks 1-4's own verification steps have all passed live (not just "should work"). Follow the established SMTP pattern (`scripts/send_specmatic_reply*.py`): dry-run by default, `--send` flag to actually send, `.gmail_app_password` for auth, `saachi.kaup@specmatic.io` as recipient, plain-text body summarizing each of the four fixes with the real verification evidence (actual pass/fail counts from Task 3, actual container-list output from Task 4, etc.) — not restating the plan, reporting what was actually run and observed.
