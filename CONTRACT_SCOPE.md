# Contract scope — why some endpoints show as "Missing in Spec"

With the actuator enabled, Specmatic now compares the OpenAPI contract against the app's
**actual** routes and flags any live endpoint that the contract doesn't govern as
*Missing in Spec*. Meridian exposes **52 `/api` endpoints**, and the executable contract
deliberately governs a **core subset (6)**. This document records that decision so the gap
is intentional and reviewable, not an oversight.

## What the contract governs (the "public" API surface)

These are the endpoints an external consumer — a frontend, an integrator, or an AI coding
agent — depends on for the **core NL-to-SQL + human-in-the-loop write-safety flow**. They
are the contract because they are the promises other code relies on:

| Method | Path | Why it's in the contract |
|---|---|---|
| POST | `/api/auth/login` | entry point; auth shape is a hard promise |
| GET | `/api/auth/session` | session/authz contract every client checks |
| GET | `/api/connections` | active DB + provider context |
| POST | `/api/command` | **the** NL-to-SQL endpoint (READ / NeedsReview / error union) |
| POST | `/api/execute` | the human-in-the-loop confirm step for writes |
| POST | `/api/undo` | rollback of the last write |

If any of these drift, a consumer breaks — so they are contract-tested at 100% (positive,
resiliency, and 401 paths) on every push.

## What is intentionally out of scope (the 46 "Missing in Spec")

The remaining endpoints power the **web UI's feature surface**. They are consumed by
Meridian's own React frontend (same-origin, same release) rather than by independent
clients, so contract-drift between separately-deployed parties isn't a risk for them. They
fall into clear groups:

- **Command Center (AI insights):** `/api/command-center/*` (kpis, anomalies, deep-ask,
  auto-insights, data-health, smart-ppt, answer-ppt, execute-raw), `/api/ask`,
  `/api/insights`, `/api/intelligence/explain`, `/api/analyze-direct`, `/api/analyze-full`
  (+ status), `/api/overview`, `/api/overview/query`, `/api/er-diagram`.
- **Dashboards:** `/api/dashboards` and `/api/dashboards/{id}[/widgets[/{widget_id}]]`,
  `/api/dashboards/auto-generate`.
- **Join Center:** `/api/join/{schema,suggest,preview,execute}`.
- **Sample databases & schema browse:** `/api/samples`, `/api/samples/install`,
  `/api/db-types`, `/api/create-database`, `/api/tables-list`, `/api/table-preview`,
  `/api/query`.
- **Connection management:** `POST/DELETE /api/connections`, `/api/connections/select`.
- **Snapshots (beyond undo):** `/api/snapshots` (GET/POST), `/api/snapshots/restore`,
  `DELETE /api/snapshots/{id}`.
- **Session / misc:** `/api/auth/logout`, `/api/set-provider`, `/api/command/paginate`,
  `GET /api/admin/metrics`.

### Why not contract them all (yet)

1. **Contracts earn their keep at trust boundaries.** Their value is stopping silent drift
   between *independently* evolving parties. The six core endpoints are that boundary; the
   feature endpoints are internal to one deployable unit (API + its own SPA, shipped together).
2. **Scope honestly, grow deliberately.** Modelling all 52 up front would be a large,
   low-signal spec that's easy to let rot. The actuator makes the gap **visible on every CI
   run**, so endpoints can be promoted into the contract as they stabilise or gain external
   consumers — the list above is the backlog.
3. **No endpoint is hidden.** The actuator publishes the full route table; this file plus the
   report's "Missing in Spec" section are the record. Nothing is undocumented — the choice of
   what to *contract-test* is explicit.

**Promotion path:** to bring one of the above under contract, add its path/schemas to
`api_contract.yaml` (with examples in `examples_api/`), and it moves from "Missing in Spec"
to a covered, tested operation.
