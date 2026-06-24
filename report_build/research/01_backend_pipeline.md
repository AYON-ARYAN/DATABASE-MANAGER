# Meridian Data — Backend Pipeline (Technical Writeup)

*Scope of this document:* the Flask backend of **Meridian Data**, an AI-powered
natural-language-to-query database explorer. Covers application bootstrap and
routing, the end-to-end query flow (intent → hardcoded commands → LLM SQL
generation → validation → execution), dual-provider LLM management, usage
telemetry, key functions/classes, and pseudocode for the central algorithms.

All claims below are grounded in the source. File:line citations use the form
`file.py:NN`. Model names, route paths, and config keys are quoted verbatim.

---

## 1. Application Bootstrap & Routing

### 1.1 `start.py` — the launcher (Docker orchestrator)

`start.py` is **not** the Flask entry point; it is a one-shot CLI launcher that
brings up the whole stack via Docker Compose. Constants (`start.py:24-26`):

- `FRONTEND_URL = "http://localhost:8080"`
- `BACKEND_URL  = "http://localhost:5001"`
- `READY_TIMEOUT_SEC = 180`

CLI flags (`start.py:212-227`): no flag = build + start + open browser;
`--rebuild` forces image rebuild; `--stop` runs `docker compose down`;
`--logs` tails logs. Notable behaviors:

- `resolve_compose_cmd()` (`start.py:38-59`) detects `docker compose` vs legacy
  `docker-compose`, exiting with guidance if neither works.
- `ensure_docker_running()` (`start.py:100-127`) auto-launches Docker
  Desktop/OrbStack/Rancher on macOS or Docker Desktop on Windows, then polls the
  daemon for up to 120 s.
- `ensure_env_file()` (`start.py:130-140`) copies `.env.example` → `.env` (or
  writes an empty `GROQ_API_KEY=`) if `.env` is missing.
- `cmd_up()` (`start.py:179-200`) brings services up detached (`up -d --build`),
  polls `BACKEND_URL` and `FRONTEND_URL` for readiness via
  `wait_until_ready()` / `is_url_ready()` (`start.py:143-167`), then opens the
  browser. Note: both the `rebuild` and non-rebuild branches append `--build`
  (`start.py:183-186`), so an image build always runs.

### 1.2 `app.py` — the Flask application

The Flask app is constructed at `app.py:42-48`:

```python
app = Flask(__name__,
            static_folder='meridian-frontend/dist/assets',
            static_url_path='/assets')
app.secret_key = "dev-secret-key"
app.config["SESSION_PERMANENT"] = False
```

The app serves a compiled React SPA's assets from `meridian-frontend/dist/assets`
at `/assets`. The dev entry point is the bottom of the file:
`app.run(debug=True, port=5001)` (`app.py:2784-2785`) — i.e. **port 5001, debug
on**, matching `BACKEND_URL` in the launcher.

Bootstrap sequence on import:

1. `load_dotenv()` (`app.py:37`); `GROQ_API_KEY` read from env, and
   `analysis_enabled = bool(GROQ_API_KEY)` (`app.py:51-52`) — this flag gates all
   Groq-only "AI Ask"/analysis features. `PAGE_SIZE = 50` (`app.py:54`).
2. `ensure_default_sqlite()` (`app.py:57`) guarantees a "Default SQLite"
   connection exists.
3. The React JSON API blueprint is registered: `from api_routes import api as
   api_blueprint; app.register_blueprint(api_blueprint)` (`app.py:60-61`).
4. Optional CORS for dev: `CORS(app, supports_credentials=True,
   origins=["http://localhost:5173"])`, guarded by `try/except ImportError`
   (`app.py:64-68`).

There are **two parallel route surfaces**: the server-rendered Jinja routes in
`app.py` (templates such as `index.html`, `review.html`, `admin.html`) and the
JSON API blueprint in `api_routes.py` (all paths prefixed `/api/...`). The React
SPA consumes the latter; the former is the legacy/templated UI. The two share
identical logic, duplicated by hand (same `USERS`, `ROLE_PERMISSIONS`,
`paginate_sql`, `safe_count`, hardcoded command handlers, etc.).

### 1.3 Sessions, Authentication, RBAC

**Demo accounts** are hardcoded in-memory (`app.py:74-87`, duplicated in
`api_routes.py:33-37`). Passwords are stored as Werkzeug hashes
(`generate_password_hash`) and verified with `check_password_hash`:

| Username  | Password    | Role     |
|-----------|-------------|----------|
| `viewer1` | `viewer123` | `VIEWER` |
| `editor1` | `editor123` | `EDITOR` |
| `admin1`  | `admin123`  | `ADMIN`  |

