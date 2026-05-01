# DATABASE-MANAGER

> Internal codename: **Meridian Data** — a multi-database, AI-assisted query and analysis platform.

## Overview

DATABASE-MANAGER is a full-stack application that lets a user explore and operate on a database using plain English. A natural language prompt is passed through an LLM, converted into a dialect-specific query (SQL, CQL, MongoDB JSON, or Redis commands), validated by a safety layer, and either executed immediately (for reads) or routed to a human approval screen (for writes). Results are paginated, exportable, and can be analyzed or visualized inside the same UI.

The project began as a SQLite-only teaching tool and grew into a general-purpose database client. It currently ships adapters for eight engines — SQLite, PostgreSQL, MySQL, Microsoft SQL Server, Oracle, MongoDB, Apache Cassandra, and Redis — each implementing a common interface so the rest of the system stays dialect-agnostic. Two LLM providers are supported in parallel: **Groq** (cloud, default model `llama-3.3-70b-versatile`) and **Ollama** running a local model such as **Mistral**. The active provider can be switched at runtime, and the system falls back to the other provider if the primary one errors out.

The goal is practical: give a student or analyst something that looks and feels like a modern data tool (chat-style input, live charts, AI-generated dashboards, PowerPoint export) without giving the LLM unsupervised write access to the database. Every destructive statement is gated behind validation, role checks, dry-run preview, and an automatic snapshot.

## Key Features

- **Natural language to query**, dialect-aware. The LLM is given the live schema (tables, columns, foreign keys, indexes, sample rows) and prompted to emit only valid syntax for the active engine.
- **Hardcoded DBMS commands** that bypass the LLM entirely: `show tables`, `describe <table>`, `show foreign keys`, `show indexes`, `show constraints`, `show table counts`, `show create table <name>`. These run instantly with zero token cost.
- **Eight database adapters** behind a single interface (`core/adapters/base.py`). Switching between SQLite and PostgreSQL is a UI dropdown, not a code change.
- **Dual-provider LLM** with automatic fallback. Configure both Groq and Ollama; if the active one is unreachable, the other is tried (`core/llm.py:172`).
- **Human-in-the-loop write review**. Any `INSERT`, `UPDATE`, or `DELETE` is held on a review screen (`templates/review.html`) where the user sees the generated query, can dry-run it, and must explicitly confirm execution.
- **Automatic snapshots before writes** with one-click rollback. SQLite uses file copy; other engines use their native dump tools (`core/snapshot.py`).
- **Role-based access control**: `VIEWER` (read + system queries only), `EDITOR` (adds writes), `ADMIN` (adds schema changes).
- **Encrypted connection storage**. Saved database passwords are encrypted with Fernet using a per-install key in `db/.secret_key` (`core/connection_manager.py:25`).
- **AI data analysis**: pick a table, run a custom query, or upload a CSV, and the LLM returns a markdown summary plus a chart configuration that is rendered with Chart.js.
- **AI-generated dashboards**: describe what you want and the model returns 4–6 widgets with working SQL; widgets are persisted to disk and re-fetch live data on every load.
- **PowerPoint export** of a result set (title slide, schema overview, query, data table, AI insights, chart) via `python-pptx`.
- **Two front-ends in one repo**: a server-rendered Jinja UI under `templates/` and a Vite/React 19 SPA under `meridian-frontend/`. Both call the same Flask backend.

## Architecture

The system has three logical layers: the user-facing UI, the Flask application (auth, routing, validation, orchestration), and the pluggable data layer (LLM providers + database adapters).

