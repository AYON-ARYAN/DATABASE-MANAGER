# Meridian Data — AI Analysis, Dashboard, Export & Frontend Layers

Technical research notes for the B.Tech mini-project report. All findings are derived
directly from source. File:line citations are given for load-bearing logic.

Project root: `/Volumes/BLACK_SHARK/MINOR_PROJECT`

---

## 1. AI ANALYSIS ENGINE — `core/analyzer.py`

The analysis engine is a thin orchestration layer over the **Groq** cloud LLM. A single
module-level client is created from the `GROQ_API_KEY` environment variable, wrapped in a
`try/except` so the app degrades gracefully (`GROQ_CLIENT = None`) when no key is present
(`core/analyzer.py:15-18`). Every public function first checks `if not GROQ_CLIENT` and
returns a `{"error": ...}` dict instead of raising. The model used throughout is
**`llama-3.3-70b-versatile`** (a Llama 3.3 70B model served by Groq).

Across all calls the engine relies on Groq's JSON-mode where structured output is needed
(`response_format={"type": "json_object"}`) and plain text where Markdown is wanted.
Temperatures are kept low for determinism: 0.2 for data/JSON tasks, 0.3 for the
conversational/Q&A and BI-report tasks.

### 1.1 `analyze_data(columns, rows, user_hint="")` — single dataset → insight + chart
(`core/analyzer.py:27-120`)

- Validates that columns and rows exist.
- **Row budget sent to the LLM:** the data is truncated to the **first 100 rows**
  (`max_rows = 100`, `core/analyzer.py:41-42`). If the dataset was larger, an explicit
  note `*(Note: Data truncated to first 100 rows for analysis)*` is appended
  (`:55-56`).
- The rows are rendered as a **Markdown table** (header row + `---` separator + data
  rows) so the model sees tabular structure (`:44-54`). A scalar row is coerced to a
  one-element list defensively (`:50-51`).
- An optional `user_hint` is prepended ("User Request/Hint: ...") so the user can steer
  the analysis (`:58`).
- The prompt demands **raw JSON only** (no markdown fences) with this exact shape
  (`:68-82`):
  ```json
  {
    "summary": "detailed insightful summary (answers the hint if given)",
    "chart": {
      "type": "pie",
      "title": "Title of the chart",
      "labels": ["Label1", "Label2"],
      "datasets": [ { "label": "Dataset Label", "data": [10, 20] } ]
    }
  }
  ```
- **Chart-type selection is delegated to the LLM**, constrained to one of six types:
  `"pie", "bar", "line", "doughnut", "area", "scatter"` (`:85`). The prompt embeds a
  "SMART RECOMMENDATION" rubric mapping data shape → chart type (pie/doughnut = parts of a
  whole; bar = categorical comparison; line = trend over time; area = volume trend;
  scatter = correlation of two numeric variables) (`:89-95`). For scatter, both `data`
  and `labels` must be numeric (X-axis) (`:88`).
- Call config: model `llama-3.3-70b-versatile`, system prompt "data analysis engine that
  outputs strict JSON", `temperature=0.2`, JSON response format (`:99-107`).
- Defensive parsing strips stray ```` ```json ```` / ```` ``` ```` fences before
  `json.loads` (`:111-117`). All failures return `{"error": "Analysis failed: ..."}`.

### 1.2 `ai_ask(question, schema, db_name, table_stats=None, dialect="sqlite", fk_info=None)` — Q&A with full DB context
(`core/analyzer.py:123-212`)

- General-purpose "DBMS teaching assistant" Q&A. The prompt is assembled from:
  - the full **schema** string (columns, types, PKs, FKs, indexes, *and sample data*),
  - optional **table statistics** ("`table: N rows`" lines, `:133-137`),
  - optional **foreign-key relationships** ("`from_table.col -> to_table.col`" lines,
    `:139-143`).
- **Dialect awareness:** a `dialect_map` translates 9 dialect keys
  (`sqlite, postgresql, mysql, mssql, oracle, mongodb, cassandra, redis`) into
  human-readable names, and the prompt forces "SQL that is valid for {dialect} syntax
  only" (`:145-150`, `:164-170`).
- The model is told to answer in **clean Markdown** (headers, bullets, SQL code blocks)
  and, at the very end, append a sentinel section `---SUGGESTED_QUERIES---` followed by a
  JSON array of 3 follow-up queries (`:179-184`).