**Roles & permission matrix** (`app.py:93-101`):

```python
ROLE_PERMISSIONS = {
    "VIEWER": {"READ", "SYSTEM"},
    "EDITOR": {"READ", "WRITE", "SYSTEM"},
    "ADMIN":  {"READ", "WRITE", "SCHEMA", "SYSTEM"},
}
```

`is_allowed(role, task)` (`app.py:111-112`) is a simple set-membership check.
Tasks are the five classes produced by `classify_query` (READ, WRITE, SCHEMA,
SYSTEM, UNKNOWN — see §2.5).

**Auth guard** — `@app.before_request require_login()` (`app.py:192-208`):
- Allows `/login`, `/static`, `/assets`, `/favicon.ico` unconditionally.
- Allows `/app` and `/app/...` (React SPA self-authenticates via the API).
- Allows `/api/auth/login` and `/api/auth/session` pre-login.
- Otherwise, if `session["logged_in"]` is falsy: returns **JSON 401** for
  `/api/*` and `/admin/*`, else redirects to the `login` view.

**Login** (`app.py:214-232`) validates credentials, then on success does
`session.clear()` and sets `logged_in`, `username`, `role`, and
`active_db = "Default SQLite"`. `logout` (`app.py:235-238`) clears the session.
The API equivalents are `POST /api/auth/login`, `POST /api/auth/logout`,
`GET /api/auth/session` (`api_routes.py:111-144`).

Session is the single source of truth for per-user state: `active_db`,
`llm_provider`, `history` (last 10 commands, `add_to_history` at `app.py:141-153`),
`conversation_context` (last 5 NL/SQL turns), and transient query state
(`last_sql`, `last_read_sql`, `last_task`, `last_explanation`,
`last_read_columns`). Rows are deliberately **not** stored in the session to
avoid the "Cookie too large" problem (`app.py:714-716`); CSV/PPT export re-runs
the stored SQL on demand.

**Admin-only routes** check `session["role"] == ROLE_ADMIN` explicitly: `/admin`
dashboard (`app.py:959-971`), `/admin/llm/config`, `/admin/ollama/pull`,
`/admin/test_llm`, snapshot create/restore/delete, `/undo`, and the API
`/api/admin/metrics` (`api_routes.py:569-580`).

---

## 2. End-to-End Query Flow

The query pipeline is implemented twice with identical semantics: the templated
`index()` POST handler (`app.py:244-751`) and the JSON `POST /api/command`
handler (`api_routes.py:213-433`). The description below cites both.

Pipeline stages: **(A)** normalize input → **(B)** hardcoded DBMS command match
(bypasses LLM) → **(C)** `show tables` SYSTEM shortcut → **(D)** LLM query
generation with full schema/context → **(E)** classification + RBAC gate →
**(F)** safety/validation gate → **(G)** execute (READ/SYSTEM) or route to review
(WRITE/SCHEMA) → **(H)** AI-Ask fallback when SQL fails.

### 2.1 Input normalization & adapter selection

The active adapter is resolved from `session["active_db"]` via
`get_active_adapter()` (`app.py:156-164`), which falls back to "Default SQLite"
on error. `dialect = adapter.dialect` and `cmd_lower = user_cmd.lower().strip()`
drive subsequent matching (`app.py:265-267`).

### 2.2 Intent / Command detection

Intent detection happens in **two distinct layers**:

**(a) Deterministic string-prefix matching in the request handler** (the real
routing). The handler inspects `cmd_lower` against fixed prefixes/exact strings
to detect "hardcoded" introspection commands before ever calling an LLM
(`app.py:269-559`). This is the actual intent classifier used at runtime.

**(b) `core/intelligence.py` — `CommandIntelligence`** (an LLM-based *semantic
explainer*, used for the in-app command guide, **not** in the hot query path).
`explain_intent(user_cmd, dialect)` (`intelligence.py:14-75`) prompts an LLM to
return strict JSON with: `summary`, `task` (READ/WRITE/SCHEMA/SYSTEM), `impact`
(LOW/MEDIUM/HIGH), `permissions` (which roles), and a `sql_pattern` example.
- Groq path: model `"llama-3.3-70b-versatile"`, `temperature: 0.1`,
  `response_format: {"type": "json_object"}`, 10 s timeout
  (`intelligence.py:36-54`).
- Ollama/Mistral path: `POST http://localhost:11434/api/generate`, model
  `"mistral"`, `format: "json"`, 15 s timeout, with a hardcoded fallback dict on
  failure (`intelligence.py:56-75`).

`get_canonical_commands()` (`intelligence.py:77-96`) returns the documented
command catalogue used by the UI guide — it explicitly labels which commands are
"hardcoded (bypass LLM)" vs "uses LLM."