```
+--------------------------------------------------------------+
|                    Browser (User)                            |
|   Jinja templates  /  React SPA (meridian-frontend)          |
+----------------------------+---------------------------------+
                             |  HTTP (session cookie)
                             v
+--------------------------------------------------------------+
|                Flask App  (app.py + api_routes.py)           |
|                                                              |
|  +-----------+   +------------------+   +-----------------+  |
|  |   Auth    |-->|  Intent Router   |-->|  Hardcoded      |  |
|  |  (RBAC)   |   |  (intelligence)  |   |  Commands       |  |
|  +-----------+   +------------------+   +-----------------+  |
|                          |                                   |
|                          v                                   |
|                 +------------------+                         |
|                 |   LLM Layer      |                         |
|                 |   core/llm.py    |                         |
|                 +------------------+                         |
|                  |               |                           |
|                  v               v                           |
|             +---------+    +-----------+                     |
|             |  Groq   |    |  Ollama   |  <-- fallback       |
|             |  cloud  |    |  local    |      chain          |
|             +---------+    +-----------+                     |
|                          |                                   |
|                          v                                   |
|                +------------------+                          |
|                |    Validator     |   blocks DROP/TRUNCATE   |
|                | core/validator.py|   /ALTER/PRAGMA/`;`      |
|                +------------------+                          |
|                          |                                   |
|         +----------------+----------------+                  |
|         |                                 |                  |
|         v                                 v                  |
|   +-----------+                    +--------------+          |
|   |   READ    |                    |    WRITE     |          |
|   |  execute  |                    |  Review page |          |
|   +-----+-----+                    +-------+------+          |
|         |                                  |                 |
|         |                                  v                 |
|         |                          +--------------+          |
|         |                          |  Snapshot +  |          |
|         |                          |  Execute     |          |
|         |                          +-------+------+          |
|         |                                  |                 |
|         +----------------+-----------------+                 |
|                          v                                   |
|              +-----------------------+                       |
|              |   Adapter Interface   |                       |
|              |   core/adapters/      |                       |
|              +-----------------------+                       |
+--------------------------------------------------------------+
                          |
                          v
   +--------+ +-----------+ +-------+ +--------+ +-------+
   | SQLite | | Postgres  | | MySQL | | MSSQL  | | Oracle|
   +--------+ +-----------+ +-------+ +--------+ +-------+
   +---------+ +-----------+ +-------+
   | MongoDB | | Cassandra | | Redis |
   +---------+ +-----------+ +-------+
```

### Request lifecycle for a natural language query

1. Browser POSTs the prompt to Flask (`app.py` for the Jinja UI, `api_routes.py` for the React SPA).
2. The session cookie identifies the user; their role is checked against the requested action.
3. The intent classifier (`core/intelligence.py`) and the hardcoded-commands shortcut decide whether to call the LLM at all.
4. If the LLM is needed, the active adapter's schema (tables, FKs, indexes, sample rows) is injected into a dialect-specific system prompt (`core/llm.py:21`).
5. `generate_query()` calls Groq first (or Ollama, depending on `active_provider` in `db/llm_config.json`) and falls back to the other provider on error.
6. The validator (`core/validator.py:42`) classifies the result as `READ`, `WRITE`, `SCHEMA`, or `SYSTEM` and blocks anything containing forbidden keywords or statement chaining.
7. `READ` and `SYSTEM` queries execute through the adapter and return paginated rows.
8. `WRITE` queries are stored in session and the user is redirected to `/review`. After confirmation, a snapshot is taken (`core/snapshot.py:60`), the query executes, and the user can `/undo` to roll back.

## Tech Stack

| Layer            | Technology                                 | Purpose                                                              |
|------------------|--------------------------------------------|----------------------------------------------------------------------|
| Backend          | Python 3.11, Flask 3.1.1                   | HTTP server, routing, session auth                                   |
| WSGI server      | gunicorn 21.2 (containerized)              | Production process model (2 workers x 4 threads, 120 s timeout)      |
| Auth             | werkzeug.security + Flask sessions         | Password hashing and session-based RBAC                              |
| Cloud LLM        | Groq SDK (`groq==0.25.0`)                  | Default provider, model `llama-3.3-70b-versatile`                    |
| Local LLM        | Ollama HTTP API (`http://localhost:11434`) | Offline provider, default model `mistral`                            |
| SQL drivers      | sqlite3, psycopg2-binary, pymysql, pymssql, oracledb | Engine-specific connectivity                              |
| NoSQL drivers    | pymongo, cassandra-driver, redis           | MongoDB, Cassandra, Redis support                                    |
| Encryption       | cryptography (Fernet)                      | Encrypts saved connection passwords in `db/connections.json`         |
| Reporting        | python-pptx 1.0.2                          | PowerPoint export of query results and AI analysis                   |
| Sample data      | faker 40.13.0                              | Generates realistic rows for sample database creation                |
| Frontend         | React 19, Vite 8, Tailwind CSS v4          | SPA build under `meridian-frontend/`                                 |
| Frontend data    | @tanstack/react-query, axios               | Server state and HTTP client                                         |
| Charts           | Chart.js 4 + react-chartjs-2               | All visualizations (bar, line, pie, scatter)                         |
| Diagrams         | mermaid                                    | Schema and relationship rendering                                    |
| Markdown         | react-markdown                             | Renders LLM explanations and AI insights                             |
| Routing (SPA)    | react-router 7                             | Client-side navigation                                               |
| Containerization | Docker + docker-compose                    | Two services: Flask backend (5001), nginx-served frontend (8080)     |
| Legacy UI        | Jinja2 templates + vanilla JS              | Server-rendered pages still live under `templates/`                  |

