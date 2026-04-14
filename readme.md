# Meridian Data

**AI-Powered Database Explorer & DBMS Teaching Tool**

Meridian Data lets you query any database using plain English. It converts natural language into validated SQL, executes queries safely, and generates AI insights, charts, and presentations — all through a clean, modern dark-mode interface.

Built for students, teachers, and analysts who want to explore databases without writing SQL from scratch.

**Supports:** SQLite · PostgreSQL · MySQL · MSSQL · Oracle · MongoDB · Cassandra · Redis

---

## Features

### Natural Language Queries
- Type plain English — *"show me top 10 customers by revenue"* — and get working SQL instantly
- Dialect-aware: generates correct syntax for every supported engine
- Conversation context — follow-up queries understand previous results
- AI fallback — if SQL generation fails, Groq answers the question directly using full schema context

### Hardcoded Commands (Always Work, No LLM Needed)

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
- Pick any table from a visual grid and analyze it with one click
- Write custom SQL and analyze the results directly
- Upload a CSV for standalone analysis
- AI generates markdown insights and auto-picks the best chart type (bar, line, pie, scatter, etc.)
- Powered by Groq — Llama 3.3 70B Versatile

### AI Dashboards
- **One-click generation** — describe what you want ("sales overview") and AI creates 4-6 widgets with working SQL
- **Manual widget builder** — pick a table, choose a chart type, customize the query
- **Live data** — widgets query the actual database on every load
- **Persistent** — dashboards saved to disk, survive restarts

### Database Overview
- Auto-generated stats: total tables, total rows, FKs, largest table
- AI executive summary of the entire database
- Table size bar chart and FK relationship table
- AI-suggested analytical queries — click to run immediately
- Ask anything box — plain English Q&A with full schema context

### Safety & Review
- **Human-in-the-loop** — all write operations (INSERT, UPDATE, DELETE) require review before execution
- **Dry run** — test queries without committing any changes
- **Snapshot rollback** — automatic backup before every write, one-click undo
- **SQL guardrails** — blocks DROP, TRUNCATE, ALTER, and SQL injection patterns
- **Role-based access** — Viewer (read-only), Editor (read + write), Admin (everything)
- **CSRF protection** — all state-changing forms protected with CSRF tokens

### LLM Administration
- **Dual provider** — switch between Groq (cloud) and Ollama (local) at any time from the UI
- **Round-robin key pool** — configure up to 6 Groq API keys; on rate-limit the next key is used automatically
- **Ollama model switching** — click any installed model to make it active
- **Pull new models** — download Ollama models directly from the admin panel
- **Usage analytics** — track API calls, latency, and token consumption per provider
- **Test console** — send raw prompts to any provider for debugging

### Export
- **CSV** — download any query result as a CSV file
- **PowerPoint** — auto-generated slides: title, schema overview, SQL, data table, AI insights, and charts

---

## Architecture

```
Browser
  |
  v
Flask (app.py)  ←  CSRF Protection (Flask-WTF)
  |
  |── Auth             Session-based login, RBAC (Viewer / Editor / Admin)
  |
  |── Query Engine
  |     |── Hardcoded Commands     Instant, no LLM
  |     |── LLM Router             Groq or Ollama
  |     |     |── groq_keys.py     Round-robin key pool (up to 6 keys)
  |     |     └── Dialect prompts  Schema-aware, FK/index/sample-data context
  |     |── Validator              Safety checks (DROP, injection, etc.)
  |     └── Adapters               Per-engine execution (SQL, CQL, MongoDB JSON, Redis)
  |
  |── Analysis Engine (Groq)
  |     |── analyze_data()         Table / query results → insights + chart config
  |     |── ai_ask()               General Q&A with full schema context
  |     |── get_table_overview()   Full DB analysis and BI summary
  |     └── analyze_schema()       Schema intelligence report
  |
  |── Dashboard Engine
  |     |── AI auto-generate       Groq JSON mode → widget configs with SQL
  |     |── Manual widget builder  Table picker + chart type selector
  |     └── Live data fetch        Per-widget query on every load
  |
  |── Export              CSV, PowerPoint (python-pptx)
  └── Snapshot System     Backup / restore / undo
```