### 2.3 Hardcoded DBMS commands (LLM bypass)

These are matched by literal string prefix/equality and answered directly from
adapter introspection methods — no LLM call. **Rationale (stated in code,
`app.py:269-271`): reliability** — schema introspection must always work,
deterministically, regardless of LLM availability or hallucination. They are
treated as SYSTEM-task results and recorded with status `"EXECUTED"`.

| Command (prefix / exact) | Adapter method | What it returns | Source |
|---|---|---|---|
| `describe <t>` / `desc <t>` / `show structure <t>` / `show columns <t>` / `show schema <t>` | `describe_table()` | columns (name, type, NOT NULL, default, PK) + FK rows + index rows + row count | `app.py:273-327` |
| `show foreign keys` (+ aliases: `list foreign keys`, `show fk(s)`, `show relationships`, `show refs`, `show references`) | `get_foreign_keys()` | all FK relationships (From/To table+column) | `app.py:329-352` |
| `show foreign keys for <t>` (+ `show fk for`, `show fks for`, `show references for`, `show refs for`) | `describe_table()` (FKs subset) | FKs for one table | `app.py:354-390` |
| `show indexes` (+ `list indexes`, `show index`, `show indices`) | `get_indexes()` | all indexes (table, name, unique, columns) | `app.py:392-415` |
| `show table counts` (+ `show row counts`, `count all tables`, `table sizes`) | `list_tables()` + per-table `SELECT COUNT(*)` | row count per table | `app.py:417-449` |
| `show constraints` (+ `list constraints`, `show all constraints`) | `get_constraints()` | all PK/FK/NOT NULL/UNIQUE constraints | `app.py:451-481` |
| `show create table <t>` (+ `show ddl <t>`, `show sql <t>`) | `get_create_table()` | the DDL/`CREATE TABLE` statement | `app.py:483-516` |
| `show tables` / `list tables` / `show collections` / `list collections` | `list_tables()` | table/collection list (RBAC-gated: requires SYSTEM) | `app.py:522-559` |

Each handler is guarded with `hasattr(adapter, '<method>')` so adapters lacking a
given introspection capability simply fall through. The identical set is
reproduced in the API at `api_routes.py:225-357`.

`show tables` is the only hardcoded command behind an explicit RBAC check
(`is_allowed(role, "SYSTEM")`, `app.py:524`); the structural-introspection
commands above it are not separately permission-checked in the handler.

### 2.4 LLM query generation (`core/llm.py`)

If no hardcoded command matches, the handler builds the schema string and calls
the LLM (`app.py:561-567`):

```python
schema = adapter.get_schema()
conversation_context = session.get("conversation_context", [])
query, explanation = generate_query_with_explanation(
    user_cmd, dialect, schema, llm_provider, history=conversation_context)
```

**Schema injection.** `adapter.get_schema()` produces a rich plain-text schema.
For SQLite (`core/adapters/sqlite_adapter.py:58-120`) it emits, per table:
- `TABLE <name>:` header;
- each column as `- name (TYPE NOT NULL DEFAULT x [PRIMARY KEY])` via
  `PRAGMA table_info` (`sqlite_adapter.py:72-78`);
- a `FOREIGN KEYS:` block (`col -> other.col`) via `PRAGMA foreign_key_list`
  (`sqlite_adapter.py:80-86`);
- an `INDEXES:` block (with UNIQUE marker, columns) via `PRAGMA index_list` +
  `PRAGMA index_info` (`sqlite_adapter.py:88-98`);
- a `SAMPLE DATA (N rows):` block of up to **3 sample rows** (`SELECT * ... LIMIT
  3`), skipping BLOB/binary columns and truncating each value to 60 chars
  (`sqlite_adapter.py:100-118`).

The other adapters (mysql, postgres, mssql, oracle, mongo, cassandra, redis)
implement `get_schema()` with the same FOREIGN KEYS / INDEXES / SAMPLE DATA
structure using dialect-appropriate catalog queries (e.g. `sys.foreign_key_columns`
for MSSQL, `user_indexes` for Oracle, `find().limit(5)` for Mongo). This means
the LLM prompt always carries columns, types, PKs, FKs, indexes, and live sample
rows.

**Dialect-aware prompting.** `core/llm.py` holds a `PROMPT_TEMPLATES` dict
(`llm.py:23-181`) keyed by dialect — `sqlite`, `mysql`, `postgresql`, `mssql`,
`oracle`, `mongodb`, `cassandra`, `redis`. Each template embeds `{schema}` and
hard rules tuned per engine, e.g.:
- SQLite/MySQL/PostgreSQL: "Output ONLY valid <engine> SQL", "always include
  `LIMIT 50` unless user specifies otherwise", "Pay close attention to FOREIGN
  KEYS and SAMPLE DATA to write accurate JOINs", PRAGMA hints for introspection
  (SQLite only).
