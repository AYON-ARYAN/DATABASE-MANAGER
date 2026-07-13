# Meridian Data

### AI-Powered Database Explorer & DBMS Teaching Tool

Meridian Data is a full-stack database exploration platform that lets you query any database using plain English. It converts natural language into validated SQL, executes queries safely, and generates insights, charts, and presentations — all through a clean, modern dark-mode interface.

Built for students, teachers, and analysts who want to explore databases without writing SQL from scratch.

**Supports**: SQLite, PostgreSQL, MySQL, MSSQL, Oracle, MongoDB, Cassandra, Redis

---

## Spec-Driven Development with Specmatic

Meridian uses **[Specmatic](https://specmatic.io)** executable contracts as a guardrail for
AI-generated code — catching silent API drift, and even **virtualizing the LLM provider** so
AI-dependent tests run offline and token-free.

### The three contracts — what each is and why it exists

| Contract | Describes | Why it exists |
|---|---|---|
| **`api_contract.yaml`** | The full `/api` surface (auth, connections, `command`, `execute`, `undo`), incl. the `/api/command` `oneOf` union (READ result / write-needs-review / error) and `401`s on protected endpoints. | **Single source of truth** for the API. Specmatic uses it to (a) **stub** the backend so the React frontend can develop in parallel, and (b) pin the real shapes (with `examples`) so humans/AI agents can't silently drift them. |
| **`contract_public.yaml`** | The **unauthenticated public surface** (`POST /api/auth/login`, incl. the `400` for malformed input). | This is what runs in **CI**. The full API is behind a Flask **session cookie**, which Specmatic's test mode can't drive (it supports header/bearer/oauth2, not cookies) — so CI tests the cookie-free surface, with inline + external **examples** and **generative resiliency** tests. |
| **`llm_contract.yaml`** | The **upstream LLM provider** Meridian consumes — Groq's OpenAI-compatible `POST /openai/v1/chat/completions`. | Lets Specmatic **stub the LLM** in tests (service virtualization). See [`LLM_CONTRACT_NOTES.md`](./LLM_CONTRACT_NOTES.md) for every deviation from the real OpenAI/Groq spec and why. |

External example files live in [`examples/`](./examples) (loaded via `--examples`).

### How the LLM mock is used (and why it's a separate CI step)

Real LLM calls would burn tokens on every CI run and be non-deterministic. So:

1. CI starts a Specmatic **stub** of `llm_contract.yaml` (`specmatic stub llm_contract.yaml --port 9090`).
2. The app's provider base URL is **env-overridable** — `core/llm_manager.py` reads `GROQ_API_URL`;
   CI sets it to the stub.
3. `scripts/llm_mock_test.py` runs the real NL-to-SQL path, which now talks to the stub instead
   of Groq → **deterministic, offline, zero-token** AI tests.

It runs as its **own step, after** the contract + resiliency tests, on purpose: those test
**Meridian's own API** (Meridian as *provider*); this step virtualizes an **upstream dependency
Meridian consumes** (Meridian as *consumer*). Different role, different contract → separate step.

### CI (`.github/workflows/contract.yml`)

On every push/PR touching the API, `specmatic.yaml`'s `schemaResiliencyTests: all` setting means
each spec's single test run already covers **both** conformance (examples) **and** resiliency
(generative/boundary) — so there are just two spec-testing jobs plus the LLM smoke test:
1. **`contract_public.yaml`** — **100% coverage** (`200` + `400`).
2. **`api_contract.yaml`**, LLM mocked — exercises the real LLM-calling endpoints (`/api/command`, …)
   with the provider served by the Specmatic stub, so the AI path is tested **offline, zero-token**.
   Protected endpoints authenticate via the app's **API bearer-token** auth — a real auth method
   for programmatic clients, enabled by setting `API_BEARER_TOKEN` — which Specmatic supplies
   through its `securitySchemes` config.
3. **LLM virtualization smoke test** (`scripts/llm_mock_test.py`).

Captured run reports for all three specs live in [`reports/`](./reports). This suite has
already caught real bugs — a `500` crash on malformed `/api/command` input, an undocumented
`config` leak in `/api/connections`, an ambiguous error `oneOf` — see the blog learnings.

For the exact commands to run these tests yourself, see **[Setup → Run all the Specmatic
tests](#2--run-all-the-specmatic-tests)** below — that section is the single source of truth
for run instructions.

---

## Screenshots

| Query Agent | AI Analysis | Database Overview |
|:-----------:|:-----------:|:-----------------:|
| ChatGPT-style input with instant results | Pick a table, get AI insights + charts | Full DB stats, relationships, suggested queries |

---

## Features

### Natural Language Queries
- Type plain English like "show me top 10 customers by revenue" and get working SQL
- Dialect-aware generation (SQLite, MySQL, PostgreSQL, etc.)
- Conversation context — follow-up queries understand previous results
- AI fallback — if SQL generation fails, Groq answers your question directly with full schema context

### Hardcoded DBMS Commands (Always Work, No LLM Needed)
These commands bypass the AI entirely and execute instantly:

| Command | What it does |
|---------|-------------|
| `show tables` | List all tables |
| `describe <table>` | Columns, types, PKs, FKs, indexes, row count |
| `show foreign keys` | All FK relationships across all tables |
| `show foreign keys for <table>` | FKs for a specific table |
| `show indexes` | All indexes across all tables |
| `show constraints` | All PKs, FKs, NOT NULL, UNIQUE constraints |
| `show table counts` | Row count for every table |
| `show create table <name>` | DDL / CREATE TABLE statement |

### AI Data Analysis
- **Pick any table** from a visual grid and analyze it with AI
- **Write custom SQL** and analyze the results
- **Upload a CSV** for standalone analysis
- AI generates markdown insights + auto-picks the best chart type (bar, line, pie, scatter, etc.)
- All powered by Groq (Llama 3.3 70B)

### AI Dashboards
- **One-click AI generation** — describe what you want ("sales overview", "customer insights") and AI creates 4-6 widgets with working SQL
- **Manual widget builder** with table picker — select a table, choose chart type, customize the query
- **Live data** — widgets fetch from the actual database on every load
- **Persistent** — dashboards saved to disk, survive restarts

### Database Overview
- Auto-generated stats cards (total tables, rows, FKs, largest table)
- AI executive summary of the database
- Table size bar chart
- Foreign key relationship table
- AI-suggested analytical queries (click to run)
- "Ask anything" box — ask questions about your database in plain English

### Safety & Review
- **Human-in-the-loop** — all write operations (INSERT, UPDATE, DELETE) require review before execution
- **Dry run** — test queries without committing
- **Snapshot rollback** — automatic backup before writes, one-click undo
- **SQL guardrails** — blocks DROP, TRUNCATE, ALTER, SQL injection patterns
- **Role-based access** — Viewer (read-only), Editor (read+write), Admin (everything)

### LLM Administration
- **Dual provider** — switch between Groq (cloud) and Ollama (local) at any time
- **Ollama model switching** — click any installed model to make it active (auto-saves)
- **Pull new models** — download models from Ollama directly from the UI
- **Usage analytics** — track API calls, latency, token consumption per provider
- **Test console** — send raw prompts to any provider for debugging

### Export
- **CSV** — download query results as CSV
- **PowerPoint** — auto-generated presentations with title slide, schema overview, SQL, data table, AI insights, and charts

---

## Architecture

```
User (Browser)
    |
    v
Flask App (app.py)
    |
    |-- Auth (session-based, RBAC)
    |-- Query Engine
    |     |-- Hardcoded Commands (instant)
    |     |-- LLM Router (Groq or Ollama)
    |     |     |-- Schema-aware prompts with FK/index/sample data
    |     |     |-- Dialect-specific templates
    |     |-- Validator (safety checks)
    |     |-- Adapter (executes against DB)
    |
    |-- Analysis Engine (Groq)
    |     |-- analyze_data() — table/query results -> insights + chart
    |     |-- ai_ask() — general Q&A with full schema context
    |     |-- get_table_overview() — full DB analysis
    |     |-- analyze_schema() — BI report generation
    |
    |-- Dashboard Engine
    |     |-- AI auto-generate (Groq JSON mode)
    |     |-- Manual widget builder
    |     |-- Live data fetch per widget
    |
    |-- Export (CSV, PowerPoint)
    |-- Snapshot System (backup/restore)
```

### Tech Stack

| Layer | Technologies |
|:------|:------------|
| **Frontend** | HTML5, CSS3 (custom dark theme), Chart.js, Marked.js |
| **Backend** | Python 3.11+, Flask |
| **AI (Cloud)** | Groq SDK — Llama 3.3 70B Versatile |
| **AI (Local)** | Ollama — Mistral, Llama 3, or any pulled model |
| **Databases** | SQLite, PostgreSQL, MySQL, MSSQL, Oracle, MongoDB, Cassandra, Redis |
| **Persistence** | File-based JSON (connections, dashboards, metrics, snapshots) |

---

## File Structure

```
.
├── app.py                      # Flask app — all routes and business logic
├── core/
│   ├── adapters/               # Database adapter framework
│   │   ├── base.py             # Abstract adapter interface
│   │   ├── sqlite_adapter.py   # SQLite (with FK/index/describe support)
│   │   ├── postgres_adapter.py # PostgreSQL (connection pooling)
│   │   ├── mysql_adapter.py    # MySQL/MariaDB
│   │   ├── mssql_adapter.py    # SQL Server
│   │   ├── oracle_adapter.py   # Oracle
│   │   ├── mongo_adapter.py    # MongoDB
│   │   ├── cassandra_adapter.py# Cassandra
│   │   └── redis_adapter.py    # Redis
│   ├── analyzer.py             # AI analysis (analyze_data, ai_ask, get_table_overview)
│   ├── connection_manager.py   # Connection lifecycle with encrypted credentials
│   ├── csv_parser.py           # CSV file ingestion
│   ├── dashboards.py           # Dashboard CRUD (JSON persistence)
│   ├── intelligence.py         # Command intent classification
│   ├── llm.py                  # LLM query generation (Groq + Ollama)
│   ├── llm_manager.py          # Provider config and Ollama model management
│   ├── metrics.py              # Usage telemetry
│   ├── ppt_generator.py        # PowerPoint generation (python-pptx)
│   ├── snapshot.py             # Database backup/restore
│   └── validator.py            # SQL safety validation
├── db/
│   ├── main.db                 # Default SQLite database
│   ├── northwind.db            # Sample Northwind database
│   ├── chinook.db              # Sample Chinook database
│   ├── connections.json        # Saved database connections
│   ├── dashboards.json         # Saved dashboards
│   ├── usage_metrics.json      # LLM usage history
│   └── snapshots/              # Database backup files
├── static/
│   └── style.css               # Complete design system (dark theme)
├── templates/
│   ├── index.html              # Main query interface (sidebar + chat input)
│   ├── login.html              # Login page
│   ├── overview.html           # Database overview dashboard
│   ├── analysis.html           # AI data analysis (table picker + charts)
│   ├── dashboards.html         # Dashboard listing + AI generator
│   ├── dashboard_view.html     # Dashboard builder (widgets + charts)
│   ├── databases.html          # Connection manager
│   ├── admin.html              # LLM admin (metrics + model switching)
│   ├── review.html             # Write query review (human-in-the-loop)
│   ├── insights.html           # Schema intelligence report
│   ├── snapshots.html          # Snapshot management
│   └── command_guide.html      # Command reference + intent analyzer
├── requirements.txt
└── .env                        # GROQ_API_KEY
```

---

## API Endpoints

### Authentication
| Method | Route | Description |
|--------|-------|-------------|
| POST | `/login` | Session-based login |
| GET | `/logout` | Clear session |

### Query Engine
| Method | Route | Description |
|--------|-------|-------------|
| POST | `/` | Submit natural language query |
| POST | `/execute` | Execute reviewed write query |
| POST | `/dry-run` | Test query without committing |
| POST | `/refine` | AI-refine a generated query |
| GET | `/export` | Download results as CSV |
| GET | `/export/ppt` | Download results as PowerPoint |

### AI Analysis
| Method | Route | Description |
|--------|-------|-------------|
| POST | `/api/analyze-direct` | Analyze a table or SQL query directly |
| POST | `/analyze` | Analyze last query results |
| POST | `/analyze-csv` | Analyze uploaded CSV |
| POST | `/api/ask` | Ask any question about the database |
| POST | `/api/insights` | Generate schema intelligence report |
| GET | `/api/tables-list` | List tables with row counts |
| POST | `/api/table-preview` | Preview first 10 rows of a table |

### Database Overview
| Method | Route | Description |
|--------|-------|-------------|
| GET | `/overview` | Database overview page |
| POST | `/api/overview` | Generate AI overview data |
| POST | `/api/overview/query` | Execute a suggested query |

### Dashboards
| Method | Route | Description |
|--------|-------|-------------|
| GET | `/dashboards` | Dashboard listing |
| GET | `/dashboards/<id>` | Dashboard builder/viewer |
| POST | `/api/dashboards` | Create dashboard |
| DELETE | `/api/dashboards/<id>` | Delete dashboard |
| POST | `/api/dashboards/auto-generate` | AI-generate full dashboard |
| POST | `/api/dashboards/<id>/widgets` | Add widget |
| DELETE | `/api/dashboards/<id>/widgets/<wid>` | Remove widget |
| POST | `/api/query` | Execute query for widget data |

### Database Management
| Method | Route | Description |
|--------|-------|-------------|
| GET | `/databases` | Connection manager page |
| POST | `/databases/add` | Add connection |
| POST | `/databases/test` | Test connection |
| POST | `/databases/test-new` | Test before saving |
| POST | `/databases/select` | Switch active database |
| POST | `/databases/delete` | Remove connection |

### LLM Administration
| Method | Route | Description |
|--------|-------|-------------|
| GET | `/admin` | Admin dashboard |
| POST | `/admin/llm/config` | Update provider config + active model |
| POST | `/admin/ollama/pull` | Pull new Ollama model |
| POST | `/admin/test_llm` | Test prompt against any provider |

### Snapshots
| Method | Route | Description |
|--------|-------|-------------|
| GET | `/snapshots` | Snapshot listing |
| POST | `/snapshots/create` | Create snapshot |
| POST | `/snapshots/restore` | Restore from snapshot |
| POST | `/snapshots/delete` | Delete snapshot |
| POST | `/undo` | Undo last write operation |

---

## Setup

### Prerequisites
- **Python 3.11 – 3.14** (verified across all four)
- **Node.js 18+** and npm (for the React frontend)
- A **Groq API key** — free at [console.groq.com](https://console.groq.com) (powers the NL-to-SQL / AI features; the hardcoded DBMS commands work without it)
- To run the contract tests: **Docker** (recommended — same as CI) *or* **Java 17+** (uses the bundled `specmatic.jar`)

### 1 — Run the application

The app is a **Flask API** plus a **React (Vite) frontend**.

```bash
# --- backend (terminal 1) ---
python3 -m venv venv && source venv/bin/activate
python -m pip install -r requirements.txt      # core deps only — runs on the bundled SQLite DBs
echo "GROQ_API_KEY=your_key_here" > .env      # needed for the AI features
python app.py                                  # API on http://localhost:5001
```
> **Use `python -m pip`, not bare `pip`/`pip3`.** On machines with several Pythons, `pip`
> can point at a *different* interpreter than the one you'll run the app with (this is what
> causes install-vs-run version mismatches). Inside the activated venv, `python -m pip`
> always targets the venv's interpreter. Verified end-to-end on **Python 3.11, 3.12, 3.13
> and 3.14**.
>
> **Database drivers are optional.** `requirements.txt` is the lean core that runs the app
> and the whole test suite on the bundled SQLite databases. The external engine drivers
> (Postgres, MySQL, MSSQL, Oracle, Mongo, Cassandra, Redis) are lazy-imported and live in
> `requirements-optional.txt` — install that **only** to connect one of those engines:
> `python -m pip install -r requirements-optional.txt`.
> macOS: port 5000 is taken by AirPlay Receiver, so the app listens on **5001**.

```bash
# --- frontend (terminal 2) ---
cd meridian-frontend
npm install
npm run dev                                    # Vite on http://localhost:5173
```
Open **http://localhost:5173/app/** — Vite proxies `/api` to the backend on 5001, and the SPA router uses basename `/app`. The sample SQLite databases (Chinook, Northwind, …) ship in `db/`, so there is nothing to seed.

**Or run the whole stack with one command (Docker):**
```bash
python start.py            # builds if needed, starts backend + frontend, opens http://localhost:8080
python start.py --stop     # stop it
```

### 2 — Run all the Specmatic tests

The contract suite runs the real API with its LLM dependency **virtualized** (a Specmatic stub of the LLM), so it is deterministic and spends **zero tokens**. `specmatic.yaml` sets `schemaResiliencyTests: all`, so every spec's test run already covers conformance (examples) **and** resiliency (generative/boundary) in one pass — that's why there are only **two** spec-testing jobs, not four.

One script starts the stub + app, runs both spec jobs plus the LLM-virtualization smoke test, and writes the HTML reports to `reports/` — it auto-uses Docker if present, else the bundled `specmatic.jar`:

```bash
bash scripts/run_specmatic_tests.sh
```
Every job reports **100% API coverage** with the actuator enabled (actual coverage); reports land in `build/reports/specmatic/test/html/` and are copied to [`reports/`](reports/) as part of the same script run. The same jobs run in CI on every push — see [`.github/workflows/contract.yml`](.github/workflows/contract.yml).

> **Authentication uses the app's real API bearer-token auth — no test-only bypass.**
> Alongside the web UI's session-cookie login, the API accepts a real `Bearer` token for
> programmatic clients (any client can use it — curl, CI, a gateway, or Specmatic). Valid
> tokens come from the `API_BEARER_TOKEN` env var; with none set the API stays cookie-only.
> The token is declared once in [`specmatic.yaml`](specmatic.yaml)
> (`securitySchemes.bearerAuth.token`, overridable via `API_BEARER_TOKEN`), and Specmatic
> sends it like any other client would — so the authenticated **and** the `401` paths are
> both exercised, with no separate code path for the test tool. `run_specmatic_tests.sh`
> starts the app with `API_BEARER_TOKEN` set (and picks free ports automatically), so just
> run the script — it owns the app + auth end to end. (Run the app manually without
> `API_BEARER_TOKEN` and the protected endpoints correctly return `401`.)

**Configurable variables** (all optional, sensible defaults baked in):

| Variable | Default | Purpose |
|---|---|---|
| `APP_PORT` | `5001` | Port the Flask app runs on |
| `STUB_PORT` | `9090` | Port the LLM stub runs on |
| `TEST_APP_PORT` | same as `APP_PORT` | Keeps `specmatic.yaml`'s `baseUrl`/`actuatorUrl` aligned with the app port |
| `API_BEARER_TOKEN` | `specmatic-ci-token` | Bearer token the app + Specmatic both use |
| `SPECMATIC_JAR` | `specmatic.jar` in repo root | Path to the Specmatic jar, if not using Docker |
| `HOME` | your shell's `$HOME` | Only relevant if your jar lives outside the repo and is referenced relative to `$HOME` |
| `GROQ_API_URL` / `GROQ_API_KEY` | stub URL / `ci-stub-key` | Where the app sends LLM calls in test mode |
| `ENABLE_ACTUATOR` | `1` (on) | Exposes the test-only `/actuator/mappings` endpoint Specmatic reads for actual-coverage reporting |

Override any of them, e.g.: `SPECMATIC_JAR=/path/to/specmatic.jar STUB_PORT=9191 bash scripts/run_specmatic_tests.sh`. The script auto-selects a free port if the default is busy, so a stale process never blocks it.

**Or run each test on its own** (concrete steps — two terminals; `TEST_APP_PORT` keeps the
config's actuator URL aligned with the app port):
```bash
# Terminal A — LLM stub + app (one line each)
java -jar ${SPECMATIC_JAR:-specmatic.jar} stub llm_contract.yaml --port 9090 &
API_BEARER_TOKEN=specmatic-ci-token ENABLE_ACTUATOR=1 \
  GROQ_API_URL=http://localhost:9090/openai/v1/chat/completions GROQ_API_KEY=ci-stub-key \
  python -m flask --app app run --port 5001 &

# Terminal B — run each spec job (schemaResiliencyTests: all in specmatic.yaml covers
# conformance + resiliency in one run — no separate "resiliency mode" invocation needed)
export TEST_APP_PORT=5001
java -jar ${SPECMATIC_JAR:-specmatic.jar} test contract_public.yaml --examples examples     --host localhost --port 5001   # public
java -jar ${SPECMATIC_JAR:-specmatic.jar} test api_contract.yaml    --examples examples_api --host localhost --port 5001   # full API, LLM mocked
```
(Swap `java -jar $SPECMATIC_JAR` for `docker run --rm --network host -v "$PWD:/specs" -w /specs specmatic/specmatic:2.48.0` to use Docker instead of the bundled jar.)

**Missing-in-spec endpoints:** the app exposes 52 `/api` routes; the contract deliberately governs
the 6 that form the external trust boundary. See [`CONTRACT_SCOPE.md`](./CONTRACT_SCOPE.md) for
the full list, the reasoning, and how to promote an endpoint into the contract later.

### Access & demo accounts
Open **http://localhost:5173/app/** (dev) or **http://localhost:8080** (Docker).

**Demo accounts:**
| Username | Password | Role |
|----------|----------|------|
| `admin1` | `admin123` | ADMIN (full access) |
| `editor1` | `editor123` | EDITOR (read + write) |
| `viewer1` | `viewer123` | VIEWER (read only) |

---

## Design

The UI uses a custom dark theme inspired by Linear, Raycast, and ChatGPT:

- Fixed top navigation with compact links
- Collapsible sidebar with query history (hamburger menu on mobile)
- ChatGPT-style floating input bar at the bottom
- Cards with subtle borders, no heavy shadows
- Responsive grid layouts for all screen sizes
- Chart.js for all visualizations
- Markdown rendering for AI responses (via Marked.js)

---

## How It Works

### Query Flow
1. User types a natural language command (e.g. "show top 5 customers")
2. System checks hardcoded commands first (instant, no LLM needed)
3. If not hardcoded, schema (with FKs, indexes, sample data) is sent to LLM
4. LLM generates dialect-specific SQL
5. Validator checks safety (blocks DROP, injection, etc.)
6. READ queries execute immediately with pagination
7. WRITE queries go to human review page with dry-run option
8. If SQL fails, system falls back to AI Ask (answers the question directly)

### Analysis Flow
1. User picks a table or writes custom SQL on the Analysis page
2. Data preview shows first 10 rows
3. On "Analyze", up to 200 rows are sent to Groq
4. Groq returns JSON with insights summary + chart configuration
5. Chart.js renders the visualization
6. Results can be exported as PowerPoint

### Dashboard Flow
1. User describes what they want (e.g. "sales overview")
2. Groq generates 4-6 widget configs with working SQL (using JSON mode for reliability)
3. Dashboard is created and user is redirected to the builder
4. Each widget fetches live data from the database on load
5. Users can add/remove widgets manually with a table picker

---

**Meridian Data** — Built as a Minor Project for DBMS coursework.
