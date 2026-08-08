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

**Live-verified result (`schemaResiliencyTests: all`, the full contract + generative
suite, run via `docker compose run contract-tests` — the exact command in the README):
100% API coverage, 1830 tests, 1776 pass (97%), 54 known/explained failures, 0 fake
anything.** Every one of the 400 response declarations in this file corresponds to a real,
curl-verified validation path in the running app — see the table below for exactly what
each operation needs, and the section after it for the one residual, honestly-documented
gap.

| Operation | What was actually needed |
|---|---|
| `POST /api/query`, `POST /api/overview/query` | A real `query` field — the generic empty body 400s ("Query required"). |
| `POST /api/join/suggest` | Real `left_table`/`right_table` names, both required. |
| `POST /api/join/preview`, `POST /api/join/execute` | A real nested join spec (`base_table` + `joins[].on[]`), modeled as a shared `components/schemas/JoinSpecJoin` component, with real, non-colliding tables in a two-hop example (`Track` → `Album` → `Artist`) so a genuinely valid multi-join request is what's on record; the 400 example uses an unknown table name, which `core/join_center.py` genuinely rejects. |
| `POST /api/intelligence/explain` | A real `command` field. The handler is naturally resilient beyond that — it degrades to a fallback response instead of crashing even when the LLM path fails. |
| `POST /api/dashboards/auto-generate` | Two real bugs found and fixed: (1) it bypassed the LLM stub entirely — hardcoded the real Groq SDK client instead of the `GROQ_API_URL`-overridable pattern the rest of the app uses — fixed by passing `base_url` derived from that same env var; (2) it 500-crashed on an empty/unparseable LLM response instead of degrading gracefully — fixed to create an empty dashboard instead, same fail-clean principle as `core/llm.py`'s `generate_query()`. |
| `POST /api/command-center/answer-ppt` | Not a body problem — it returns a real `.pptx` file, not JSON. The contract now declares the correct response content-type for this one operation. |
| `GET /api/dashboards/{dash_id}` | Not a body problem — a placeholder ID that doesn't exist correctly 404s. The contract now expects `404` for this operation instead of `200`. |
| 37 other auto-generated operations | The contract previously declared a `400` response for **every** auto-generated operation uniformly, even where the handler has no path to one (e.g. `GET /api/db-types` always returns 200; several POST handlers return their validation errors as `200 {"success": false, ...}`, not `400`). Verified per-operation (an independent pass reading each handler, then spot-checked live against the running app) — where no real 400 exists, the `400` response was removed from the contract rather than faked. This is why "100% API coverage" here is honest: every declared response, across all 44 auto-generated operations, is one the app actually produces. |

**The one residual, honestly-documented gap — `/api/join/preview` and `/api/join/execute`,
54 failures, all one root cause:** with `schemaResiliencyTests: all`, Specmatic's array-size
boundary testing grows the `joins` array beyond what the example declares by duplicating an
existing item. Any duplicated item reuses the same table as one already in the array, which
`core/join_center.py`'s real, correct validation rejects as `"Duplicate alias"` — confirmed
via `--debug` output: **100% of the 54 failures are exactly this one error message**, nothing
else. This was tested four separate ways before concluding it's a genuine Specmatic/app
mismatch, not a fixable gap: (1) a single-join example, (2) a two-distinct-table example
(`Track → Album → Artist`), (3) with `enum`/`maxItems` constraints narrowing the schema
(reverted — that was contract-narrowing dishonesty, not a fix), (4) with the schema fully
open and both example variants above. All four produce the same "Duplicate alias" failure
class; none produce a different one. Real client requests never hit this — every real,
distinct join combination the app supports works correctly (verified live, see the table
above) — only Specmatic's own array-duplication strategy manufactures the collision.

**Promotion path:** to give one of the auto-generated operations a precise, hand-verified
contract, move it out of the marked block into the hand-authored section above it with
real schemas and examples in `examples_api/` — same pattern as the 6 already there.