### Tech Stack

| Layer | Technologies |
|:------|:------------|
| **Frontend** | HTML5, CSS3 (custom dark theme), Chart.js, Marked.js |
| **Backend** | Python 3.11+, Flask, Flask-WTF |
| **AI — Cloud** | Groq API — Llama 3.3 70B Versatile |
| **AI — Local** | Ollama — Mistral, Llama 3, or any pulled model |
| **Databases** | SQLite, PostgreSQL, MySQL, MSSQL, Oracle, MongoDB, Cassandra, Redis |
| **Security** | CSRF tokens (Flask-WTF), env-based secrets, SQL injection guards |
| **Persistence** | File-based JSON (connections, dashboards, metrics, snapshots) |

---

## File Structure

```
.
├── app.py                          # Flask app — all routes and business logic
├── core/
│   ├── adapters/                   # Per-engine adapter framework
│   │   ├── base.py
│   │   ├── sqlite_adapter.py
│   │   ├── postgres_adapter.py
│   │   ├── mysql_adapter.py
│   │   ├── mssql_adapter.py
│   │   ├── oracle_adapter.py
│   │   ├── mongo_adapter.py
│   │   ├── cassandra_adapter.py
│   │   └── redis_adapter.py
│   ├── analyzer.py                 # AI analysis (analyze_data, ai_ask, get_table_overview)
│   ├── connection_manager.py       # Connection lifecycle with encrypted credentials
│   ├── csv_parser.py               # CSV ingestion
│   ├── dashboards.py               # Dashboard CRUD (JSON persistence)
│   ├── groq_keys.py                # Round-robin Groq API key pool
│   ├── intelligence.py             # Command intent classification
│   ├── llm.py                      # LLM query generation (Groq + Ollama)
│   ├── llm_manager.py              # Provider config and Ollama model management
│   ├── metrics.py                  # Usage telemetry
│   ├── ppt_generator.py            # PowerPoint generation (python-pptx)
│   ├── snapshot.py                 # Database backup / restore
│   └── validator.py                # SQL safety validation
├── db/
│   ├── main.db                     # Default SQLite database
│   ├── northwind.db                # Sample Northwind database
│   ├── chinook.db                  # Sample Chinook database
│   ├── connections.json            # Saved database connections (gitignored)
│   ├── dashboards.json             # Saved dashboards
│   ├── usage_metrics.json          # LLM usage history
│   └── snapshots/                  # Database backup files
├── static/
│   ├── css/
│   ├── js/
│   └── style.css                   # Complete design system (dark theme)
├── templates/
│   ├── base.html                   # Base layout
│   ├── index.html                  # Main query interface
│   ├── login.html                  # Login page
│   ├── overview.html               # Database overview
│   ├── analysis.html               # AI data analysis
│   ├── dashboards.html             # Dashboard listing
│   ├── dashboard_view.html         # Dashboard builder
│   ├── databases.html              # Connection manager
│   ├── admin.html                  # LLM admin panel
│   ├── review.html                 # Write query review
│   ├── insights.html               # Schema intelligence report
│   ├── snapshots.html              # Snapshot management
│   ├── create_database.html        # New database wizard
│   └── command_guide.html          # Command reference
├── .env                            # Your secrets (gitignored — never commit)
├── .env.example                    # Template — copy to .env and fill in values
└── requirements.txt
```

---

## Setup

