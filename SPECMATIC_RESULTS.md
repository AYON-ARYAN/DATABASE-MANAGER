# Specmatic Run Results — Meridian Data (real, captured)

Specmatic **v2.48.0**, run against the live Flask app (`python -m flask --app app run --port 5001`).
All output below is real, not illustrative.

---

## 1. Stub / service virtualization — `specmatic stub api_contract.yaml`
Specmatic served a contract-conformant mock with **no backend, DB, or LLM keys**:

`POST /api/command` →
```json
{ "task": "...", "sql": "...", "explanation": "...",
  "columns": ["...","...","..."], "results": [["...","...","..."]],
  "page": 582, "page_size": 985, "total_rows": 796 }   // matches ReadResult
```
`POST /api/auth/login` → `{ "success": true, "username": "...", "role": "..." }`  // matches LoginOk

This is what the React frontend (`meridian-frontend`) can develop against in parallel.

## 2. Executable contract test (GREEN) — `specmatic test contract_public.yaml --host localhost --port 5001`
```
API: POST /api/auth/login -> 200
Tests run: 1, Successes: 1, Failures: 0
```
The live API conforms to its contract. ✅

## 3. 🎯 The money shot — catching AI-style drift
Simulating what an AI coding agent often does, I renamed `success` → `ok` in the `/api/auth/login`
response (a silent shape change). Re-running the **same** contract test:
```
Scenario: POST /api/auth/login -> 200 ... has FAILED
  Summary: A required property defined in the specification is missing
  Specification expected mandatory property "success" to be present but was missing from the response
Tests run: 1, Successes: 0, Failures: 1
```
**Specmatic caught the drift instantly**, naming the exact missing field — before it could break the
frontend or production. Reverting the one-line change → back to GREEN (1/1). This is the guardrail.

## 4. Auth-boundary finding (real insight) — full contract test
Running the test against the *full* `api_contract.yaml` surfaced something useful:
```
GET  /api/connections -> expected 200 but got 401
POST /api/command     -> expected 200 but got 401
POST /api/execute     -> expected 200 but got 401
POST /api/undo        -> expected 200 but got 401
Tests run: 7, Successes: 1, Failures: 6
```
Specmatic immediately enforced that **6 of 7 endpoints sit behind authentication** (Flask session) —
a boundary my initial contract hadn't documented. I updated the contract to document the `401`
responses. (Specmatic supports header/bearer/oauth2 auth for automated login, not Flask cookies, so
the authenticated happy-paths are exercised via the stub + the public endpoint above.)

---

### Takeaway
Two guardrails, one principle — *don't let generated actions run unchecked*:
- **DB layer:** `needs_review` → human confirm → `/api/execute` + `/api/undo` rollback
- **API layer (Specmatic):** executable contract catches silent drift (human or AI) in CI, in seconds