- This is **not** JSON mode (`temperature=0.3`, no `response_format`) — it returns prose
  (`:187-194`). The code then splits on `---SUGGESTED_QUERIES---`, takes the prose half as
  `answer`, and `json.loads` the second half into `suggested_queries` (silently `[]` on
  failure) (`:198-209`). Returns `{"answer": ..., "suggested_queries": [...]}`.

### 1.3 `get_table_overview(schema, db_name, table_stats, dialect="sqlite")` — overview dashboard report
(`core/analyzer.py:215-295`)

- Powers the Overview page. JSON-mode call returning a fixed structure (`:244-265`):
  - `summary` — a 2-3 paragraph executive summary,
  - `highlights` — label/value stat cards (Total Tables, Total Rows, Foreign Keys,
    Largest Table),
  - `table_size_chart` — `{labels[], data[]}` for ALL tables sorted by size,
  - `relationship_map` — list of `{from, to, via}` FK edges,
  - `suggested_queries` — 4-6 `{title, query, chart_type}` analytical queries.
- Same dialect-map enforcement and same fence-stripping/`json.loads` parsing.
  `temperature=0.2`.

### 1.4 `analyze_schema(schema, db_name)` — BI / schema report (Markdown)
(`core/analyzer.py:298-331`)

- "Data Architect / BI Analyst" prompt that returns a **pure Markdown** report (not JSON)
  with four sections: Executive Overview (purpose: e-commerce/HR/inventory etc.), Key
  Entities & Relationships, Data Quality & Schema Observations, and **Top 5 Business
  Questions** (`:311-317`). Returns `{"markdown": ...}`. `temperature=0.3`.

### 1.5 Full-Database Analysis pipeline (the most elaborate flow)

This is a **two-LLM-call, multi-step, asynchronous** pipeline with job tracking. State is
held in an in-process dict `_analysis_jobs` guarded by a `threading.Lock`
(`core/analyzer.py:23-24`). Jobs older than 10 minutes are garbage-collected
(`_gc_old_jobs`, `:553-559`).

**Job lifecycle:**
1. `start_full_analysis(connection_name, dialect)` (`:707-725`) — GCs stale jobs, mints a
   `uuid4` job id, seeds the job dict (`status="starting"`, `total_steps=4` placeholder),
   then launches `run_full_analysis_pipeline` on a **daemon `threading.Thread`** and
   returns the job id immediately (non-blocking).
2. `run_full_analysis_pipeline(job_id, connection_name, dialect)` (`:584-704`):
   - **Step 1 — collect schema:** gets adapter, schema, table list; computes per-table row
     counts via `SELECT COUNT(*)` and collects FK info (`:594-618`).
   - **Step 2 — generate queries (LLM call 1):** `generate_analytical_queries(...)`
     (`:337-424`) asks the model for **6-10 analytical SELECT queries** spanning six
     categories (distribution, top-N rankings, aggregations, cross-table joins, time
     trends, anomaly detection). Hard rules: all queries must be valid for the dialect,
     must be SELECT/read-only, and must include `LIMIT 500`. Output JSON is
     `{"queries": [{title, sql, chart_type}, ...]}`, **capped to 10** (`:419-422`).
   - **Steps 3..N — execute each query safely** (`:636-681`):
     - Each query is classified via `core.validator.classify_query`; non-`READ` queries
       are skipped with an explanatory error (`:651-654`).
     - `core.validator.is_safe` gates unsafe queries (`:657-660`).
     - For SQL dialects (not mongodb/redis) a `LIMIT 500` is injected if missing via
       `_ensure_limit` (`:576-581`, `:663-665`).
     - Execution runs on a single-worker `ThreadPoolExecutor` with a **30-second timeout**
       (`future.result(timeout=30)`); timeouts and exceptions are captured per-query
       (`:667-677`). Rows are normalised to plain lists.
   - **Step N+1 — generate report (LLM call 2):** `generate_full_report(...)`
     (`:430-541`). Each query's results are re-serialised as a Markdown table
     **truncated to 50 rows** for token budget (`rows = qr["rows"][:50]`, `:457`,
     with a "Showing 50 of N rows" note). The model returns
     `{"executive_summary": markdown, "insights": [{title, markdown, chart}, ...]}`; one
     insight per successfully-executed query, charts drawn from the same six types, pie/
     doughnut limited to top-10 categories. The original SQL is re-attached to each
     insight afterwards (`:534-537`).
   - Final state: `status="complete"`, `result=report`.