### Prerequisites
- Python 3.11+
- A Groq API key — free at [console.groq.com](https://console.groq.com)
- [Ollama](https://ollama.com) *(optional — for local AI without an internet connection)*

### Install

```bash
# 1. Clone the repo
git clone <repo-url>
cd DATABASE-MANAGER

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
#    Open .env and set GROQ_API_KEY_1 and SECRET_KEY
```

### Configure `.env`

```ini
# At minimum, set these two:
GROQ_API_KEY_1=your_groq_api_key_here
SECRET_KEY=<run: python -c "import secrets; print(secrets.token_hex(32))">

# Add up to 5 more keys for automatic round-robin rotation on rate limits:
GROQ_API_KEY_2=
GROQ_API_KEY_3=
GROQ_API_KEY_4=
GROQ_API_KEY_5=
GROQ_API_KEY_6=

# Never enable debug in production:
FLASK_DEBUG=false
```

### Run

```bash
python app.py
```

Open `http://127.0.0.1:5000` in your browser.

### Demo Accounts

| Username | Password | Role |
|----------|----------|------|
| `admin1` | `admin123` | Admin — full access |
| `editor1` | `editor123` | Editor — read + write |
| `viewer1` | `viewer123` | Viewer — read only |

---

## API Reference

### Authentication
| Method | Route | Description |
|--------|-------|-------------|
| POST | `/login` | Session login |
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
| POST | `/api/analyze-direct` | Analyze a table or SQL result |
| POST | `/analyze` | Analyze last query results |
| POST | `/analyze-csv` | Analyze uploaded CSV |
| POST | `/api/ask` | Ask any question about the database |
| POST | `/api/insights` | Generate schema intelligence report |
| GET | `/api/tables-list` | List tables with row counts |
| POST | `/api/table-preview` | Preview first 10 rows of a table |

### Database Overview
| Method | Route | Description |
|--------|-------|-------------|
| GET | `/overview` | Overview page |
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
| POST | `/api/query` | Execute widget query |

### Database Management
| Method | Route | Description |
|--------|-------|-------------|
| GET | `/databases` | Connection manager |
| POST | `/databases/add` | Add connection |
| POST | `/databases/test` | Test saved connection |
| POST | `/databases/test-new` | Test before saving |
| POST | `/databases/select` | Switch active database |
| POST | `/databases/delete` | Remove connection |

### LLM Administration
| Method | Route | Description |
|--------|-------|-------------|
| GET | `/admin` | Admin dashboard |
| POST | `/admin/llm/config` | Update provider / active model |
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

## How It Works

### Query Flow
1. User types a natural language command — *"show top 5 customers"*
2. System checks hardcoded commands first (instant, no LLM needed)
3. If not hardcoded: schema (tables, columns, FKs, indexes, sample data) is sent to the LLM
4. LLM returns dialect-specific SQL
5. Validator checks safety — blocks DROP, TRUNCATE, ALTER, injection patterns
6. **READ** queries execute immediately, results paginated in the UI
7. **WRITE** queries go to the human review page with dry-run option
8. If SQL fails or is ambiguous, the system falls back to AI Ask — answers in plain English

### Analysis Flow
1. User picks a table or writes custom SQL on the Analysis page
2. First 10 rows are shown as a data preview
3. On "Analyze": up to 200 rows are sent to Groq
4. Groq returns JSON: markdown insights + chart configuration
5. Chart.js renders the visualization
6. Results can be exported as PowerPoint

### Dashboard Flow
1. User describes what they want — *"sales overview"*
2. Groq generates 4-6 widget configs with working SQL (JSON mode for reliability)
3. Dashboard is saved and user is redirected to the builder
4. Each widget queries live data from the database on every page load
5. Users can add or remove widgets manually using the table picker

### Key Rotation Flow
1. App starts — `groq_keys.py` loads up to 6 keys from `.env`
2. Every Groq call uses `get_current_key()`
3. On HTTP 429 (rate limit): `rotate()` advances to the next key and retries
4. After key 6 is exhausted, rotation wraps back to key 1
5. If all keys are exhausted, Groq calls fall through to the Ollama local fallback

---

## Design

The UI uses a custom dark theme inspired by Linear, Raycast, and ChatGPT:

- Fixed top navigation with compact section links
- Collapsible sidebar with query history (hamburger toggle on mobile)
- ChatGPT-style floating input bar pinned to the bottom
- Cards with subtle borders, no heavy drop shadows
- Responsive grid layouts for all screen sizes
- Chart.js for all data visualizations
- Marked.js for AI markdown response rendering

---

*Meridian Data — Built as a Minor Project for DBMS coursework.*