- MSSQL: "Use `TOP N` instead of `LIMIT`", `[]` identifiers, `TOP 50` default.
- Oracle: "Use `FETCH FIRST N ROWS ONLY`", `FETCH FIRST 50 ROWS ONLY` default.
- MongoDB / Redis: output **must be a JSON object** with a prescribed operation
  schema (operation/collection/filter/pipeline… for Mongo; command/args or a
  `commands` array for Redis).
- Universal rules across SQL dialects: "Use ONLY tables and columns shown above",
  "NEVER output plain text… GENERATE THE SQL", "No markdown/code fences", "use
  `IS NULL` (not `= ''`) for blank values".

`_get_system_prompt(dialect, schema)` (`llm.py:201-204`) selects the template
(falling back to `sqlite`) and injects `DATABASE SCHEMA:\n{schema}`.

**Generation + provider fallback.** `generate_query()` (`llm.py:257-296`):
1. Loads provider config (`llm_manager.load_config()` and `get_active_config()`).
2. Builds the system context (template+schema) and a flattened
   `CONVERSATION HISTORY` string from prior turns plus the new `USER COMMAND`.
3. Builds an ordered fallback **chain**: if the requested provider is `mistral`,
   chain = `[mistral, groq]`; otherwise `[groq, mistral]` (`llm.py:278-281`).
4. Iterates the chain: `_call_groq` (`llm.py:210-234`) sends a proper
   `system + history + user` `messages` array to the Groq Chat Completions API
   at `temperature=0.1`, 60 s timeout, and logs the call to metrics;
   `_call_ollama` (`llm.py:237-254`) posts the flattened `full_prompt` to Ollama
   (`stream:false`, options `num_thread:4, num_ctx:2048, temperature:0.1`) and
   logs metrics. The **first provider to succeed wins**; on exhaustion it returns
   `"ERROR: all providers failed (...)"` (`llm.py:296`). This gives automatic
   cloud↔local failover.