3. `get_job_status(job_id)` (`:562-573`) — returns `{status, progress, step, total_steps,
   result}` for the frontend's polling loop. `total_steps` is recomputed as
   `2 + len(queries) + 1` once query count is known (`:633`).

**Key numbers to cite in the report:**
- Single-dataset analysis sends **≤100 rows** to the LLM.
- Full-report synthesis sends **≤50 rows per query** to the LLM.
- Generated analytical queries: **6-10, capped at 10**, each forced `LIMIT 500`.
- Per-query execution timeout: **30 s**. Job TTL: **10 min**.
- Six supported chart types everywhere: `pie, bar, line, doughnut, area, scatter`.

---

## 2. DASHBOARD ENGINE — `core/dashboards.py`

This module is a **flat-file (JSON) CRUD store** for user-built dashboards — it does NOT
itself call the LLM (AI auto-generation of widgets is driven from the API/route layer and
the analyzer; this file is the persistence + manual-builder layer).

- **Persistence:** all dashboards live in a single file `db/dashboards.json`
  (`core/dashboards.py:6`). `_load_dashboards` returns `{"dashboards": []}` if the file is
  missing or unparseable (`:8-15`); `_save_dashboards` ensures the directory exists and
  writes pretty-printed JSON (`indent=2`) (`:17-20`).
- **CRUD surface:**
  - `list_dashboards()` (`:22-23`)
  - `get_dashboard(dashboard_id)` — linear lookup by id (`:25-30`)
  - `create_dashboard(name)` — appends `{id: uuid4, name, widgets: [], created_at:
    ISO-8601}` (`:32-42`)
  - `delete_dashboard(dashboard_id)` — filter-out by id (`:44-47`)
  - `add_widget(dashboard_id, title, query, chart_type="table", db_name="Default
    SQLite")` — appends a widget `{id: uuid4, title, query, chart_type, db_name,
    created_at}` (`:49-64`). **A widget is essentially a saved SQL query plus a chart
    type and the source DB name** — it stores no data, only the query.
  - `remove_widget(dashboard_id, widget_id)` (`:66-73`)
- **Live data fetch is client-side.** The widget stores only the query; the actual data is
  fetched at render time. In `templates/dashboard_view.html` each widget runs an async
  `POST /api/query` with `{query, db_name}` on page load (`dashboard_view.html:147-166`),
  then renders either a table (`renderTable`) or a Chart.js chart (`renderChart`). This is
  what "live data fetch" means here — dashboards always reflect current DB state because
  the query re-executes every view.
- **AI auto-generation (4-6 widgets) & manual builder:** the manual builder is the
  Add-Widget modal in `dashboard_view.html` (title, chart-type select of bar/line/pie/
  doughnut/table, a quick table-picker that auto-fills `SELECT * FROM "<table>" LIMIT 50`,
  or free-form SQL — `:50-81`, `:100-138`). AI auto-generation reuses the analyzer's
  `get_table_overview` / `generate_analytical_queries` `suggested_queries` (each carries a
  `chart_type`) which the route layer turns into widgets via `add_widget`. The JSON store
  is the single source of truth for both paths.

---

## 3. EXPORT LAYER

### 3.1 PowerPoint generation — `core/ppt_generator.py` (python-pptx)

A `PPTGenerator` class builds a **16:9** deck (`Inches(13.33) × Inches(7.5)`,
`ppt_generator.py:31-33`) with a futuristic dark aesthetic. Brand color tokens mirror the
web theme: dark bg `RGB(10,10,12)`, slate-50 text, slate-400 secondary, Apple-blue
`#0A84FF`, Gemini-purple `#8B5CF6`, ChatGPT-green `#10A37F` (`:17-22`).

Reusable helpers:
- `_add_background(slide)` — paints a full-bleed branded background image
  (`static/assets/meridian_bg.png`) when present, else falls back to a solid dark
  rectangle; always stamps a top-right "Meridian Data" brand label (`:36-71`).
- `_add_glass_panel(...)` — a rounded-rectangle "glassmorphism" panel (40% transparent
  dark fill, faint 0.5pt white hairline border) used as the visual container on every
  slide (`:73-88`).

