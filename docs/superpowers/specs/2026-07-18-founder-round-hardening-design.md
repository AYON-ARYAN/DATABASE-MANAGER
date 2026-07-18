# Founder-round hardening (Naresh Jain feedback, 2026-07-17)

## Context

After the founder-round call with Naresh Jain (Specmatic CEO), he gave three pieces of
feedback verbally (no written email — relayed by Ayon), plus a packaging ask:

1. LLM resilience isn't tested — the online LLM call path should be hard-broken
   (empty/malformed responses) to see how the app copes.
2. Actuator isn't enabled when he checked — Flask makes you do this manually vs.
   FastAPI-style automatic introspection.
3. Contract test coverage only spans the 6 governed `/api` endpoints out of ~50-60
   real ones — "a hacker wouldn't stop at 5."
4. Packaging: local run currently requires running backend, frontend, and (for AI
   features) an LLM provider separately. Wants one Docker command that runs
   everything, including a local Ollama LLM, so nobody needs cloud credentials or
   multiple terminals to see the app work.

## 1. LLM resilience

**Root cause (confirmed in code):** `core/llm.py::generate_query()` falls back to
returning the literal string `"ERROR: all providers failed (...)"` when every
provider in the chain fails or returns something unparseable. Nothing downstream
checks for this — `app.py:637`, `app.py:951`, and `api_routes.py:375` all feed the
return value straight into `classify_query()` → `is_safe()` → the query executor as
if it were real SQL.

**Fix:**
- `_call_groq` / `_call_ollama` validate the response shape (non-empty `choices`,
  non-blank `content`) and raise a clear `ValueError` instead of letting a raw
  `KeyError`/`IndexError` propagate.
- `generate_query()` returns `None` (not a string) when every provider fails, so it
  can never be mistaken for a generated query.
- The three call sites check for `None` and render a clean user-facing message
  ("couldn't generate a query, please retry or rephrase") instead of attempting to
  execute the failure text.
- New `scripts/llm_fault_injection_test.py`: drives the app's NL-to-SQL path against
  the existing Specmatic LLM stub (`llm_contract.yaml`), feeding it deliberately
  broken responses (empty `choices` array, blank `content`, malformed JSON body) and
  asserts the app degrades cleanly each time — no crash, no attempted SQL execution
  of the failure text, a `None`/clean-error result surfaced instead.

## 2. Actuator visibility

**Fix:** `ENABLE_ACTUATOR` defaults to **on** for local/dev runs (`python app.py`
directly), stays **opt-in/off** for the production path (gunicorn/Docker), mirroring
how Spring Boot Actuator itself behaves (dev-enabled, prod-gated). Add a link to
`/actuator` from the app's own footer/UI so it's discoverable without reading docs —
answering the "FastAPI just gives you this" comment without a framework rewrite.

## 3. Full API contract

**Fix:** New `scripts/generate_full_contract.py` walks `app.url_map` (the same
introspection `/actuator/mappings` already does) and emits `full_api_contract.yaml`
covering every real route — auto-generated, not hand-authored, so it's tractable for
~50-60 endpoints. Wired into a new Specmatic run
(`schemaResiliencyTests: all`) so generative/negative tests exercise every
endpoint's auth and input handling. The existing hand-authored `api_contract.yaml`
(6 endpoints, rich examples) is kept as-is as the deep/curated layer;
`full_api_contract.yaml` is the new broad-coverage layer. `CONTRACT_SCOPE.md` gets a
short update explaining the two-tier approach so it doesn't read as duplicated
effort.

## 4. Docker Compose + local Ollama

**Fix:** Add an `ollama` service to `docker-compose.yml` (official `ollama/ollama`
image, persisted volume, port 11434 on the compose network only). Add a one-shot
init step that runs `ollama pull mistral` against it on first `docker compose up`
(not baked into the image — that would add gigabytes to every build). Backend's
`OLLAMA_API_URL` points at the compose-network Ollama service by default. Result:
`docker compose up` alone brings up backend + frontend + a working local LLM, no
cloud key required, no separate terminal windows. `readme.md`'s Docker section
updated to present this as the "just run it" path.

## Verification

Each of the four is verified live before anything is called done:
- Fault-injection script passes against the running app + LLM stub.
- Actuator visible on a plain `python app.py` run with no env vars set.
- Full-contract Specmatic run completes against the live app, report generated,
  covering all ~50-60 endpoints.
- `docker compose up` brings up all three containers from a clean state; curl +
  browser check confirms the AI query path works end-to-end through the
  containerized Ollama, no host Python/npm/Ollama install involved.

Only after all four are confirmed working does the summary email go to Saachi.

## Out of scope

- No framework migration (Flask stays Flask — no FastAPI rewrite).
- No retry/backoff logic for LLM calls (not what was asked; fail-clean is enough).
- No changes to the existing 6-endpoint `api_contract.yaml`'s hand-authored examples.
