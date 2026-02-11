
# AI Database Manager — Requirements Document

---

## 1. Problem Statement

This project explores how local large language models can safely interact with structured databases using natural language. Traditional database systems require SQL knowledge, which limits accessibility for non-expert users. Existing AI-based solutions often rely on cloud APIs and execute generated queries without sufficient safeguards.

The goal of this system is to build an offline, human-in-the-loop database manager that converts natural language to SQL while ensuring safe, transparent, and reversible execution. The project focuses on reliability, guardrails, and practical integration of local LLMs into real database workflows.

### Current Challenges

- SQL syntax knowledge required for database operations
- Risk of destructive operations without preview mechanisms
- Lack of offline AI-powered database tools
- No built-in rollback mechanisms for write operations
- Cloud-based solutions expose sensitive data to external services

---

## 2. Goals

### Primary Goals

1. **Democratize Database Access:** Enable users without SQL knowledge to interact with databases using natural language
2. **Ensure Data Safety:** Prevent accidental data loss through validation, preview, and undo mechanisms
3. **Maintain Privacy:** Operate entirely offline using local LLM infrastructure
4. **Human Oversight:** Require explicit user approval before executing any database operation

### Secondary Goals

1. Provide transparent SQL generation for educational purposes
2. Support all standard CRUD operations (Create, Read, Update, Delete)
3. Deliver a responsive, intuitive web interface
4. Minimize setup complexity for end users

---

## 3. Functional Requirements

### 3.1 Natural Language Processing

**FR-1:** The system shall accept natural language queries in English describing database operations.

**FR-2:** The system shall classify user input into categories:
- Schema inspection (list tables, describe structure)
- Data retrieval (SELECT)
- Data insertion (INSERT)
- Data modification (UPDATE)
- Data deletion (DELETE)

**FR-3:** The system shall provide database schema context to the LLM for accurate SQL generation.

**FR-4:** The system shall generate a single, executable SQL statement from natural language input.

### 3.2 SQL Review and Validation

**FR-5:** The system shall display generated SQL to the user before execution.

**FR-6:** The system shall validate SQL statements to ensure:
- Only one statement per request
- No dangerous operations (DROP, TRUNCATE, ALTER on restricted tables)
- Syntactic correctness

**FR-7:** The system shall allow users to approve or reject generated SQL.

**FR-8:** The system shall prevent automatic execution of any SQL statement.

### 3.3 Database Operations

**FR-9:** The system shall execute SELECT queries and display results in tabular format.

**FR-10:** The system shall support INSERT operations with user confirmation.

**FR-11:** The system shall support UPDATE operations with user confirmation.

**FR-12:** The system shall support DELETE operations with affected row count preview.

**FR-13:** The system shall handle schema inspection queries (list tables, describe columns) without LLM involvement.

### 3.4 Safety Mechanisms

**FR-14:** The system shall create automatic snapshots before any write operation (INSERT, UPDATE, DELETE).

**FR-15:** The system shall provide an "Undo" function to restore the database to the previous snapshot.

**FR-16:** The system shall display the number of rows affected by DELETE operations before execution.

**FR-17:** The system shall block SQL statements containing multiple commands or dangerous keywords.

### 3.5 User Interface

**FR-18:** The system shall provide a web-based interface accessible via standard browsers (Chrome, Safari, Edge, Firefox).

**FR-19:** The system shall display:
- Input field for natural language commands
- Generated SQL review page
- Query results in formatted tables
- Execution status messages
- Undo option for write operations

**FR-20:** The system shall provide clear error messages for invalid inputs or failed operations.

---

## 4. Non-Functional Requirements

### 4.1 Performance

**NFR-1:** SQL generation shall complete within 10 seconds for typical queries.

**NFR-2:** Database queries shall execute within 5 seconds for datasets under 100,000 rows.

**NFR-3:** Snapshot creation shall complete within 3 seconds for databases under 100MB.