**Slide builders (all use blank layout `slide_layouts[6]`):**
- `add_title_slide(subtitle)` — centred glass panel, 44pt bold title, purple accent line,
  22pt subtitle (`:90-127`).
- `add_text_slide(title, content)` — title ribbon + content panel; splits content on
  newlines into bullet paragraphs (strips leading `- *`), 18pt body (`:129-158`).
- `add_table_slide(title, columns, rows)` — native PPTX table; **caps to 10 columns and
  10 data rows**, header cells styled slate-800 fill / blue bold text, zebra striping on
  even rows, cell values truncated to 50 chars (`:160-216`).
- `add_chart_slide(title, chart_config)` — builds a `CategoryChartData`, coerces every
  value to float (non-numeric → 0) and pads/truncates to match labels, then maps the
  chart type via `chart_type_map`: **bar→COLUMN_CLUSTERED, line→LINE, pie→PIE,
  doughnut→DOUGHNUT, area→AREA** (`:263-269`); unknown types default to clustered column.
  Legend on, secondary-color legend font, chart title text-frame disabled. On any failure
  it degrades to a "chart could not be rendered" text box (`:218-290`). **Note: `scatter`
  is supported in the web charts but is NOT in the PPTX `chart_type_map`, so a scatter
  config falls through to clustered column.**
- `add_schema_slide(schema_text)` — monospace ("Consolas") schema dump truncated to the
  first 30 lines; lines containing `TABLE` are bold-blue, lines with `FOREIGN` are green
  (`:292-323`).
- `save()` — renders to an in-memory `io.BytesIO` and returns it (`:325-329`).

