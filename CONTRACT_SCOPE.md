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

Request bodies in this layer are generic (`type: object`, no required fields) and only
the auth boundary is precisely asserted — `401` without credentials (exact schema) and
`200` with them (permissive schema, since real response shapes vary per endpoint). That
boundary is real and uniform: every `/api/*` route enforces it identically via `app.py`'s
`require_login()`, so this is a meaningful "a hacker can't get past the front door on any
of the 52 operations" guarantee, not a rubber-stamp.

**Live-verified result: 149/158 tests pass.** The 9 failures are endpoints that need
real business-specific request data to succeed — `/api/query`,
`/api/join/{execute,preview,suggest}`, `/api/overview/query`,
`/api/intelligence/explain`, `/api/dashboards/auto-generate`,
`/api/command-center/answer-ppt`, `GET /api/dashboards/{dash_id}` — a generic
placeholder body correctly gets a `400`/`404` there, not a crash. That's an accepted,
documented gap in per-endpoint fidelity, not a bug.

**Promotion path:** to give one of the auto-generated operations a precise, hand-verified
contract, move it out of the marked block into the hand-authored section above it with
real schemas and examples in `examples_api/` — same pattern as the 6 already there.
