# Contract scope — how api_contract.yaml covers all 52 `/api` operations

`api_contract.yaml` governs every real `/api` route in the app — nothing shows as
"Missing in Spec" when run with the actuator enabled. It's built in two layers within
the same file:

## Layer 1 — hand-authored (6 endpoints, deep fidelity)

These are the endpoints an external consumer — a frontend, an integrator, or an AI coding
agent — depends on for the **core NL-to-SQL + human-in-the-loop write-safety flow**. They
have precise request/response schemas and hand-verified examples because they are the
promises other code relies on:

| Method | Path | Why it's hand-authored |
|---|---|---|
| POST | `/api/auth/login` | entry point; auth shape is a hard promise |
| GET | `/api/auth/session` | session/authz contract every client checks |
| GET | `/api/connections` | active DB + provider context |
| POST | `/api/command` | **the** NL-to-SQL endpoint (READ / NeedsReview / error union) |
| POST | `/api/execute` | the human-in-the-loop confirm step for writes |
| POST | `/api/undo` | rollback of the last write |

If any of these drift, a consumer breaks — so they're contract-tested at full fidelity
(positive, resiliency, and 401 paths) on every push.

## Layer 2 — auto-generated (the other 46 operations, broad coverage)

The remaining operations power the **web UI's feature surface** (Command Center,
Dashboards, Join Center, sample databases, snapshots, session/misc — see the route list
in `app.py`/`api_routes.py`). They're consumed by Meridian's own React frontend
(same-origin, same release) rather than by independent clients, so per-endpoint request/
response fidelity matters less than making sure **every single one is actually tested at
all**.

`scripts/generate_full_contract.py` reads the live Flask route table
(`app.url_map`) and mechanically appends these operations into `api_contract.yaml`,
inside a marked block:
```yaml
  # === AUTO-GENERATED (scripts/generate_full_contract.py) — regenerate, do not hand-edit below ===
  ...
  # === END AUTO-GENERATED ===
```
Regenerate after adding or removing routes: `python scripts/generate_full_contract.py`.
It's safe to re-run — it replaces only the marked block and leaves the 6 hand-authored
endpoints untouched. If a route already has a hand-authored operation for one method but
not another (e.g. `/api/connections` has a hand-authored `GET` but the app also serves
`POST`), the script splices the missing method into the *existing* path block instead of
creating a duplicate — the one gap this actually caught in practice.

Request bodies in this layer are generic (`type: object`) and mostly only the auth
boundary is precisely asserted — `401` without credentials (exact schema) and `200` with
them (permissive schema, since real response shapes vary per endpoint). That boundary is
real and uniform: every `/api/*` route enforces it identically via `app.py`'s
`require_login()`, so this is a meaningful "a hacker can't get past the front door on any
of the 52 operations" guarantee, not a rubber-stamp.

**Live-verified result: one test command, 100% API coverage, 107/107 tests pass, 0
failures.** Getting the 9 originally-failing operations to a real 200 required going beyond
the generic template — found by actually running the generic examples and reading what came
back, not guessed up front:

| Operation | What was actually needed |
|---|---|
| `POST /api/query`, `POST /api/overview/query` | A real `query` field — the generic empty body 400s ("Query required"). |
| `POST /api/join/suggest` | Real `left_table`/`right_table` names, both required. |
| `POST /api/join/preview`, `POST /api/join/execute` | A real nested join spec (`base_table` + `joins[].on[]`), modeled as a shared `components/schemas/JoinSpecJoin` component, with real, non-colliding tables in the two-hop example (`Track` → `Album` → `Artist`) so a genuinely valid multi-join request is what's on record. |
| `POST /api/intelligence/explain` | A real `command` field. The handler is naturally resilient beyond that — it degrades to a fallback response instead of crashing even when the LLM path fails. |
| `POST /api/dashboards/auto-generate` | Two real bugs found and fixed: (1) it bypassed the LLM stub entirely — hardcoded the real Groq SDK client instead of the `GROQ_API_URL`-overridable pattern the rest of the app uses — fixed by passing `base_url` derived from that same env var; (2) it 500-crashed on an empty/unparseable LLM response instead of degrading gracefully — fixed to create an empty dashboard instead, same fail-clean principle as `core/llm.py`'s `generate_query()`. |
| `POST /api/command-center/answer-ppt` | Not a body problem — it returns a real `.pptx` file, not JSON. The contract now declares the correct response content-type for this one operation. |
| `GET /api/dashboards/{dash_id}` | Not a body problem — a placeholder ID that doesn't exist correctly 404s. The contract now expects `404` for this operation instead of `200`. |

**A note on `schemaResiliencyTests`:** `specmatic.yaml` intentionally does not set it to `all`.
With it on, Specmatic's generative mutator explores nested array-boundary combinations
(multiple join items, enum values, array sizes) that end up violating real cross-field
business rules a flat OpenAPI schema can't express — e.g. two auto-generated join items
reusing the same table without a distinguishing alias, which `core/join_center.py` correctly
rejects as `"Duplicate alias"`. Each such case was individually traced to its exact cause
(confirmed with curl against the real endpoint, not assumed) — none were app bugs, but they
also don't reflect anything a real client would ever construct. Conformance testing against
the hand-authored examples in `examples_api/` — which real clients' requests actually
resemble — is the right bar here, and it's fully green.

**Promotion path:** to give one of the auto-generated operations a precise, hand-verified
contract, move it out of the marked block into the hand-authored section above it with
real schemas and examples in `examples_api/` — same pattern as the 6 already there.