5. `clean_sql()` (`llm.py:184-199`) strips ```` ``` ```` fences, stray backticks,
   whitespace, and a trailing `;` from the model output.

**Single-call query + explanation.** `generate_query_with_explanation()`
(`llm.py:299-363`) is the function the handlers actually call. As an optimization
it asks the model for **one** structured response in the form
`QUERY: <raw>` / `EXPLANATION: <bullets>` (`llm.py:317-326`), then
case-insensitively partitions the text on `query:` / `explanation:`
(`llm.py:344-361`) into `(query, explanation)`. If the structure is missing it
treats the whole output as the query. It limits output with
`options={"num_predict": 512}`.

**Conversation context.** After generation the handler appends
`{"user": user_cmd, "assistant": query}` to `session["conversation_context"]`,
pruning to the **last 5 turns** (`app.py:569-573`, `api_routes.py:368-371`). This
context is replayed into every subsequent prompt, enabling follow-up/refinement
queries. The `/refine` route (`app.py:859-907`) reuses this by feeding
`REFINE THIS QUERY:\n<sql>\n\nUSER FEEDBACK: <fb>` back through the same function.

### 2.5 Classification & RBAC gate

`classify_query(query, dialect)` (`core/validator.py:108-182`) maps generated
output to a task class:
- **MongoDB:** parses JSON, maps `find/aggregate/count` → READ, the `insert*/
  update*/delete*` ops → WRITE, else UNKNOWN (`validator.py:117-128`).
- **Redis:** parses JSON, classifies by command against `READ_CMDS`/`WRITE_CMDS`
  sets; a multi-command batch is WRITE if any step writes (`validator.py:131-158`).
- **SQL dialects:** `SYSTEM` if it starts with an introspection prefix
  (`show tables`, `describe `, `pragma `, `\d`, etc.) or contains metadata-table
  keywords (`sqlite_master`, `information_schema`, `pg_catalog`, `sys.tables`…);
  `READ` for `select`; `WRITE` for `insert/update/delete`; `SCHEMA` for
  `create/alter/drop`; else `UNKNOWN` (`validator.py:160-182`).

The RBAC gate (`app.py:575-593`): compute `task`, then derive an
`effective_task`. **Special rule:** an `UNKNOWN` result is promoted to `READ` for
ADMIN/EDITOR **only if it also passes the safety check** (`app.py:580-581`) —
this lets non-SQL "answer-style" LLM output flow into the AI-Ask fallback rather
than being hard-blocked. If `is_allowed(role, effective_task)` is false, the
command is logged as `"BLOCKED (ROLE)"` and rejected.

### 2.6 Validation/safety gate (`is_safe`)

`is_safe(query, dialect)` (`core/validator.py:42-102`) is the destructive-action
firewall, evaluated before any READ executes and again in `/execute`:
- **NoSQL:** rejects `NOSQL_DANGEROUS` tokens (`dropDatabase`, `FLUSHALL`,
  `CONFIG`, `SHUTDOWN`, `SLAVEOF`…); for Mongo, also parses JSON and blocks any
  `drop*` operation; invalid JSON is unsafe (`validator.py:49-64`).
- **SQL:** rejects `SQL_DANGEROUS` substrings (`drop `, `truncate `, `alter `,
  `shutdown`, `attach `, `detach `, `pragma `, and comment tokens `--`, `/*`,
  `*/`) and **blocks statement stacking via any `;`** (`validator.py:68-74`).
- Then allowlists: `SELECT` → safe; `insert/update/delete` → safe; SYSTEM-classified
  → safe.
- **Permissive text fallback** (`validator.py:88-95`): if the string contains
  none of `(; -- /* */ xp_ drop truncate alter)`, it is deemed "safe enough" to
  display as text — this is what lets a plain-English LLM answer pass through to
  the AI-Ask path rather than erroring.

### 2.7 Execution & pagination

READ/SYSTEM (or safe-UNKNOWN-as-READ) queries execute immediately
(`app.py:596-735`):
- NoSQL: executed directly, no pagination.
- System queries (`is_system_query`: contains `sqlite_master`/`pragma`/
  `information_schema`) or already-limited queries (`is_already_limited`: contains
  ` limit `/` offset `): executed as-is.
- Otherwise: `paginate_sql(sql, page)` wraps with `LIMIT 50 OFFSET (page-1)*50`
  (`app.py:125-128`), and `safe_count()` (`app.py:131-138`) wraps the original
  SQL in `SELECT COUNT(*) FROM (<sql>) AS subq` to get a total for the paginator
  (skipped for system/limited queries). `PAGE_SIZE = 50`.

Results render to `index.html` (templated) or return as JSON
`{task, sql, explanation, columns, results, page, page_size, total_rows}` (API).

### 2.8 WRITE / SCHEMA → human review

WRITE/SCHEMA queries are **never auto-executed**. They are stashed in
`session["last_sql"]`/`last_task`/`last_explanation`, logged as
`"PENDING REVIEW"`, and rendered on `review.html` (`app.py:737-751`); the API
returns `{"needs_review": True, sql, explanation, task}`
(`api_routes.py:426-433`). The user then confirms via `POST /execute`
(`app.py:910-940`) / `POST /api/execute` (`api_routes.py:467-489`), which:
re-checks `is_allowed` **and** `is_safe`; takes an automatic **snapshot**
(`take_snapshot`) before WRITE/SCHEMA; for `DELETE`, calls
`adapter.preview_delete(query)` first; then executes. A separate `POST /dry-run`
(`app.py:843-856`) lets the adapter validate a statement without committing.

### 2.9 AI-Ask fallback (`core/analyzer.py: ai_ask`)

When a READ path raises during execution, the handler attempts a graceful
fallback to a direct natural-language answer — but **only when `analysis_enabled`
(a Groq key is present)** (`app.py:629-712`, `api_routes.py:402-415`):

- For a safe-UNKNOWN treated as READ, it calls `ai_ask(...)` immediately
  (`app.py:632-665`).
- For a genuinely failed SQL statement, it retries via `ai_ask` only when the
  error text contains `"syntax"` or `"no such"` (`app.py:677-699`).
- If `ai_ask` is unavailable/fails, it degrades to displaying the raw LLM text in
  an "Intelligence Response" / "Execution failed" panel.

`ai_ask(question, schema, db_name, table_stats=None, dialect="sqlite",
fk_info=None)` (`core/analyzer.py:123-212`) uses the module-level
`GROQ_CLIENT` (Groq SDK, initialised at `analyzer.py:14-18`; `None` if no key).
It builds a teaching-assistant prompt embedding the **full schema (with PKs, FKs,
indexes, sample data)**, optional table statistics, optional FK list, and a
dialect name map (`analyzer.py:145-184`); calls model
`"llama-3.3-70b-versatile"` at `temperature=0.3`; and parses the response into
`{"answer": <markdown>, "suggested_queries": [...]}` by splitting on a literal
`---SUGGESTED_QUERIES---` marker that the model is told to emit
(`analyzer.py:196-209`). The rest of `analyzer.py` provides related Groq-backed
features (`analyze_data`, `analyze_schema`, full async analysis jobs) all on the
same model.

---

## 3. LLM Provider Management (`core/llm_manager.py`)

A tiny JSON-file-backed config layer for the dual provider setup.

- **Config file:** `LLM_CONFIG_FILE = "db/llm_config.json"` (`llm_manager.py:5`).
- **`DEFAULT_CONFIG`** (`llm_manager.py:7-20`):
  - `active_provider: "mistral"` (i.e. local Ollama is the default).
  - `providers.groq`: `{api_key: <env GROQ_API_KEY>, model:
    "llama-3.3-70b-versatile", url:
    "https://api.groq.com/openai/v1/chat/completions"}`.
  - `providers.mistral`: `{model: "mistral", url:
    "http://localhost:11434/api/generate"}` (Ollama).
- **Persistence:** `load_config()` reads the JSON (returns `DEFAULT_CONFIG` if
  the file is missing or unparseable); `save_config()` writes it pretty-printed,
  creating `db/` if needed (`llm_manager.py:22-34`).
- **Active selection:** `get_active_config()` returns
  `(active_provider, providers[active_provider])` (`llm_manager.py:36-39`).
- **Ollama model ops:** `list_local_models()` GETs
  `http://localhost:11434/api/tags` (5 s) and returns the `models` list;
  `pull_ollama_model(name)` POSTs to `…/api/pull` with `stream:false` (300 s) and
  returns a boolean (`llm_manager.py:42-57`).

