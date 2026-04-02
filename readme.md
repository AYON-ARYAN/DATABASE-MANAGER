# Meridian Data

### AI-Powered Database Explorer & DBMS Teaching Tool

Meridian Data is a full-stack database exploration platform that lets you query any database using plain English. It converts natural language into validated SQL, executes queries safely, and generates insights, charts, and presentations — all through a clean, modern dark-mode interface.

Built for students, teachers, and analysts who want to explore databases without writing SQL from scratch.

**Supports**: SQLite, PostgreSQL, MySQL, MSSQL, Oracle, MongoDB, Cassandra, Redis

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
- Python 3.11+
- [Ollama](https://ollama.com) (optional, for local AI)
- Groq API key (free at [console.groq.com](https://console.groq.com))

### Installation

```bash
# Clone and enter
cd "MINOR PROJECT"

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure API key
echo "GROQ_API_KEY=your_key_here" > .env

# (Optional) Pull a local model
ollama pull mistral

# Run
python app.py
```

### Access
Open `http://127.0.0.1:5000` in your browser.

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