## Project Structure

```
DATABASE-MANAGER/
├── app.py                       # Flask app, Jinja routes, auth, query orchestration
├── api_routes.py                # /api blueprint consumed by the React SPA
├── start.py                     # One-shot launcher (docker compose up + open browser)
├── add_chinook.py               # Helper: registers a local Chinook connection
├── requirements.txt             # Python dependencies
├── Dockerfile                   # Multi-stage build: builds React then Python image
├── docker-compose.yml           # Backend + frontend services on a shared bridge net
├── readme.md                    # Existing detailed product README (this file replaces it)
│
├── core/
│   ├── adapters/
│   │   ├── base.py              # Common adapter interface (execute, schema, snapshot)
│   │   ├── sqlite_adapter.py
│   │   ├── postgres_adapter.py
│   │   ├── mysql_adapter.py
│   │   ├── mssql_adapter.py
│   │   ├── oracle_adapter.py
│   │   ├── mongo_adapter.py
│   │   ├── cassandra_adapter.py
│   │   └── redis_adapter.py
│   ├── llm.py                   # Groq + Ollama clients with fallback chain
│   ├── llm_manager.py           # Reads/writes db/llm_config.json
│   ├── validator.py             # Safety check + READ/WRITE/SCHEMA/SYSTEM classifier
│   ├── intelligence.py          # LLM-based intent explanation for the command guide
│   ├── connection_manager.py    # Encrypted connection store (Fernet)
│   ├── snapshot.py              # Cross-engine snapshot/restore registry
│   ├── analyzer.py              # AI table/CSV analysis with chart suggestions
│   ├── dashboards.py            # Dashboard CRUD (JSON-persisted)
│   ├── ppt_generator.py         # PowerPoint export
│   ├── metrics.py               # LLM call telemetry (latency, tokens)
│   ├── csv_parser.py
│   ├── db.py                    # Legacy SQLite-only helpers
│   └── sample_databases.py      # Faker-driven sample DB generators
│
├── templates/                   # Jinja2 server-rendered UI
│   ├── index.html               # Chat-style query page
│   ├── login.html
│   ├── overview.html            # AI database overview
│   ├── analysis.html            # Table picker + AI analysis
│   ├── dashboards.html
│   ├── dashboard_view.html
│   ├── databases.html           # Connection manager
│   ├── admin.html               # LLM admin (provider switch, metrics)
│   ├── review.html              # Human approval for writes
│   ├── snapshots.html
│   ├── insights.html
│   ├── command_guide.html
│   └── create_database.html
│
├── static/                      # CSS / JS / assets for the Jinja UI
│
├── meridian-frontend/           # React 19 + Vite 8 SPA
│   ├── src/
│   │   ├── App.jsx, main.jsx
│   │   ├── api/                 # axios clients per backend resource
│   │   ├── pages/               # QueryPage, OverviewPage, AdminPage, ...
│   │   ├── components/
│   │   ├── context/
│   │   └── lib/
│   ├── package.json
│   ├── vite.config.js
│   ├── nginx.conf               # Used by the frontend container
│   └── Dockerfile
│
└── db/
    ├── main.db                  # Default SQLite database
    ├── llm_config.json.example  # Template for provider config
    ├── connections.json         # Encrypted saved connections (gitignored)
    ├── snapshots.json           # Snapshot registry
    ├── snapshots/               # Snapshot files
    ├── dashboards.json          # Saved dashboards
    └── usage_metrics.json       # LLM call history
```

## Prerequisites

- **Python 3.11 or newer** (the Docker image uses `python:3.11-slim`).
- **Node.js 20+** if you want to run the React SPA in dev mode (the container build uses `node:20-alpine`).
- **Docker Desktop** (or any compatible engine) if you want the one-command path via `start.py`.
- A **Groq API key** for cloud inference. Get one at https://console.groq.com.
- **Ollama** installed locally if you want offline inference. After install:

  ```bash
  ollama pull mistral
  ollama serve   # exposes http://localhost:11434
  ```

- System packages required by the database drivers when building from source: `build-essential`, `libpq-dev` (Postgres), `default-libmysqlclient-dev` (MySQL), `freetds-dev` (MSSQL). The Dockerfile installs these automatically.

## Installation

### Option 1 — Docker (recommended)

