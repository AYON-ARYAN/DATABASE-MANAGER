# Live Functional Test Results (captured 2026-05-25, admin session, Default SQLite = Chinook clone)

## Hardcoded DBMS commands (LLM bypass) — deterministic, sub-20ms
| Command | Task | HTTP | Latency | Cols | Rows | Notes |
|---|---|---|---|---|---|---|
| show tables | SYSTEM | 200 | 12 ms | 1 | 12 | 11 Chinook tables + DummyTableTest |
| describe Customer | SYSTEM | 200 | 4 ms | 5 | 19 | columns + FKs + indexes + row-count rows |
| show foreign keys | SYSTEM | 200 | 3 ms | 4 | 11 | all FK relationships |
| show indexes | SYSTEM | 200 | 2 ms | 4 | 11 | all indexes |
| show constraints | SYSTEM | 200 | 3 ms | 3 | 55 | PK/FK/NOT NULL/UNIQUE |
| show table counts | SYSTEM | 200 | 16 ms | 2 | 12 | per-table row counts |
| show create table Album | SYSTEM | 200 | 2 ms | 1 | 1 | DDL string |

## NL->SQL generation (Groq llama-3.3-70b-versatile fallback; Ollama offline)
| NL command | Task | Latency | Generated SQL | Result |
|---|---|---|---|---|
| "how many invoices are there per country" | READ | ~740 ms | SELECT BillingCountry, COUNT(InvoiceId) ... GROUP BY BillingCountry ORDER BY ... | 25 rows; USA 91, Canada 56, France 35 |
| "list the top 5 genres by number of tracks" | READ | ~780 ms | SELECT Genre.Name, COUNT(Track.TrackId) ... LEFT JOIN ... GROUP BY ... ORDER BY ... LIMIT 5 | 5 rows |
| "list top 10 customers by total spent" | READ | ~800 ms | SELECT FirstName, LastName, SUM(Total) ... INNER JOIN Invoice ... GROUP BY CustomerId ORDER BY TotalSpent DESC | 10 rows |

## Safety / RBAC / human-in-the-loop
| Command | Outcome | Latency | Evidence |
|---|---|---|---|
| "insert a new genre called Lofi" | WRITE -> needs_review=true, NOT executed | 610 ms | SQL: INSERT INTO Genre (Name) VALUES ('Lofi') routed to review page |
| "drop table Artist" | NOT executed (no SCHEMA-drop ran; table intact) | 703 ms | destructive DDL never reached DB |
| "truncate table Invoice" | BLOCKED: "ADMIN not allowed to run UNKNOWN" | 187 ms | is_safe rejects TRUNCATE -> not promoted to READ -> blocked |
| "delete from Customer where CustomerId=1" | BLOCKED: "ADMIN not allowed to run UNKNOWN" | 108 ms | rejected by validation gate |

## Observed limitation (report honestly)
The JSON `/api/command` endpoint echoes the *previous* executed READ query's result set
(sql + rows lag by one request) due to reading session `last_read_sql` set on a prior
request; WRITE->review and blocked responses are returned correctly in-request. The
server-rendered Jinja path renders within the same request. Worth noting in Limitations.

## Environment
- Server: Flask dev server, http://127.0.0.1:5001, debug on
- Active DB: "Default SQLite" (db/main.db, Chinook schema, 11 tables)
- Provider chain: Mistral selected -> Ollama offline -> automatic Groq fallback succeeded
