# System Design Document: AI-Powered Database Manager

**Project Name:** AI Database Manager (Local LLM Powered)  
**Version:** 1.0  
**Date:** February 11, 2026  
**Document Type:** Technical Design Specification

---

## Table of Contents

1. [Overview](#1-overview)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Component Design](#3-component-design)
4. [Data Flow](#4-data-flow)
5. [LLM Interaction Design](#5-llm-interaction-design)
6. [Safety and Validation Design](#6-safety-and-validation-design)
7. [Snapshot and Undo Design](#7-snapshot-and-undo-design)
8. [API Design](#8-api-design)
9. [Database Schema](#9-database-schema)
10. [Design Decisions and Tradeoffs](#10-design-decisions-and-tradeoffs)
11. [Error Handling Strategy](#11-error-handling-strategy)
12. [Performance Considerations](#12-performance-considerations)
13. [Security Considerations](#13-security-considerations)
14. [Testing Strategy](#14-testing-strategy)
15. [Future Improvements](#15-future-improvements)

---
## Components

### 1. Web Interface (Flask + HTML/CSS)
Provides user interface for:
- Natural language input
- SQL review before execution
- Query result display
- Undo actions

### 2. LLM Interface Layer
Handles:
- Prompt construction with schema context
- Communication with local Ollama server
- SQL generation from user input

### 3. Schema Introspection Layer
Extracts:
- Table names
- Column structures
- Database metadata  
This context is provided to the LLM to improve SQL accuracy.

### 4. SQL Validation Layer
Ensures:
- Only single SQL statement executed
- Dangerous operations blocked
- Queries classified (READ / WRITE / SCHEMA)

### 5. Execution Engine
Handles:
- Safe execution of SQL queries
- Returning results to UI
- Error handling and reporting

### 6. Snapshot & Undo System
Before any write operation:
- Database snapshot is stored
- Undo restores previous snapshot
- Prevents irreversible data loss

## Data Flow

1. User enters natural language command in UI
2. System checks if command is system-handled (e.g., list tables)
3. If not, schema context is retrieved
4. Prompt is sent to local LLM
5. LLM generates SQL query
6. SQL is shown to user for review
7. Validator checks safety
8. If approved → execution
9. If write operation → snapshot taken before execution
10. Results displayed in UI
11. Undo available for write operations

## Key Design Tradeoffs

### Local LLM vs Cloud APIs
Chosen for privacy, offline operation, and full control over execution.

### Human-in-the-loop vs Autonomous execution
Prevents accidental destructive queries and increases trust in system.

### SQLite vs Full DBMS
Chosen for simplicity and portability for a prototype system.

### Rule-based validation alongside LLM
Improves reliability instead of trusting model output blindly.

### Snapshot-based undo vs transaction rollback
Snapshots provide simple and reliable recovery for local databases.

## Future Improvements

- Add embeddings-based schema retrieval
- Query history and audit logging
- Multi-database support (Postgres/MySQL)
- Role-based access control
- Query explanation mode
- RAG-based documentation querying
- Autonomous agent mode with stronger guardrails

## 1. Overview

This project is a local AI-powered database manager that converts natural language commands into SQL queries using a locally running LLM (Ollama + Mistral). The system is designed with a strong emphasis on safety, human review, and recoverability.

Instead of allowing fully autonomous execution, all generated SQL is reviewed and validated before execution. Write operations are protected through snapshot-based rollback to ensure that database changes remain reversible.

The goal of this project is to explore reliable integration of local LLMs into real developer tools rather than building an unrestricted autonomous agent.

### 1.1 Purpose

This document describes the technical architecture and design of the AI Database Manager, a system that enables natural language interaction with SQLite databases using a locally-hosted Large Language Model (LLM). The design prioritizes safety, transparency, and offline operation.

### 1.2 Design Principles

1. **Human-in-the-Loop:** No SQL executes without explicit user approval
2. **Fail-Safe:** Default to safety over convenience
3. **Transparency:** Show all generated SQL before execution
4. **Reversibility:** Support undo for destructive operations
5. **Simplicity:** Minimize dependencies and complexity
6. **Offline-First:** No external API dependencies

### 1.3 Technology Stack

| Layer | Technology | Justification |
|-------|-----------|---------------|
| Frontend | HTML/CSS/JavaScript | Minimal dependencies, universal browser support |
| Backend | Flask (Python) | Lightweight, easy to deploy, excellent SQLite support |
| Database | SQLite | Serverless, portable, zero-configuration |
| LLM Runtime | Ollama | Local execution, model-agnostic, simple API |
| LLM Model | Mistral 7B | Open-source, good instruction following, reasonable size |

---

## 2. High-Level Architecture

### 2.1 System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         User (Browser)                       │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Flask Web Application                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                  Route Handlers                       │  │
│  │  • /          (Home page)                            │  │
│  │  • /process   (NL → SQL generation)                  │  │
│  │  • /execute   (SQL execution)                        │  │
│  │  • /undo      (Rollback operation)                   │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   LLM Core   │  │  Validator   │  │   Snapshot   │
│   (llm.py)   │  │(validator.py)│  │(snapshot.py) │
└──────┬───────┘  └──────────────┘  └──────┬───────┘
       │                                     │
       ▼                                     │
┌──────────────┐                            │
│   Ollama     │                            │
│   Service    │                            │
│ (localhost)  │                            │
└──────────────┘                            │
                                            │
        ┌───────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────┐
│          Database Layer (db.py)          │
│  ┌────────────────────────────────────┐ │
│  │     SQLite Connection Manager      │ │
│  └────────────────────────────────────┘ │
└────────────────┬─────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│         SQLite Database (main.db)        │
└──────────────────────────────────────────┘
```

### 2.2 Architectural Layers

#### Presentation Layer
- **Responsibility:** User interface, input collection, result display
- **Components:** HTML templates (index.html, review.html)
- **Technology:** Static HTML/CSS with minimal JavaScript

#### Application Layer
- **Responsibility:** Request routing, business logic orchestration
- **Components:** Flask routes, request handlers
- **Technology:** Flask web framework

#### Business Logic Layer
- **Responsibility:** Core functionality (SQL generation, validation, execution)
- **Components:** LLM interface, validator, snapshot manager
- **Technology:** Python modules

#### Data Layer
- **Responsibility:** Database operations, persistence
- **Components:** Database manager, SQLite connection
- **Technology:** SQLite with Python sqlite3 library

#### External Services Layer
- **Responsibility:** LLM inference
- **Components:** Ollama API client
- **Technology:** HTTP REST API to localhost:11434

---

## 3. Component Design

### 3.1 Component Overview

## High-Level Architecture

User (Browser UI)
   ↓
Flask Backend
   ↓
Intent + Safety Layer
   ↓
Local LLM (Ollama - Mistral)
   ↓
SQL Validator
   ↓
SQLite Database
   ↓
Snapshot & Undo System

```
core/
├── db.py          # Database operations and connection management
├── llm.py         # LLM interaction and prompt engineering
├── validator.py   # SQL validation and safety checks
└── snapshot.py    # Database snapshot and undo functionality
```

### 3.2 Database Manager (db.py)

**Purpose:** Centralized database access and schema introspection

**Key Responsibilities:**
- Establish and manage SQLite connections
- Execute SQL queries with error handling
- Retrieve database schema information
- Provide transaction management

**Interface:**

```python
class DatabaseManager:
    def __init__(self, db_path: str)
    def get_connection() -> sqlite3.Connection
    def execute_query(sql: str) -> List[Dict]
    def execute_write(sql: str) -> int  # Returns affected rows
    def get_schema() -> Dict[str, List[str]]  # {table: [columns]}
    def get_table_list() -> List[str]
    def close()
```

**Design Decisions:**
- **Connection pooling:** Not implemented (single-user, low concurrency)
- **Transaction management:** Explicit commits for write operations
- **Schema caching:** Fetched on-demand (schema changes are rare)

### 3.3 LLM Interface (llm.py)

**Purpose:** Interact with Ollama API to generate SQL from natural language

**Key Responsibilities:**
- Format prompts with schema context
- Send requests to Ollama API
- Parse and extract SQL from LLM responses
- Handle LLM errors and timeouts

**Interface:**

```python
class LLMInterface:
    def __init__(self, model: str = "mistral", endpoint: str = "http://localhost:11434")
    def generate_sql(prompt: str, schema: Dict) -> str
    def is_available() -> bool
```

**Prompt Engineering Strategy:**

```
System Context:
- Database schema (tables and columns)
- SQL dialect (SQLite)
- Output format requirements

User Input:
- Natural language command

Expected Output:
- Single SQL statement
- No explanations or markdown
```

### 3.4 SQL Validator (validator.py)

**Purpose:** Ensure SQL safety before execution

**Key Responsibilities:**
- Validate SQL syntax
- Detect dangerous operations
- Ensure single-statement execution
- Classify SQL intent (SELECT, INSERT, UPDATE, DELETE)

**Interface:**

```python
class SQLValidator:
    def validate(sql: str) -> ValidationResult
    def get_intent(sql: str) -> str  # "SELECT", "INSERT", "UPDATE", "DELETE"
    def is_safe(sql: str) -> bool
    def count_statements(sql: str) -> int
```

**Validation Rules:**

| Rule | Description | Action |
|------|-------------|--------|
| Single statement | Only one SQL command allowed | Reject if multiple |
| Dangerous keywords | Block DROP, TRUNCATE, ALTER | Reject immediately |
| Syntax check | Valid SQLite syntax | Parse and validate |
| Intent classification | Determine operation type | Used for safety logic |

### 3.5 Snapshot Manager (snapshot.py)

**Purpose:** Create and restore database snapshots for undo functionality

**Key Responsibilities:**
- Create database file copies before writes
- Restore database from snapshot
- Manage snapshot storage
- Clean up old snapshots

**Interface:**

```python
class SnapshotManager:
    def __init__(self, db_path: str, snapshot_dir: str = "snapshots/")
    def create_snapshot() -> str  # Returns snapshot ID
    def restore_snapshot(snapshot_id: str) -> bool
    def get_latest_snapshot() -> Optional[str]
    def cleanup_old_snapshots(keep_last: int = 5)
```

**Storage Strategy:**
- Snapshots stored as `snapshot_<timestamp>.db`
- Only last 5 snapshots retained (configurable)
- Atomic file operations to prevent corruption

---

## 4. Data Flow

### 4.1 End-to-End Request Flow

#### Phase 1: Natural Language Input

```
User Input → Flask Route (/process) → Intent Classification
                                            │
                                            ├─→ Schema Query? → Direct Response
                                            │
                                            └─→ Data Operation → LLM Processing
```

#### Phase 2: SQL Generation

```
Natural Language → Prompt Construction → Ollama API → SQL Extraction → Validation
                        ↑                                                   │
                        │                                                   │
                   Schema Context                                           │
                                                                            ▼
                                                                    Review Page
```

#### Phase 3: Execution

```
User Approval → Intent Check → Snapshot (if write) → Execute → Display Results
                                                          │
                                                          └─→ Store Snapshot ID
```

#### Phase 4: Undo (Optional)

```
Undo Request → Retrieve Latest Snapshot → Restore Database → Confirm Success
```

### 4.2 Sequence Diagram: SELECT Query

```
User          Flask         LLM          Validator      Database
 │              │            │              │              │
 │─"Show customers"─>│       │              │              │
 │              │────────>│  │              │              │
 │              │   Generate SQL            │              │
 │              │<────────│  │              │              │
 │              │            │              │              │
 │              │────────────────>│         │              │
 │              │      Validate   │         │              │
 │              │<────────────────│         │              │
 │              │                           │              │
 │<─Review Page─│                           │              │
 │              │                           │              │
 │─"Execute"──>│                           │              │
 │              │───────────────────────────────>│        │
 │              │                           │    Execute   │
 │              │<───────────────────────────────│        │
 │<─Results────│                           │              │
```

### 4.3 Sequence Diagram: DELETE Query with Undo

```
User          Flask      Validator   Snapshot    Database
 │              │            │           │           │
 │─"Delete ID 5"─>│          │           │           │
 │              │──>LLM──>│  │           │           │
 │<─Review Page─│          │           │           │
 │              │            │           │           │
 │─"Execute"──>│            │           │           │
 │              │────────>│  │           │           │
 │              │  Validate  │           │           │
 │              │<────────│  │           │           │
 │              │            │           │           │
 │              │────────────────>│      │           │
 │              │      Create Snapshot   │           │
 │              │<────────────────│      │           │
 │              │                         │           │
 │              │─────────────────────────────>│     │
 │              │              Execute DELETE  │     │
 │              │<─────────────────────────────│     │
 │<─Success────│                         │           │
 │              │                         │           │
 │─"Undo"────>│                         │           │
 │              │────────────────>│      │           │
 │              │      Restore Snapshot  │           │
 │              │<────────────────│      │           │
 │<─Restored───│                         │           │
```

---

## 5. LLM Interaction Design

### 5.1 Prompt Engineering

**Prompt Template:**

```
You are a SQL expert. Generate a single SQLite query based on the user's request.

DATABASE SCHEMA:
{schema_information}

RULES:
1. Output ONLY the SQL statement
2. No explanations, no markdown, no code blocks
3. Use SQLite syntax
4. Generate exactly ONE statement
5. Use proper table and column names from the schema

USER REQUEST:
{user_input}

SQL:
```

**Schema Formatting:**

```
Table: customers
Columns: CustomerId, FirstName, LastName, Email, Phone

Table: invoices
Columns: InvoiceId, CustomerId, InvoiceDate, Total
```

### 5.2 LLM Communication Protocol

**Request Format (Ollama API):**

```json
{
  "model": "mistral",
  "prompt": "<formatted_prompt>",
  "stream": false,
  "options": {
    "temperature": 0.1,
    "top_p": 0.9
  }
}
```

**Response Parsing:**

```python
def extract_sql(llm_response: str) -> str:
    # Remove markdown code blocks
    sql = llm_response.strip()
    sql = sql.replace("```sql", "").replace("```", "")
    
    # Extract first statement
    sql = sql.split(";")[0].strip()
    
    return sql
```

### 5.3 Error Handling

| Error Type | Cause | Mitigation |
|------------|-------|------------|
| Connection refused | Ollama not running | Clear error message with setup instructions |
| Timeout | Slow inference | 30-second timeout, retry option |
| Invalid response | LLM hallucination | Validation layer catches issues |
| Model not found | Mistral not pulled | Check model availability on startup |

---

## 6. Safety and Validation Design

### 6.1 Multi-Layer Safety Architecture

```
User Input
    │
    ▼
┌─────────────────────┐
│  Intent Detection   │  ← Classify operation type
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  SQL Validation     │  ← Syntax and safety checks
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Human Review       │  ← User approval required
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Pre-Execution      │  ← Snapshot for writes
│  Snapshot           │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Execution          │  ← Actual database operation
└─────────────────────┘
```

### 6.2 Validation Rules Implementation

**Dangerous Keyword Detection:**

```python
DANGEROUS_KEYWORDS = [
    "DROP", "TRUNCATE", "ALTER", "CREATE", "PRAGMA",
    "ATTACH", "DETACH", "VACUUM"
]

def contains_dangerous_keywords(sql: str) -> bool:
    sql_upper = sql.upper()
    return any(keyword in sql_upper for keyword in DANGEROUS_KEYWORDS)
```

**Statement Count Validation:**

```python
def count_statements(sql: str) -> int:
    # Remove string literals to avoid false positives
    cleaned = re.sub(r"'[^']*'", "", sql)
    return cleaned.count(";") + 1
```

**Intent Classification:**

```python
def classify_intent(sql: str) -> str:
    sql_upper = sql.strip().upper()
    
    if sql_upper.startswith("SELECT"):
        return "SELECT"
    elif sql_upper.startswith("INSERT"):
        return "INSERT"
    elif sql_upper.startswith("UPDATE"):
        return "UPDATE"
    elif sql_upper.startswith("DELETE"):
        return "DELETE"
    else:
        return "UNKNOWN"
```

### 6.3 DELETE Preview Mechanism

**Implementation:**

```python
def preview_delete(sql: str) -> int:
    # Convert DELETE to SELECT COUNT(*)
    # DELETE FROM table WHERE condition
    # → SELECT COUNT(*) FROM table WHERE condition
    
    preview_sql = sql.upper().replace("DELETE", "SELECT COUNT(*)", 1)
    result = execute_query(preview_sql)
    return result[0]["COUNT(*)"]
```

**User Flow:**

1. User approves DELETE SQL
2. System executes preview query
3. Display: "This will delete X rows. Confirm?"
4. User confirms → Execute with snapshot
5. User cancels → Abort operation

---

## 7. Snapshot and Undo Design

### 7.1 Snapshot Architecture

**Design Goals:**
- Fast snapshot creation (< 3 seconds for 100MB databases)
- Reliable restoration
- Minimal storage overhead
- Automatic cleanup

**Storage Structure:**

```
project_root/
├── db/
│   └── main.db              # Active database
└── snapshots/
    ├── snapshot_20260211_110530.db
    ├── snapshot_20260211_110645.db
    └── snapshot_20260211_110812.db
```

### 7.2 Snapshot Creation Process

```
Write Operation Detected
    │
    ▼
Generate Snapshot ID (timestamp)
    │
    ▼
Close Active Connections
    │
    ▼
Copy Database File (shutil.copy2)
    │
    ▼
Verify Copy Integrity (file size check)
    │
    ▼
Store Snapshot Metadata
    │
    ▼
Return Snapshot ID
```

**Implementation:**

```python
def create_snapshot(self) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_id = f"snapshot_{timestamp}"
    snapshot_path = os.path.join(self.snapshot_dir, f"{snapshot_id}.db")
    
    # Ensure no active transactions
    self.db_manager.close()
    
    # Copy database file
    shutil.copy2(self.db_path, snapshot_path)
    
    # Verify integrity
    if os.path.getsize(snapshot_path) != os.path.getsize(self.db_path):
        raise SnapshotError("Snapshot verification failed")
    
    return snapshot_id
```

### 7.3 Restoration Process

```
Undo Request
    │
    ▼
Retrieve Latest Snapshot ID
    │
    ▼
Verify Snapshot Exists
    │
    ▼
Close Active Connections
    │
    ▼
Backup Current Database (safety)
    │
    ▼
Replace Database with Snapshot
    │
    ▼
Verify Restoration
    │
    ▼
Reopen Connections
```

**Implementation:**

```python
def restore_snapshot(self, snapshot_id: str) -> bool:
    snapshot_path = os.path.join(self.snapshot_dir, f"{snapshot_id}.db")
    
    if not os.path.exists(snapshot_path):
        raise SnapshotError(f"Snapshot {snapshot_id} not found")
    
    # Close connections
    self.db_manager.close()
    
    # Create safety backup
    backup_path = f"{self.db_path}.backup"
    shutil.copy2(self.db_path, backup_path)
    
    try:
        # Restore snapshot
        shutil.copy2(snapshot_path, self.db_path)
        return True
    except Exception as e:
        # Rollback to backup
        shutil.copy2(backup_path, self.db_path)
        raise SnapshotError(f"Restoration failed: {e}")
    finally:
        # Cleanup backup
        if os.path.exists(backup_path):
            os.remove(backup_path)
```

### 7.4 Snapshot Lifecycle Management

**Retention Policy:**
- Keep last 5 snapshots by default
- Automatic cleanup after each new snapshot
- Manual cleanup option available

**Cleanup Strategy:**

```python
def cleanup_old_snapshots(self, keep_last: int = 5):
    snapshots = sorted(
        [f for f in os.listdir(self.snapshot_dir) if f.endswith(".db")],
        key=lambda x: os.path.getmtime(os.path.join(self.snapshot_dir, x)),
        reverse=True
    )
    
    # Remove old snapshots
    for snapshot in snapshots[keep_last:]:
        os.remove(os.path.join(self.snapshot_dir, snapshot))
```

### 7.5 Tradeoffs

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| Full file copy | Simple, reliable, complete state | Storage overhead, slower for large DBs | **Selected** - Simplicity priority |
| Transaction log | Space-efficient, fast | Complex implementation, SQLite limitations | Rejected |
| Incremental backup | Efficient storage | Complex, requires tracking changes | Rejected |
| WAL mode snapshots | Fast, SQLite native | Requires WAL mode, complexity | Future consideration |

---

## 8. API Design

### 8.1 HTTP Endpoints

#### GET /

**Purpose:** Render home page with input form

**Response:**
- HTML page (index.html)
- Input field for natural language
- Example queries

---

#### POST /process

**Purpose:** Convert natural language to SQL

**Request Body:**

```json
{
  "query": "Show first 5 customers"
}
```

**Response (Success):**

```json
{
  "status": "success",
  "sql": "SELECT * FROM customers LIMIT 5",
  "intent": "SELECT",
  "safe": true
}
```

**Response (Error):**

```json
{
  "status": "error",
  "message": "LLM service unavailable"
}
```

---

#### POST /execute

**Purpose:** Execute validated SQL

**Request Body:**

```json
{
  "sql": "SELECT * FROM customers LIMIT 5",
  "intent": "SELECT"
}
```

**Response (SELECT):**

```json
{
  "status": "success",
  "results": [
    {"CustomerId": 1, "FirstName": "John", "LastName": "Doe"},
    {"CustomerId": 2, "FirstName": "Jane", "LastName": "Smith"}
  ],
  "row_count": 2
}
```

**Response (INSERT/UPDATE/DELETE):**

```json
{
  "status": "success",
  "affected_rows": 1,
  "snapshot_id": "snapshot_20260211_110530",
  "message": "Operation completed successfully"
}
```

---

#### POST /undo

**Purpose:** Restore last snapshot

**Request Body:**

```json
{
  "snapshot_id": "snapshot_20260211_110530"
}
```

**Response:**

```json
{
  "status": "success",
  "message": "Database restored to previous state"
}
```

---

### 8.2 Internal Module APIs

**DatabaseManager API:**

```python
# Connection management
get_connection() -> sqlite3.Connection
close() -> None

# Query execution
execute_query(sql: str) -> List[Dict[str, Any]]
execute_write(sql: str) -> int

# Schema operations
get_schema() -> Dict[str, List[str]]
get_table_list() -> List[str]
describe_table(table_name: str) -> List[Dict]
```

**LLMInterface API:**

```python
# SQL generation
generate_sql(prompt: str, schema: Dict) -> str

# Health check
is_available() -> bool
get_model_info() -> Dict
```

**SQLValidator API:**

```python
# Validation
validate(sql: str) -> ValidationResult
is_safe(sql: str) -> bool

# Analysis
get_intent(sql: str) -> str
count_statements(sql: str) -> int
extract_table_names(sql: str) -> List[str]
```

**SnapshotManager API:**

```python
# Snapshot operations
create_snapshot() -> str
restore_snapshot(snapshot_id: str) -> bool
get_latest_snapshot() -> Optional[str]

# Management
list_snapshots() -> List[str]
cleanup_old_snapshots(keep_last: int) -> None
```

---

## 9. Database Schema

### 9.1 Application Database

The system uses the user's existing SQLite database. No application-specific tables are created in the user database.

### 9.2 Metadata Storage

**Option 1: In-Memory (Current Implementation)**
- Snapshot metadata stored in memory
- Lost on application restart
- Simple, no schema pollution

**Option 2: Separate Metadata DB (Future)**

```sql
CREATE TABLE snapshots (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_path TEXT NOT NULL,
    file_size INTEGER,
    operation_type TEXT,
    sql_executed TEXT
);

CREATE TABLE execution_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    natural_language TEXT,
    generated_sql TEXT,
    intent TEXT,
    status TEXT,
    affected_rows INTEGER,
    snapshot_id TEXT,
    FOREIGN KEY (snapshot_id) REFERENCES snapshots(id)
);
```

---

## 10. Design Decisions and Tradeoffs

### 10.1 Key Design Decisions

#### Decision 1: Local LLM vs Cloud API

**Options:**
- A) Cloud API (OpenAI, Anthropic)
- B) Local LLM (Ollama)

**Decision:** Local LLM (B)

**Rationale:**
- Privacy: No data leaves user's machine
- Cost: No API fees
- Offline: Works without internet
- Control: Model selection flexibility

**Tradeoffs:**
- Lower accuracy than GPT-4
- Requires local setup
- Hardware requirements

---

#### Decision 2: Human-in-the-Loop vs Autonomous Execution

**Options:**
- A) Auto-execute generated SQL
- B) Require human approval

**Decision:** Human approval (B)

**Rationale:**
- Safety: Prevents accidental data loss
- Trust: Users see what will execute
- Learning: Educational value
- Debugging: Easier to identify LLM errors

**Tradeoffs:**
- Extra click required
- Slower workflow

---

#### Decision 3: Snapshot Strategy

**Options:**
- A) Full database copy
- B) Transaction log replay
- C) SQLite backup API

**Decision:** Full database copy (A)

**Rationale:**
- Simplicity: Easy to implement and understand
- Reliability: Complete state capture
- Portability: Standard file operations

**Tradeoffs:**
- Storage: Larger disk usage
- Speed: Slower for large databases
- Scalability: Not suitable for multi-GB databases

---

#### Decision 4: Single vs Multi-Statement Execution

**Options:**
- A) Allow multiple SQL statements
- B) Restrict to single statement

**Decision:** Single statement (B)

**Rationale:**
- Safety: Reduces attack surface
- Predictability: Clear intent
- Validation: Easier to analyze
- LLM behavior: More reliable generation

**Tradeoffs:**
- Flexibility: Can't batch operations
- Efficiency: Multiple requests for related tasks

---

#### Decision 5: Frontend Framework

**Options:**
- A) React/Vue.js SPA
- B) Vanilla HTML/CSS/JS
- C) Server-side rendering only

**Decision:** Vanilla HTML/CSS/JS (B)

**Rationale:**
- Simplicity: No build process
- Dependencies: Minimal external libraries
- Performance: Fast page loads
- Compatibility: Works everywhere

**Tradeoffs:**
- Features: Limited interactivity
- Development: More manual DOM manipulation
- Maintainability: Less structured than frameworks

---

### 10.2 Tradeoff Analysis

| Aspect | Chosen Approach | Alternative | Justification |
|--------|----------------|-------------|---------------|
| **LLM Hosting** | Local (Ollama) | Cloud API | Privacy, offline capability |
| **Database** | SQLite | PostgreSQL | Simplicity, portability |
| **Undo Mechanism** | File snapshots | Transaction logs | Implementation simplicity |
| **Validation** | Pre-execution | Post-execution rollback | Proactive safety |
| **UI Architecture** | Server-rendered | SPA | Minimal dependencies |
| **Concurrency** | Single-user | Multi-user | Scope limitation |
| **Authentication** | None | User accounts | Prototype scope |
| **Snapshot Storage** | Local filesystem | Cloud storage | Offline operation |

---

## 11. Error Handling Strategy

### 11.1 Error Categories

#### User Errors
- Invalid natural language input
- Ambiguous requests
- References to non-existent tables

**Handling:** Clear error messages with suggestions

---

#### LLM Errors
- Connection failures
- Timeout
- Invalid SQL generation
- Model hallucinations

**Handling:** Fallback messages, retry options, validation layer

---

#### Database Errors
- Syntax errors
- Constraint violations
- Lock timeouts
- Disk space issues

**Handling:** Transaction rollback, user-friendly error translation

---

#### System Errors
- Snapshot creation failure
- File permission issues
- Disk full

**Handling:** Graceful degradation, clear error reporting

---

### 11.2 Error Response Format

```json
{
  "status": "error",
  "error_type": "validation_error",
  "message": "SQL contains dangerous keywords",
  "details": "DROP TABLE is not allowed",
  "suggestion": "Try rephrasing your request",
  "recoverable": true
}
```

### 11.3 Logging Strategy

**Log Levels:**
- ERROR: System failures, data corruption risks
- WARNING: LLM issues, validation failures
- INFO: Successful operations, snapshots created
- DEBUG: SQL generation, validation details

**Log Format:**

```
[2026-02-11 11:05:30] [INFO] [db.py:45] Query executed: SELECT * FROM customers LIMIT 5
[2026-02-11 11:05:35] [WARNING] [llm.py:78] LLM timeout, retrying...
[2026-02-11 11:05:40] [ERROR] [snapshot.py:102] Snapshot creation failed: Disk full
```

---

## 12. Performance Considerations

### 12.1 Performance Targets

| Operation | Target | Measurement |
|-----------|--------|-------------|
| SQL generation | < 10s | LLM inference time |
| Query execution | < 5s | For 100K rows |
| Snapshot creation | < 3s | For 100MB database |
| Page load | < 1s | Initial render |
| Undo operation | < 5s | Restoration time |

### 12.2 Optimization Strategies

#### LLM Performance
- **Temperature tuning:** Lower temperature (0.1) for deterministic output
- **Prompt optimization:** Minimal context, clear instructions
- **Model selection:** Balance between size and accuracy

#### Database Performance
- **Connection reuse:** Single connection per request
- **Query optimization:** LIMIT clauses for large result sets
- **Index awareness:** LLM prompted to use indexed columns

#### Snapshot Performance
- **Incremental approach (future):** Only snapshot changed data
- **Compression (future):** Compress old snapshots
- **Async operations (future):** Background snapshot creation

#### Frontend Performance
- **Minimal JavaScript:** Reduce parsing time
- **CSS optimization:** Inline critical styles
- **Result pagination (future):** Limit displayed rows

### 12.3 Scalability Limits

**Current Design Limits:**
- Database size: ~500MB (snapshot overhead)
- Result set: ~10,000 rows (browser rendering)
- Concurrent users: 1 (no session management)
- Snapshot retention: 5 snapshots (disk space)

**Scaling Strategies (Future):**
- Streaming results for large queries
- Incremental snapshot system
- Multi-user session management
- Result export instead of display

---

## 13. Security Considerations

### 13.1 Threat Model

**In Scope:**
- SQL injection via LLM manipulation
- Accidental data deletion
- Unauthorized schema modifications
- Local file system access

**Out of Scope:**
- Network attacks (offline system)
- Multi-user authorization
- Encryption at rest
- Audit compliance

### 13.2 Security Measures

#### SQL Injection Prevention

```python
# Validation layer blocks dangerous patterns
BLOCKED_PATTERNS = [
    r";\s*DROP",
    r";\s*DELETE",
    r"UNION\s+SELECT",
    r"--",
    r"/\*.*\*/"
]

def contains_injection_pattern(sql: str) -> bool:
    return any(re.search(pattern, sql, re.IGNORECASE) 
               for pattern in BLOCKED_PATTERNS)
```

#### File System Security
- Restrict database path to configured directory
- Validate snapshot paths to prevent directory traversal
- Use absolute paths for all file operations

#### Input Sanitization
- Limit natural language input length (1000 chars)
- Strip control characters
- Validate UTF-8 encoding

### 13.3 Security Best Practices

1. **Principle of Least Privilege:** Application runs with user permissions only
2. **Defense in Depth:** Multiple validation layers
3. **Fail Secure:** Default to rejection on validation errors
4. **Audit Trail:** Log all write operations (future)
5. **Secure Defaults:** Dangerous operations disabled by default

---

## 14. Testing Strategy

### 14.1 Unit Testing

**Components to Test:**
- `validator.py`: SQL validation logic
- `snapshot.py`: Snapshot creation and restoration
- `llm.py`: Prompt formatting, response parsing
- `db.py`: Query execution, schema retrieval

**Test Coverage Target:** 80%+

**Example Test Cases:**

```python
# validator_test.py
def test_dangerous_keyword_detection():
    assert validator.is_safe("SELECT * FROM users") == True
    assert validator.is_safe("DROP TABLE users") == False
    assert validator.is_safe("DELETE FROM users; DROP TABLE users") == False

def test_statement_count():
    assert validator.count_statements("SELECT * FROM users") == 1
    assert validator.count_statements("SELECT * FROM users; SELECT * FROM orders") == 2
```

### 14.2 Integration Testing

**Test Scenarios:**
1. End-to-end SELECT query flow
2. INSERT with snapshot creation
3. DELETE with preview and undo
4. LLM unavailable handling
5. Invalid SQL generation recovery

### 14.3 User Acceptance Testing

**Test Cases:**
- Non-technical user can execute basic queries
- SQL review page is understandable
- Error messages are actionable
- Undo functionality works as expected

### 14.4 Performance Testing

**Benchmarks:**
- SQL generation time for various query complexities
- Snapshot creation time for different database sizes
- Query execution time for large result sets

---

## 15. Future Improvements

### 15.1 Short-Term Enhancements (Phase 2)

#### 1. Execution History

**Feature:** Track all executed queries with timestamps

**Benefits:**
- Audit trail
- Query reuse
- Learning from past interactions

**Implementation:**
```sql
CREATE TABLE query_history (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME,
    natural_language TEXT,
    generated_sql TEXT,
    status TEXT,
    affected_rows INTEGER
);
```

---

#### 2. DELETE Confirmation Dialog

**Feature:** Explicit confirmation before DELETE execution

**Benefits:**
- Additional safety layer
- Prevents accidental deletions
- Shows affected row count

**UI Flow:**
```
Review SQL → Preview Affected Rows → Confirmation Dialog → Execute
```

---

#### 3. UPDATE Preview

**Feature:** Show before/after values for UPDATE operations

**Implementation:**
```python
def preview_update(sql: str) -> Dict:
    # Extract WHERE clause
    # SELECT current values
    # Show proposed changes
    return {"before": [...], "after": [...]}
```

---

#### 4. Result Pagination

**Feature:** Paginate large result sets

**Benefits:**
- Better browser performance
- Improved UX for large queries
- Reduced memory usage

---

### 15.2 Medium-Term Enhancements (Phase 3)

#### 1. Multi-Database Support

**Feature:** Support PostgreSQL, MySQL, MariaDB

**Challenges:**
- Dialect-specific SQL generation
- Different snapshot mechanisms
- Connection management complexity

---

#### 2. Query Optimization Suggestions

**Feature:** LLM suggests index creation or query improvements

**Example:**
```
"This query scans 1M rows. Consider adding an index on 'email' column."
```

---

#### 3. Natural Language Result Explanation

**Feature:** LLM explains query results in plain English

**Example:**
```
Query: "Show top 5 customers by spending"
Explanation: "These are the 5 customers who have spent the most money, 
with John Doe leading at $5,432."
```

---

#### 4. Batch Operations

**Feature:** Execute multiple related operations

**Example:**
```
"Add 3 new customers: John, Jane, and Bob"
→ 3 INSERT statements with single snapshot
```

---

### 15.3 Long-Term Vision (Phase 4)

#### 1. Multi-User Support

**Features:**
- User authentication
- Role-based access control
- Session management
- Concurrent query execution

---

#### 2. Advanced Analytics

**Features:**
- Data visualization (charts, graphs)
- Trend analysis
- Anomaly detection
- Natural language reporting

---

#### 3. Schema Evolution Support

**Features:**
- Track schema changes
- Migration suggestions
- Backward compatibility checks

---

#### 4. Collaborative Features

**Features:**
- Share queries with team
- Comment on results
- Query templates library
- Best practices suggestions

---

### 15.4 Technical Debt and Refactoring

**Current Technical Debt:**
1. No comprehensive error handling in LLM module
2. Snapshot cleanup is manual
3. No connection pooling
4. Limited test coverage
5. Hardcoded configuration values

**Refactoring Priorities:**
1. Extract configuration to config file
2. Implement proper logging framework
3. Add comprehensive unit tests
4. Refactor validation logic into rule engine
5. Implement async snapshot creation

---

## 16. Deployment and Operations

### 16.1 Deployment Architecture

**Single-Machine Deployment:**

```
User Machine
├── Python 3.10+ Runtime
├── Ollama Service (background)
├── Flask Application (foreground)
└── SQLite Database (file)
```

**No external dependencies or services required.**

### 16.2 Configuration Management

**Configuration File (config.yaml):**

```yaml
database:
  path: "db/main.db"
  
llm:
  endpoint: "http://localhost:11434"
  model: "mistral"
  timeout: 30
  temperature: 0.1

snapshot:
  directory: "snapshots/"
  retention_count: 5
  auto_cleanup: true

server:
  host: "127.0.0.1"
  port: 5000
  debug: false

validation:
  max_input_length: 1000
  allow_multiple_statements: false
  dangerous_keywords: ["DROP", "TRUNCATE", "ALTER"]
```

### 16.3 Monitoring and Observability

**Metrics to Track:**
- Query success/failure rate
- Average SQL generation time
- Snapshot creation frequency
- Database size growth
- Error frequency by type

**Health Checks:**
- Ollama service availability
- Database connectivity
- Disk space for snapshots
- Application responsiveness

---

## 17. Conclusion

### 17.1 Design Summary

The AI Database Manager implements a safety-first architecture for natural language database interaction. Key design principles include:

1. **Human oversight** at every critical decision point
2. **Multi-layer validation** to prevent dangerous operations
3. **Reversibility** through snapshot-based undo
4. **Transparency** by showing all generated SQL
5. **Privacy** through local-only operation

### 17.2 Success Criteria

The design will be considered successful if:

- Users can execute common database operations without SQL knowledge
- Zero data loss incidents occur in testing
- The system operates reliably offline
- Setup complexity is minimal (< 15 minutes)
- LLM-generated SQL is correct 90%+ of the time for common queries

### 17.3 Next Steps

1. **Implementation:** Build core modules following this design
2. **Testing:** Comprehensive unit and integration tests
3. **Documentation:** User guide and API documentation
4. **Validation:** User acceptance testing with non-technical users
5. **Iteration:** Refine based on feedback and real-world usage

---

## Appendix A: Glossary

- **LLM:** Large Language Model - AI system for natural language understanding
- **Ollama:** Local LLM runtime environment
- **Snapshot:** Point-in-time database backup for undo functionality
- **Intent:** Classification of SQL operation type (SELECT, INSERT, etc.)
- **Validation:** Process of checking SQL safety before execution
- **Human-in-the-loop:** Design requiring human approval for critical actions
- **Schema:** Database structure definition (tables, columns, types)

---

## Appendix B: References

### Technical Documentation
- SQLite Documentation: https://www.sqlite.org/docs.html
- Ollama API Reference: https://github.com/ollama/ollama/blob/main/docs/api.md
- Flask Documentation: https://flask.palletsprojects.com/
- Python sqlite3 Module: https://docs.python.org/3/library/sqlite3.html

### Research Papers
- "Language Models as Database Interfaces" (2023)
- "Safety Considerations in AI-Powered Code Generation" (2024)
- "Prompt Engineering for SQL Generation" (2024)

### Related Projects
- Text-to-SQL benchmarks (Spider, WikiSQL)
- Natural language database interfaces
- LLM-powered development tools

---

**Document Version:** 1.0  
**Last Updated:** February 11, 2026  
**Authors:** Engineering Team  
**Status:** Final for Phase 1 Implementation  
**Next Review:** March 11, 2026