**Two notions of "active provider" coexist.** The per-session UI toggle is
`session["llm_provider"]` (set by `POST /set_llm_provider` (`app.py:945-953`) /
`POST /api/set-provider` (`api_routes.py:495-502`); only `"mistral"`/`"groq"`
accepted), and this session value is what the handlers pass into
`generate_query_with_explanation`. The file-based `active_provider` in
`llm_config.json` is the global default consulted inside `generate_query` when no
provider is passed, and managed by Admins.

**Admin model switching** (`/admin/llm/config`, `app.py:974-995`): merges posted
`active_provider` and per-provider field updates into the config and saves —
this is how the Groq API key, model name, or default provider are persisted.
`/admin/ollama/pull` (`app.py:998-1008`) pulls a new local model;
`/admin/test_llm` (`app.py:1011-1027`) runs a one-off generation against a dummy
schema `TEST_TABLE(col_a, col_b)` for diagnostics.

> **Naming caveat for the report:** internally the local provider is keyed
> `"mistral"` and the cloud provider `"groq"`. The Groq cloud model is
> `llama-3.3-70b-versatile` (a Llama-3.3 model served by Groq), while the local
> Ollama model is literally `mistral`. So "mistral" = local Ollama; "groq" =
> cloud Llama-3.3.

---

## 4. Usage Metrics / Telemetry (`core/metrics.py`)

A flat-file telemetry log of every LLM call.

- **File:** `METRICS_FILE = "db/usage_metrics.json"` (`metrics.py:6`) — a JSON
  array of entries.