### 4.2 Usability

**NFR-4:** The system shall require no more than 3 clicks to execute a database operation.

**NFR-5:** The interface shall be responsive and functional on desktop browsers with minimum 1280x720 resolution.

**NFR-6:** Error messages shall be user-friendly and actionable.

### 4.3 Reliability

**NFR-7:** The system shall handle LLM connection failures gracefully with informative error messages.

**NFR-8:** Database snapshots shall be stored reliably with integrity verification.

**NFR-9:** The system shall prevent data corruption through transaction management.

### 4.4 Security

**NFR-10:** The system shall operate entirely offline without external API calls.

**NFR-11:** The system shall not expose database credentials in logs or UI.

**NFR-12:** The system shall sanitize user inputs to prevent injection attacks.

### 4.5 Maintainability

**NFR-13:** The codebase shall follow modular architecture with clear separation of concerns:
- Database operations (db.py)
- LLM interaction (llm.py)
- SQL validation (validator.py)
- Snapshot management (snapshot.py)

**NFR-14:** The system shall include inline documentation for core functions.

**NFR-15:** Configuration parameters (LLM endpoint, database path) shall be externalized.

### 4.6 Portability

**NFR-16:** The system shall run on Windows 10+, macOS 11+, and Linux distributions with Python 3.10+.

**NFR-17:** The system shall use SQLite as the database engine (no external database server required).

**NFR-18:** The system shall support any Ollama-compatible LLM model.

---

## 5. Constraints

### 5.1 Technical Constraints

**C-1:** The system is limited to SQLite databases (no PostgreSQL, MySQL, etc.).

**C-2:** The system requires Ollama to be installed and running locally.

**C-3:** The system requires Python 3.10 or higher.

**C-4:** LLM accuracy depends on the quality of the Mistral model and prompt engineering.

### 5.2 Operational Constraints

**C-5:** The system is designed for single-user operation (no multi-user concurrency).

**C-6:** The system is intended for development, testing, and prototyping—not production environments.

**C-7:** Snapshot storage is limited by available disk space.

**C-8:** The system does not support real-time collaboration or concurrent database access.

### 5.3 Design Constraints

**C-9:** The system must maintain a human-in-the-loop design (no autonomous execution).

**C-10:** The UI must function without JavaScript frameworks (vanilla HTML/CSS/JS).

**C-11:** The system must not require internet connectivity after initial setup.

---
## Design Philosophy

This system prioritizes safety and user control over full automation. 
Instead of allowing autonomous execution, all generated SQL must be 
reviewed by the user before execution. Write operations are protected 
through snapshot-based rollback to prevent irreversible data loss.

The project is designed as an exploration of reliable LLM-assisted tools 
rather than a fully autonomous agent, focusing on practical integration, 
debuggability, and trust in AI-assisted workflows.

## 6. Success Criteria

### 6.1 Functional Success

**SC-1:** Users can successfully execute SELECT, INSERT, UPDATE, and DELETE operations using natural language with 90%+ accuracy for common queries.

**SC-2:** All write operations create snapshots and can be undone successfully.

**SC-3:** DELETE operations display accurate row counts before execution.

**SC-4:** The system blocks 100% of dangerous SQL operations (DROP, TRUNCATE, etc.).

### 6.2 Usability Success

**SC-5:** Users with no SQL knowledge can complete basic database tasks (view data, add records) within 5 minutes of first use.

**SC-6:** The SQL review interface clearly displays generated queries with syntax highlighting or formatting.

**SC-7:** Error messages guide users toward corrective actions in 100% of failure cases.

### 6.3 Technical Success

**SC-8:** The system operates fully offline after initial setup and model download.

**SC-9:** The application starts successfully on Windows, macOS, and Linux with documented setup steps.

**SC-10:** The system handles databases up to 500MB without performance degradation.

### 6.4 Safety Success