```bash
git clone https://github.com/AYON-ARYAN/DATABASE-MANAGER.git
cd DATABASE-MANAGER

# Provide your Groq API key (optional but enables AI features)
echo "GROQ_API_KEY=your_key_here" > .env

# Bring up backend (port 5001) and frontend (port 8080)
python start.py
```

`start.py` will:
1. Verify Docker is installed and the daemon is running (auto-launches Docker Desktop on macOS/Windows if needed).
2. Create `.env` from `.env.example` if missing.
3. Run `docker compose up -d --build`.
4. Wait until both services pass their health checks.
5. Open `http://localhost:8080` in the default browser.

To stop: `python start.py --stop`. To tail logs: `python start.py --logs`.

### Option 2 — Bare metal (Flask + Jinja UI only)

```bash
git clone https://github.com/AYON-ARYAN/DATABASE-MANAGER.git
cd DATABASE-MANAGER

python3 -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp db/llm_config.json.example db/llm_config.json
echo "GROQ_API_KEY=your_key_here" > .env

python app.py                       # serves on http://127.0.0.1:5000
```

### Option 3 — Bare metal with the React SPA in dev mode

In one terminal, run the Flask backend as in Option 2. In a second terminal:

```bash
cd meridian-frontend
npm install
npm run dev                         # Vite dev server on http://localhost:5173
```

Vite proxies API calls to Flask. Flask is configured to allow CORS from `http://localhost:5173` (`app.py:71`).

## Usage

After starting the app, sign in at `/login`. The repository ships with three demo accounts that exist purely for local development; rotate or remove them before any non-local deployment.

| Username | Password   | Role     | Allowed actions                       |
|----------|------------|----------|---------------------------------------|
| viewer1  | viewer123  | VIEWER   | READ, SYSTEM                          |
| editor1  | editor123  | EDITOR   | READ, WRITE, SYSTEM                   |
| admin1   | admin123   | ADMIN    | READ, WRITE, SCHEMA, SYSTEM           |

### Running natural language queries

The default landing page is the chat-style query interface. Type a request in plain English and submit. Example prompts that work against the bundled SQLite database:

```
show tables
describe customers
show top 10 customers by total spend
list the 5 most-played tracks with their artist names
how many invoices were issued in 2010 grouped by country
which employees report to Andrew Adams
```

For read queries the result table appears immediately with pagination. For writes (`INSERT` / `UPDATE` / `DELETE`) the app generates the SQL, then redirects to `/review` where you can:

- See the exact statement that will run.
- Click **Dry Run** to see how many rows would be affected.
- Click **Execute** to take a snapshot and run the statement.
- Click **Cancel** to discard.

If something went wrong after a write, hit **Undo** on the snapshots page to restore the most recent backup.

### AI analysis

Open the **Analysis** page, pick a table (or paste a custom query, or upload a CSV). The first 10 rows preview immediately. Click **Analyze** to send up to 200 rows to the LLM; it returns a markdown summary plus a Chart.js configuration that the page renders inline. The whole report can be exported as a `.pptx`.

### Dashboards

On the **Dashboards** page, type a description such as `sales overview` or `customer behavior`. The LLM returns 4–6 widget definitions, each with its own SQL and recommended chart type. Widgets are stored in `db/dashboards.json` and re-fetch live data every time the dashboard is opened.

### Switching databases

Open **Databases** to add a new connection. Pick the engine, fill in host/port/credentials, click **Test**, then **Save**. The password is encrypted with Fernet before being written to `db/connections.json`. From the dropdown in the header you can switch the active connection at any time; subsequent queries are routed through that adapter and use that engine's dialect prompt.

### Switching LLM providers

The **Admin** page shows the currently active provider (Groq or Ollama), per-provider call counts, latency, and token usage. You can:

- Toggle the active provider.
- Change the Groq model name.
- List installed Ollama models, click one to make it active, or pull a new model from the UI.
- Send a raw test prompt to either provider for debugging.

## Configuration

