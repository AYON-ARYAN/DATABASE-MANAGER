# Specmatic Integration — Meridian Data

This document shows how Meridian Data uses **Specmatic** and its OpenAPI contract
(`api_contract.yaml`) as an **executable contract** — to contract-test the live API and to
stub it for the frontend, so neither humans nor AI coding agents can silently drift the API.

> Prereq: **Docker Desktop running** (start it first), and the Meridian Data app running.

## Files
- `api_contract.yaml` — the OpenAPI 3.0 contract (single source of truth) for the `/api` blueprint
- `specmatic.yaml` — Specmatic config pointing at the contract

## 0. Run the app
```bash
flask --app app run --port 5001  #            # serves the Flask /api blueprint on http://localhost:5001
```

## 1. Contract test (the executable contract)
Specmatic reads the contract, auto-generates positive **and** negative requests, fires them at
the running API, and verifies every response conforms to the spec.
```bash
docker run --rm --network host -v "$PWD:/specs" -w /specs \
  specmatic/specmatic:latest test --host localhost --port 5001
```
> 📸 Screenshot the passing run for the blog.

## 2. Service virtualization (stub) — frontend dev with no backend
Spin up a spec-conformant mock so the React SPA (`meridian-frontend`) can develop in parallel:
```bash
docker run --rm --network host -v "$PWD:/specs" -w /specs \
  specmatic/specmatic:latest stub --port 9000
# then:
curl -s -X POST localhost:9000/api/command -H 'Content-Type: application/json' \
  -d '{"command":"show top 10 customers by revenue"}' | jq
```
The stub returns data matching the `ReadResult`/`NeedsReview` schema — no DB, no LLM keys needed.
> 📸 Screenshot the stub serving contract-shaped data.

## 3. 🎯 THE MONEY SHOT — catching AI-generated drift
This is the heart of the submission (their question: *can executable contracts improve AI-assisted dev?*).

1. Ask an AI coding agent (Claude Code / Cursor) to modify an endpoint — e.g.
   *"add a `confidence` score to /api/command and rename `needs_review` to `requiresReview`."*
2. Let the agent change `api_routes.py` (it will happily rename the field — exactly the silent
   drift that breaks the React frontend three layers downstream).
3. Re-run the contract test (Step 1). **Specmatic fails instantly**, pinpointing:
   `/api/command -> response did not match: key "needs_review" missing` (or status/type mismatch).
4. Fix in one line. Re-run → green.

**The lesson:** the executable contract turned a silent, AI-introduced integration bug into an
automated test failure in seconds — *before* it ever reached the frontend or production.
> 📸 Screenshot the red failure (with the exact mismatch line) + the green re-run.

## 4. Bonus — backward-compatibility check
Prove the contract prevents breaking changes between versions:
```bash
cp api_contract.yaml api_contract_v2.yaml   # make a breaking edit in v2 (e.g. drop a required field)
docker run --rm -v "$PWD:/specs" -w /specs \
  specmatic/specmatic:latest compatible /specs/api_contract.yaml /specs/api_contract_v2.yaml
```
> 📸 Screenshot the "incompatible" detection.

## Why this matters for Meridian Data specifically
Meridian Data already enforces **human-in-the-loop write safety** (`needs_review` →
`/api/execute` confirm → `/api/undo` rollback). Specmatic adds a *second* guardrail at the
**API-contract** layer: the same "don't let it run unchecked" philosophy, now applied to
AI-generated code. Two guardrails, one principle — the 80% plumbing that makes AI safe to ship.