**Deck composition** is assembled by the Flask route `GET /export/ppt`
(`app.py:1288-1355`), which re-fetches data on demand (to keep the session cookie small)
and adds, in order: (1) **Title slide** (subtitle = the user's query), (2) **Schema slide**
(if schema available), (3) **Generated SQL** text slide, (4) **AI Logic Explanation** text
slide (if present), (5) **Query Results (Top 10)** table slide, (6) **AI Data Insights**
text slide + **Data Visualization** chart slide (only if a `last_analysis` with a `summary`/
`chart` is in session). The download name is `meridian_report_<unixtime>.pptx`.

### 3.2 CSV export — `GET /export` (`app.py:814-837`)

Reads `last_read_sql` from the session (redirects home if absent), re-executes it through
the active adapter, writes columns + all rows to an in-memory `StringIO` with the stdlib
`csv.writer`, and streams it as `text/csv` with
`Content-Disposition: attachment; filename=results.csv`. Re-execution (rather than caching
rows) keeps the session cookie small.

---

## 4. CSV INGESTION — `core/csv_parser.py`

A single function `parse_csv(file_content)` returning `(columns, rows)`
(`csv_parser.py:4-40`):
- Accepts `str` or `bytes`; bytes are decoded UTF-8 with `errors='replace'` (`:11-12`).
- Uses the stdlib `csv.reader` over a `StringIO`. The first row is taken as the header
  (`columns`); empty header → `([], [])` (`:14-19`).
- Each subsequent non-empty row is **type-coerced for better charting**: every cell is
  stripped, then parsed as `float` if it contains a `.`, else `int`, falling back to the
  raw string on `ValueError` (`:23-36`). This is what lets uploaded CSVs feed numeric
  chart axes directly.
- Any failure is re-raised as `ValueError("Failed to parse CSV: ...")` (`:39-40`).

This output `(columns, rows)` feeds straight into `analyzer.analyze_data(columns, rows,
hint)` via the `/analyze-csv` route used by both frontends.

---

## 5. FRONTEND — TWO PARALLEL UIs

Meridian Data ships **two** front-ends against the same Flask JSON API: a legacy
**server-rendered Jinja** UI (under `templates/` + `static/`) and a newer **React SPA**
(`meridian-frontend/`) mounted at the `/app` base path.

### 5.1 Server-rendered Jinja + Chart.js + Marked.js (dark theme)

**Templating & layout.** Pages extend a layered set of layouts: `base.html` →
`layouts/shell.html` (query/chat layout with a left **sidebar** for history + a fixed
bottom chat bar) or `layouts/page.html` (standard content pages). `shell.html` provides a
collapsible mobile sidebar via a `toggleSidebar()` JS toggle and `.sidebar.open` class
(`templates/layouts/shell.html:4-28`). Templates seen: `index.html` (query/chat),
`overview.html`, `analysis.html`, `dashboards.html`, `dashboard_view.html`, `databases.html`,
`create_database.html`, `admin.html`, `login.html`, `review.html`, `snapshots.html`,
`insights.html`, `command_guide.html`, `base_bare.html`.

**Vendored libraries (CDN):** Chart.js, Marked.js (Markdown→HTML), and on the Overview page
Mermaid 10 for the ER diagram — all pulled from `cdn.jsdelivr.net` per page via
`{% block head_extra %}` (`index.html:6-9`, `overview.html:7-11`, `analysis.html:7-10`).

**`index.html` — the query/chat page.** A ChatGPT-style single-textarea composer that
auto-grows up to 160px, submits on Enter (Shift+Enter = newline), and shows a top progress
bar (`TopProgress`) while POSTing the natural-language `command` to `/` (`:188-217`). The
sidebar lists query **history** with task badges (READ/WRITE/SCHEMA/SYSTEM) and click-to-
rerun (`:11-27`). A context bar lets the user switch the active DB and the LLM provider
(**Mistral** vs **Groq**, with a confirm dialog warning that Groq sends the schema to the
cloud — `:219-224`). Results render as an HTML table with **CSV / PPT / Analyze** export
links and Prev/Next pagination (`:65-96`); AI responses render Markdown client-side via
`marked.parse` into `#ai-response-body` (`:226-230`); a welcome state offers six "quick
card" example commands. Generated SQL and explanation are shown in `<pre>` cards.

**`analysis.html` — the AI analysis workbench.** Four source tabs: **From Table / Custom
SQL / Upload CSV / Entire Database** (`:25-54`). Behaviour:
- *Table* tab fetches `/api/tables-list`, renders clickable table chips with row counts,
  and previews data via `/api/table-preview`.
- *SQL* tab previews custom SELECTs.
- *CSV* tab uploads a file to `/analyze-csv` (multipart).
- Single-dataset analysis POSTs to `/api/analyze-direct`, renders the AI `summary` through
  `marked.parse` and the returned chart config through a local `renderChart()`.
- *Entire Database* tab kicks off the async pipeline: `POST /api/analyze-full` returns a
  `job_id` stored in `sessionStorage`, then a **2-second polling loop** hits
  `/api/analyze-full/status/<job_id>`, updating a step/total progress bar and status text;
  on completion it renders the executive summary + an insight grid (each insight = Markdown
  body + chart + collapsible `<details>` SQL) (`:225-303`). The poll auto-resumes on page
  reload if a job id is still in `sessionStorage` (`:350-353`).
- **Client-side charting** (`renderChart`/`renderInsightChart`) maps the analyzer's six
  types to Chart.js: `area` is rendered as a `line` with `fill:true`; `scatter` maps each
  value to `{x: label[i], y: value}` points; a fixed 10-color palette is used, with alpha
  suffixes for bars/areas (`:307-346`). Dark-theme axis/legend colors (`#71717a`,
  `#a1a1aa`) match the CSS tokens.

**`dashboard_view.html` — dashboard renderer.** Server-renders one card per widget, then a
per-widget IIFE `POST /api/query` fetches live data and calls `renderTable` or `renderChart`
(`:147-202`). An Add-Widget modal (title, chart-type select, quick table-pick auto-filling
`SELECT * FROM "<t>" LIMIT 50`, or custom SQL) POSTs to `/api/dashboards/<id>/widgets`;
delete is `DELETE /api/dashboards/<id>/widgets/<wid>`. Esc closes the modal.

**`overview.html` — database overview.** An "Ask anything" AI box (calls the Q&A endpoint,
renders Markdown answers + suggested-query chips), skeleton-loading stat cards, an Executive
Summary card, a **Table Sizes** bar chart, a textual relationships list, a **Mermaid
ER-diagram** section (with fullscreen + refresh), and a suggested-queries grid that opens a
query-result modal (`overview.html:24-120`).

**Design system / CSS.** The CSS was refactored from one monolith (`static/style.css.bak`,
~26 KB) into modular files under `static/css/`: `tokens.css`, `reset.css`, `layout.css`,
`nav.css`, `components.css`, `utilities.css`, `main.css`, plus a `pages/` folder. The theme
is a **near-black dark UI** built on CSS custom properties in `tokens.css`:
`--bg #09090b`, surfaces as low-alpha white overlays (`rgba(255,255,255,0.03/0.06)`),
hairline borders (`rgba(255,255,255,0.07)`), text ramp `#e4e4e7 / #a1a1aa / #52525b`, and an
accent set (blue `#3b82f6`, purple `#8b5cf6`, green `#22c55e`, red `#ef4444`, amber `#f59e0b`)
each with a translucent "-dim" variant (`tokens.css:7-33`). Radii scale `8/12/16/20px` +
full-pill; a 280px sidebar / 52px nav; a shared cubic-bezier transition; legacy aliases keep
older class names working (`:39-60`). The font is **Inter** (Google Fonts, weights 300-700).
Components (`components.css`) include `.card` (translucent surface, hover border-brighten),
status cards (`.success-card`/`.error-card`/`.warning-card`/`.notice-box`), and color-coded
`.badge.READ/WRITE/SCHEMA/SYSTEM` task chips. Vanilla-JS helpers live in `static/js/`:
`command-palette.js`, `table-sort.js`, `toast.js`.

### 5.2 React SPA — `meridian-frontend/`

A modern Vite-built React single-page app, clearly the intended successor UI.

**Framework / tooling (`package.json`):**
- **React 19** (`react`/`react-dom` ^19.2) with `StrictMode` (`src/main.jsx`).
- **Vite 8** as the build tool/dev server, with `@vitejs/plugin-react` and the
  **Tailwind CSS v4** Vite plugin (`@tailwindcss/vite`) — Tailwind v4 is the styling
  system (`vite.config.js:1-6`). ESLint 9 flat config for linting.
- **React Router v7** for routing (`react-router`), **TanStack React Query v5** for server
  state/caching (`retry:1`, `staleTime:30000` — `App.jsx:25-27`).
- **axios** HTTP client, **chart.js + react-chartjs-2** for charts, **react-markdown** for
  Markdown, **mermaid 11** for ER diagrams, **lucide-react** for icons.

**Dev proxy.** `vite.config.js` runs the dev server on **port 5173** and proxies API paths
(`/api`, `/admin`, `/databases`, `/export`, `/dry-run`, `/refine`, `/analyze`,
`/analyze-csv`) to the Flask backend on **`http://localhost:5001`** (`:7-19`). The built SPA
is served under the **`/app`** base path (React Router `basename="/app"`, `App.jsx:64`).

**API layer.** `src/api/` has one module per backend domain (`client.js`, `query.js`,
`analysis.js`, `dashboards.js`, `databases.js`, `overview.js`, `auth.js`, `admin.js`,
`snapshots.js`, `samples.js`, `commandCenter.js`, `joinCenter.js`). `client.js` configures a
shared axios instance with `withCredentials: true` (cookie/session auth) and a **401
interceptor** that redirects to `/login` (except on the login page or session-probe
requests) (`src/api/client.js:1-24`).

**App structure & routing (`App.jsx`).** Providers wrap the tree:
`QueryClientProvider → AuthProvider → ToastProvider → BrowserRouter`. Every route except
`/login` is wrapped in a `ProtectedRoute` that blocks until `useAuth().loading` resolves,
redirects unauthenticated users to `/login`, and (when authed) mounts a `DbProvider`
(`:29-34`). Three React contexts: `AuthContext`, `DbContext`, `ToastContext`.

**Pages (`src/pages/`, 17 total):** Login, Query (`/`), CommandCenter, CommandGuide,
Overview, Dashboards, DashboardView (`/dashboards/:id`), Analysis, Insights, Databases,
CreateDatabase, Snapshots, Admin, Samples, JoinCenter, Review. Navigation order comes from
`NAV_ITEMS` in `src/lib/constants.js`: Query, Command Center, Overview, Dashboards,
Analysis, Join Center, Databases, Samples, Snapshots, Admin (each with a lucide icon).

**Components.**
- `layout/Navbar.jsx` — fixed glassy top nav (`bg-zinc-950/80 backdrop-blur-xl`), gradient
  "Zap" logo, desktop link row with active-state highlighting, an active-DB pill, a
  **role badge** (ADMIN purple-pink / EDITOR blue-cyan / VIEWER emerald-teal gradients) +
  username + logout, and a collapsible **mobile hamburger menu** (`md:hidden`) — fully
  responsive (`Navbar.jsx`).
- `layout/AppShell.jsx` — page wrapper used by every page.
- `ui/` primitives: `Badge`, `Button`, `Card`, `EmptyState`, `Input`, `LoadingSpinner`,
  `Modal`.
- `data/ResultsTable.jsx`, `charts/ChartWrapper.jsx`.

**Charting (`components/charts/ChartWrapper.jsx`).** Registers Chart.js modules
(Category/Linear scales, Bar/Line/Arc/Point elements, Title/Tooltip/Legend/Filler) once,
and renders via react-chartjs-2's `Bar/Line/Pie/Doughnut` — with **`area` mapped to `Line`
+ `fill`** in both the component map and `buildDataset` (`:74-87`, `:109`). It shares the
same dark palette (`CHART_COLORS` in `constants.js`, ten hex colors) and dark
axis/legend/tooltip styling (`commonOptions`/`pieOptions`). Pie/doughnut get solid per-slice
colors with a near-black border; bars get alpha fills + rounded corners; line/area get a
tensioned curve. `maintainAspectRatio:false` inside a fixed-height div makes charts
responsive.

**Analysis page (`pages/AnalysisPage.jsx`).** A faithful React re-implementation of the
Jinja analysis workbench: same four tabs (Table/SQL/CSV/Full DB), table picker via
`getTablesList`, preview via `previewTable`, single analysis via `analyzeDirect`, CSV via a
raw `fetch('/analyze-csv')` multipart POST, and the **full-DB async pipeline** with the same
**2-second `setInterval` polling** of `getAnalysisStatus(job_id)` and a gradient progress bar
(`AnalysisPage.jsx:75-105`, `205-220`). Results render AI `summary`/`executive_summary`/per-
insight `markdown` through `react-markdown` and charts through `ChartWrapper`; insight SQL is
shown in a styled `<pre>` (`:222-277`). Tailwind utility classes give the "glass" card look
(`glass rounded-xl`, `border-l-4 border-purple-500`, `animate-fade-up`).

**Markdown rendering.** Jinja side uses **Marked.js** (`marked.parse`) injected into
`.markdown-body` containers; React side uses **react-markdown** `<ReactMarkdown>` into the
same `.markdown-body` class — consistent styling across both UIs.

**Build artifacts.** `meridian-frontend/dist/` contains the production build (hashed JS/CSS
chunks). Notably a large number of `mermaid` diagram chunks (flow, ER, class, sequence,
gantt, gitGraph, pie, sankey, etc.) are code-split out, confirming Mermaid is lazy-loaded
for the diagram/overview features. A `Dockerfile` + `nginx.conf` accompany the SPA for
containerised static hosting.

---

## Cross-cutting observations for the report

- **One LLM, two providers:** the analyzer module hardwires **Groq / llama-3.3-70b-versatile**;
  the query/NL→SQL path additionally exposes **Mistral vs Groq** selection in the UI
  (`index.html:46-50`), with an explicit privacy confirm before sending schema to Groq.
- **Determinism via low temperature + JSON mode** is the consistent design choice for all
  structured outputs; prose outputs (Q&A, BI report) use slightly higher temperature and
  Markdown.
- **Token-budget guards** appear at every LLM boundary: 100-row cap for direct analysis,
  50-row-per-query cap for the full report, `LIMIT 500` on generated queries, 10-query cap,
  10-row/10-column caps in the PPTX table.
- **Safety is enforced before execution**, not by the LLM: generated queries pass through
  `classify_query` + `is_safe` and a 30 s timeout before their results reach the report
  prompt.
- **The two frontends are feature-parallel** and talk to the identical Flask JSON API
  (session-cookie auth, role-based badges). The Jinja UI is server-rendered with CDN
  Chart.js/Marked/Mermaid; the React SPA is a Vite + React 19 + Tailwind v4 + React Query
  rebuild served under `/app`. Chart semantics (six types, `area`→filled line,
  scatter→{x,y} points, shared dark palette) are kept consistent between them.
- **Minor inconsistency worth a footnote:** `scatter` is offered by the analyzer/web charts
  but is absent from the PPTX `chart_type_map`, so exported scatter charts silently become
  clustered-column bars (`ppt_generator.py:263-273`).