| Variable / file                | Default                                | Purpose                                                     |
|--------------------------------|----------------------------------------|-------------------------------------------------------------|
| `.env` -> `GROQ_API_KEY`       | empty                                  | Cloud LLM auth. If empty, AI features fall back to Ollama.  |
| `.env` -> `FLASK_ENV`          | `production` (in compose)              | Standard Flask environment flag.                            |
| `SERVE_REACT_AT_ROOT`          | `1`                                    | When set, Flask serves the built React SPA at `/`.          |
| `db/llm_config.json`           | copy from `db/llm_config.json.example` | Active provider, model name, endpoints, API key.            |
| `db/connections.json`          | auto-created                           | Saved DB connections; passwords encrypted with Fernet.      |
| `db/.secret_key`               | auto-generated                         | Fernet key used to encrypt/decrypt saved passwords.         |
| Backend port                   | 5001 (Docker) / 5000 (bare metal)      | Flask + gunicorn listen port.                               |
| Frontend port                  | 8080                                   | nginx-served React build (Docker only).                     |
| Vite dev port                  | 5173                                   | React dev server, allowed via CORS in `app.py:71`.          |
| Default DB                     | `db/main.db` (SQLite)                  | Created on first startup by `ensure_default_sqlite()`.      |
| Snapshot cap                   | `MAX_SNAPS_PER_DB = 5`                 | Oldest snapshot is evicted on the sixth.                    |
| Pagination                     | `PAGE_SIZE = 50`                       | Rows per page in result tables.                             |

## Safety Model

The validator (`core/validator.py`) is the single chokepoint between LLM output and the database adapter. It enforces the following rules:

1. **Forbidden SQL keywords** are blocked outright: `drop `, `truncate `, `alter `, `shutdown`, `attach `, `detach `, `pragma `, plus the comment markers `--`, `/*`, `*/`. (`core/validator.py:11`)
2. **Statement stacking is blocked**: any query containing `;` is rejected to prevent appending a destructive command after a benign one. (`core/validator.py:62`)
3. **NoSQL guards**: for MongoDB the parsed JSON is rejected if the operation contains `drop`. For Redis the dangerous-command list blocks `FLUSHALL`, `FLUSHDB`, `CONFIG`, `SHUTDOWN`, `DEBUG`, `SLAVEOF`, `REPLICAOF`. (`core/validator.py:55`)
4. **Classification gates**: every query is tagged `READ`, `WRITE`, `SCHEMA`, `SYSTEM`, or `UNKNOWN`. The route handler then checks the tag against the user's role permissions before executing. (`app.py:106`)

| Role    | READ | WRITE | SCHEMA | SYSTEM |
|---------|------|-------|--------|--------|
| VIEWER  | yes  | no    | no     | yes    |
| EDITOR  | yes  | yes   | no     | yes    |
| ADMIN   | yes  | yes   | yes    | yes    |

5. **Human review for writes**: an `INSERT`, `UPDATE`, or `DELETE` is never executed inline. It is held in the session and the user is redirected to `/review`, where they can dry-run and must explicitly confirm.
6. **Pre-write snapshot**: just before a write executes, `take_snapshot()` is called against the active adapter. Up to five snapshots are retained per connection, and the user can `/undo` to restore the most recent one.
7. **Encrypted credentials at rest**: saved DB passwords are Fernet-encrypted with a per-install key. The on-disk file (`db/connections.json`) and the key (`db/.secret_key`) are both gitignored.
8. **Masked display**: when listing connections in the UI, passwords are replaced with bullets (`core/connection_manager.py:78`).

## Limitations & Future Work

- **`app.secret_key` is hardcoded** to `"dev-secret-key"` in `app.py:48`. This must be replaced with a strong, environment-supplied secret before any non-local deployment.
- **Demo credentials are committed** in `app.py` and `api_routes.py`. They are intended for local exploration; remove them and wire in a real user store before exposing the app.
- **Snapshot support is engine-dependent.** SQLite uses a simple file copy; other engines rely on their respective dump tools being available in the environment. Cassandra and Redis snapshot semantics in particular are best-effort.
- **No streaming for LLM responses.** The query and the explanation are returned in one shot; there is no token-by-token streaming yet.
- **Read pagination is appended at the SQL level** with `LIMIT` / `OFFSET`. For very large tables on engines without keyset pagination, deep page numbers will be slow.
- **Schema introspection is rebuilt per request** for the dialect prompt. Caching this per connection would reduce LLM prompt-build time on busy databases.
- **The Jinja UI and the React SPA partially overlap.** Both consume the same backend; consolidating onto the SPA is in progress.
- **No automated test suite** ships with the repository today. CI and a pytest suite are obvious next steps.
- **Single-tenant by design.** There is no multi-user workspace concept; everyone shares the same set of saved connections and dashboards.

## License

No license file is currently present in the repository. Until one is added, all rights are reserved by the author. If you intend to use, fork, or redistribute this code, please contact the maintainer first. The recommended default for a portfolio project is **MIT**, which can be added by dropping a `LICENSE` file at the repository root.