- **`log_call(provider, model, latency, prompt_tokens=0, completion_tokens=0)`**
  (`metrics.py:8-37`): appends one entry with `timestamp` (ISO), `provider`,
  `model`, `latency` (rounded to 3 dp), `prompt_tokens`, `completion_tokens`, and
  computed `total_tokens`. It self-trims to the **last 1000 entries** for
  performance (`metrics.py:33-34`). Called inside both `_call_groq`
  (`llm.py:232-233`, using Groq's `usage.prompt_tokens`/`completion_tokens`) and
  `_call_ollama` (`llm.py:252-253`, using Ollama's
  `prompt_eval_count`/`eval_count`).
- **`get_summary()`** (`metrics.py:39-79`) powers the admin dashboard:
  - `total_calls`, `avg_latency` (mean latency over all entries), `total_tokens`.
  - `calls_by_provider`: per-provider call counts.
  - `trends`: from the **last 50 calls** — time labels (`HH:MM:SS`), plus
    per-provider token and latency series split into `groq_*`/`mistral_*` arrays
    (suitable for charting).
  - `recent_history`: the last 20 entries.

Surfaced through `/admin` (`app.py:965`) and `GET /api/admin/metrics`
(`api_routes.py:569-580`), both Admin-gated.

---

## 5. Key Functions / Classes & Responsibilities

| Symbol | File:line | Responsibility |
|---|---|---|
| `app` (Flask) | `app.py:42-48` | App object; serves SPA assets; `secret_key`; non-permanent sessions |
| `require_login()` | `app.py:192-208` | Global before-request auth guard (JSON 401 for API, redirect for HTML) |
| `login()` / `logout()` | `app.py:214-238` | Credential check + session setup/teardown |
| `index()` | `app.py:244-808` | The templated query pipeline (POST) + pagination (GET) |
| `is_allowed()` | `app.py:111-112` | RBAC set-membership check |
| `is_system_query/is_already_limited/paginate_sql/safe_count` | `app.py:115-138` | Pagination + count helpers |
| `add_to_history()` | `app.py:141-153` | Maintains last-10 command history in session |
| `get_active_adapter()` | `app.py:156-164` | Resolves DB adapter for the session, with default fallback |
| `execute()` | `app.py:910-940` | Executes reviewed WRITE/SCHEMA after re-checking perms+safety; snapshots first |
| `refine_query()` | `app.py:859-907` | Re-prompts the LLM with prior SQL + feedback |
| `admin()` / `update_llm_config()` / `pull_model()` | `app.py:959-1008` | Admin metrics + provider config + model pull |
| `api` (Blueprint) | `api_routes.py:28` | JSON API surface for the React SPA |
| `api_command()` | `api_routes.py:213-433` | JSON twin of `index()` POST pipeline |
| `_join_guard()` | `api_routes.py:653-669` | Preflight for `/api/join/*` (auth, READ perm, dialect support) |
| `generate_query()` | `llm.py:257-296` | Provider-fallback generation core |
| `generate_query_with_explanation()` | `llm.py:299-363` | Single-call query+explanation (the handler entry point) |
| `_call_groq()` / `_call_ollama()` | `llm.py:210-254` | Provider transports; emit metrics |
| `clean_sql()` | `llm.py:184-199` | Strips fences/backticks/`;` from LLM output |
| `_get_system_prompt()` + `PROMPT_TEMPLATES` | `llm.py:23-204` | Dialect-aware system prompt assembly |
| `CommandIntelligence.explain_intent()` | `intelligence.py:14-75` | LLM semantic intent explainer (guide, not hot path) |
| `CommandIntelligence.get_canonical_commands()` | `intelligence.py:77-96` | Command catalogue for the UI guide |
| `classify_query()` / `is_safe()` | `validator.py:42-182` | Task classification + destructive-action firewall |
| `load_config/save_config/get_active_config` | `llm_manager.py:22-39` | Provider config persistence |
| `list_local_models/pull_ollama_model` | `llm_manager.py:42-57` | Ollama model management |
| `log_call()` / `get_summary()` | `metrics.py:8-79` | Telemetry write + dashboard aggregation |
| `ai_ask()` | `analyzer.py:123-212` | Groq NL Q&A fallback with full schema context |
| `SQLiteAdapter.get_schema()` | `sqlite_adapter.py:58-120` | Builds schema text (cols, PKs, FKs, indexes, 3 sample rows) |

---

## 6. Algorithms as Pseudocode

### 6.1 Query routing (the central dispatcher)

```
function handle_command(user_cmd, session):
    adapter  = get_active_adapter(session)        # dialect-specific
    dialect  = adapter.dialect
    cmd      = lowercase(strip(user_cmd))
    role     = session.role

    # (B) Hardcoded introspection — deterministic, no LLM
    if cmd starts-with any DESCRIBE_PREFIX:
        return render(adapter.describe_table(table))          # SYSTEM
    if cmd in SHOW_FK_ALIASES:        return render(adapter.get_foreign_keys())
    if cmd starts-with FK_FOR_PREFIX: return render(adapter.describe_table(t).fks)
    if cmd in SHOW_INDEXES_ALIASES:   return render(adapter.get_indexes())
    if cmd in TABLE_COUNT_ALIASES:    return render(count_each_table(adapter))
    if cmd in CONSTRAINT_ALIASES:     return render(adapter.get_constraints())
    if cmd starts-with CREATE_TABLE_PREFIX: return render(adapter.get_create_table(t))

    # (C) SYSTEM shortcut (RBAC-gated)
    if cmd in {show tables, list tables, show/list collections}:
        if not is_allowed(role, "SYSTEM"): return error("Permission denied")
        return render(adapter.list_tables())

    # (D) LLM generation with full context
    schema  = adapter.get_schema()                # cols + PKs + FKs + idx + samples
    history = session.conversation_context        # last 5 turns
    (query, explanation) = generate_query_with_explanation(
                               user_cmd, dialect, schema, session.llm_provider, history)
    push (user_cmd, query) into history; keep last 5

    # (E) classify + RBAC
    task = classify_query(query, dialect)
    effective = task
    if task == UNKNOWN and role in {ADMIN, EDITOR} and is_safe(query, dialect):
        effective = READ
    if not is_allowed(role, effective):
        return error(role + " not allowed to run " + task)

    # (F)+(G) safety + execute, or (H) review
    if task in {READ, SYSTEM} or (task == UNKNOWN and effective == READ):
        if not is_safe(query, dialect): return error("Unsafe query blocked")
        try:
            rows, cols, total = execute_with_pagination(adapter, query, page=1)
            return render(rows, cols, total, query, explanation)
        except ExecError as e:
            return ai_ask_fallback(user_cmd, schema, dialect, e)   # only if Groq enabled
    else:   # WRITE / SCHEMA
        stash query/task/explanation in session; log "PENDING REVIEW"
        return render_review_page(query, explanation, task)
```

### 6.2 Provider-fallback generation

```
function generate_query(user_cmd, dialect, schema, provider, history):
    cfg     = load_config()
    provider = provider or cfg.active_provider          # session value or file default
    context = system_prompt(dialect, schema)            # template + schema injection
    full    = context + flatten(history) + "USER COMMAND: " + user_cmd

    chain = (provider == "mistral") ? [mistral, groq] : [groq, mistral]
    errors = []
    for (name, pcfg) in chain:
        try:
            if name == "groq":
                if not pcfg.api_key: raise "no key"
                out = POST Groq(messages=[system, ...history..., user], temp=0.1)
            else:
                out = POST Ollama(prompt=full, temp=0.1, num_ctx=2048)
            log_call(name, model, latency, prompt_tokens, completion_tokens)
            return clean_sql(out)                       # first success wins
        except e:
            errors.append(name + ": " + e)              # fall through to next provider
    return "ERROR: all providers failed (" + join(errors) + ")"
```

### 6.3 Validation gate (`is_safe`, SQL path)

```
function is_safe(query, dialect):
    q = lower(strip(query))
    if dialect in {mongodb, redis}:
        if any NOSQL_DANGEROUS token in q: return false
        if mongodb: parse JSON; if "drop" in operation: return false; if invalid JSON: return false
        return true
    # SQL dialects
    for kw in {drop , truncate , alter , shutdown, attach , detach , pragma , --, /*, */}:
        if kw in q: return false
    if ";" in query: return false                       # block statement stacking
    if q starts-with "select":                 return true
    if q starts-with {insert, update, delete}: return true
    if classify_query(query, dialect) == SYSTEM: return true
    # permissive text fallback (lets plain-English AI answers display)
    if no token from {; -- /* */ xp_ drop truncate alter} in q: return true
    return false
```

### 6.4 Task classification (`classify_query`, SQL path)

```
function classify_query(query, dialect):
    q = lower(strip(query))
    if dialect == mongodb: return by-operation(find/aggregate/count=READ; insert*/update*/delete*=WRITE)
    if dialect == redis:   return by-command(READ_CMDS / WRITE_CMDS; batch=WRITE if any write)
    if q starts-with SYSTEM_PREFIXES (show tables, describe, pragma, \d, ...): return SYSTEM
    if q contains {sqlite_master, information_schema, pg_catalog, sys.tables}: return SYSTEM
    if q starts-with "select":                 return READ
    if q starts-with {insert, update, delete}: return WRITE
    if q starts-with {create, alter, drop}:    return SCHEMA
    return UNKNOWN
```

---

## 7. Notable Implementation Facts (report-worthy)

- **Two-layer safety:** RBAC (role→task set) **and** a keyword/structure firewall
  (`is_safe`) run independently; WRITE/SCHEMA additionally require explicit human
  confirmation through a review page, and `is_safe`/`is_allowed` are re-checked at
  execution time.
- **Determinism for introspection:** structural commands (`describe`, `show
  foreign keys`, `show indexes`, etc.) bypass the LLM entirely and read from
  adapter introspection, guaranteeing correctness independent of model quality.
- **Resilience:** cloud↔local LLM failover (`generate_query`), plus an AI-Ask
  fallback that answers in natural language when generated SQL errors.
- **Context-aware:** a 5-turn rolling conversation history is replayed into every
  prompt, enabling follow-ups and the `/refine` loop.
- **Multi-dialect by construction:** eight prompt templates and per-adapter
  schema builders cover SQLite, MySQL, PostgreSQL, MSSQL, Oracle, MongoDB,
  Cassandra, Redis — including JSON-shaped output contracts for the NoSQL engines.
- **Privacy/size pragmatism:** result rows are never stored in the session cookie
  (re-fetched for export); metrics file self-caps at 1000 entries.
- **Duplication risk (for the report's limitations section):** `app.py` (templated)
  and `api_routes.py` (JSON) reimplement the same pipeline, RBAC tables, and
  helpers by hand, so the two surfaces can drift.