**SC-11:** Zero data loss incidents occur during testing with proper undo functionality.

**SC-12:** All SQL statements are validated before execution with zero bypasses.

**SC-13:** Snapshot integrity is maintained across 1000+ write operations.

---

## 7. Out of Scope

The following features are explicitly excluded from the current version:

- Multi-user authentication and authorization
- Support for non-SQLite databases
- Real-time collaboration features
- Advanced SQL features (stored procedures, triggers, views)
- Data visualization and charting
- Export to CSV/Excel
- Query history and audit logs
- Scheduled or automated queries
- Mobile application interface
- Cloud deployment or SaaS offering

---

## 8. Dependencies

### 8.1 External Dependencies

- **Ollama:** Local LLM runtime (version 0.1.0+)
- **Mistral Model:** LLM for SQL generation
- **Python:** Runtime environment (3.10+)
- **Flask:** Web framework (2.0+)
- **SQLite:** Database engine (3.35+)

### 8.2 Python Libraries

- `flask` - Web application framework
- `requests` - HTTP client for Ollama API
- `sqlite3` - Database interface (standard library)
- `shutil` - File operations for snapshots (standard library)

---

## 9. Assumptions

1. Users have basic understanding of database concepts (tables, rows, columns)
2. Ollama service is running and accessible at `http://localhost:11434`
3. The Mistral model is pre-downloaded via `ollama pull mistral`
4. Users have read/write permissions for the database file and snapshot directory
5. The database schema is relatively stable (not frequently changing)
6. Natural language inputs are in English
7. Users will review generated SQL before execution

---

## 10. Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| LLM generates incorrect SQL | High | Medium | Human review required before execution; validation layer |
| Snapshot storage exhaustion | Medium | Low | Implement snapshot rotation; document storage requirements |
| Ollama service unavailable | High | Low | Clear error messaging; connection retry logic |
| Browser compatibility issues | Low | Low | Test on major browsers; use standard HTML/CSS |
| Database corruption | High | Very Low | Use SQLite transactions; maintain snapshot backups |
| Poor LLM performance on complex queries | Medium | Medium | Document limitations; provide example queries |

---

## 11. Acceptance Criteria

The system will be considered complete when:

1. All functional requirements (FR-1 through FR-20) are implemented and tested
2. All safety mechanisms (FR-14 through FR-17) function correctly
3. The system passes end-to-end testing on Windows and macOS
4. Documentation (README, setup guide) is complete and validated
5. The system successfully handles the example queries listed in README.md
6. Code review confirms adherence to modular architecture (NFR-13)
7. Performance benchmarks meet specified thresholds (NFR-1, NFR-2, NFR-3)

---

## 12. Future Enhancements (Roadmap)

### Phase 2 (Post-MVP)

- Execution history and audit logs
- DELETE confirmation dialogs with affected row preview
- SQL diff preview for UPDATE operations
- Pagination and sorting for large result sets
- Query result export (CSV, JSON)

### Phase 3 (Advanced Features)

- Support for PostgreSQL and MySQL
- Role-based access control
- Multi-user support with session management
- Advanced analytics and data visualization
- Natural language query suggestions

---

## Appendix A: Glossary

- **LLM:** Large Language Model - AI system trained to understand and generate human language
- **Ollama:** Open-source tool for running LLMs locally
- **Mistral:** Open-source LLM model optimized for instruction following
- **CRUD:** Create, Read, Update, Delete - fundamental database operations
- **Snapshot:** Point-in-time copy of the database for rollback purposes
- **Schema:** Structure definition of database tables and columns
- **Human-in-the-loop:** Design pattern requiring human approval for critical actions

---

## Appendix B: References

- SQLite Documentation: https://www.sqlite.org/docs.html
- Ollama Documentation: https://ollama.com
- Flask Documentation: https://flask.palletsprojects.com/
- Mistral AI: https://mistral.ai/

---