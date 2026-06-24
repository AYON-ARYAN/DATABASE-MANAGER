# Meridian Data — Database & Safety Layer (Research Note 02)

Scope: the data-access architecture (adapter pattern), the SQL/NoSQL safety
validator, the connection manager (encrypted credential store), the snapshot /
rollback engine, the human-in-the-loop write review + dry-run flow, and the
extracted schema of the bundled SQLite sample databases (for the ER diagram and
Dataset Description sections of the report).

All file/line citations refer to the repository at
`/Volumes/BLACK_SHARK/MINOR_PROJECT`.

---

## 1. The Adapter Pattern (multi-database support)

### 1.1 Why an adapter layer

Meridian Data is an AI NL→SQL explorer that must talk to *eight* heterogeneous
database engines — three of which (MongoDB, Cassandra, Redis) are not even SQL.
Rather than scattering engine-specific `if dialect == ...` branches through the
Flask app, the project uses the classic **Adapter (a.k.a. Gang-of-Four wrapper)
pattern**: a single abstract interface, `DatabaseAdapter`, defines every
operation the rest of the application is allowed to call; each engine gets one
concrete subclass that translates those calls into engine-native API calls.

The application code therefore never imports `psycopg2`, `pymongo`, etc. — it
only ever holds a `DatabaseAdapter` reference and calls methods like
`adapter.get_schema()` or `adapter.execute(query)`. New engines can be added
without touching the app: implement the interface and register the class.

### 1.2 The abstract base interface

File: `core/adapters/base.py`.

`DatabaseError(Exception)` (base.py:9) is the common exception type. The
interface is `class DatabaseAdapter(ABC)` (base.py:14), constructed with a plain
`config: dict` and a lazily-initialised connection handle `self._conn`
(base.py:21-23).

**Abstract methods every adapter MUST implement** (decorated `@abstractmethod`):

| Method | Line | Contract |
|---|---|---|
| `connect()` | base.py:28 | Establish a live connection. |
| `disconnect()` | base.py:33 | Close the connection. |
| `test_connection() -> bool` | base.py:38 | True if reachable. |
| `get_schema() -> str` | base.py:56 | Human-readable schema string **for LLM context** (the format the NL→SQL prompt is fed). |
| `list_tables() -> list` | base.py:67 | Table / collection names. |
| `execute(query) -> tuple` | base.py:75 | Returns `(columns, rows)` for reads; `([], [])` for writes. |

**Concrete (overridable, with default behaviour) methods** — these have working
defaults in the base class so a minimal adapter can skip them:

- `get_connection()` / `release_connection(conn)` (base.py:43-51) — the pooling
  hooks. Default `get_connection` lazily connects and returns the single
  persistent connection; default `release_connection` is a no-op (suits a
  singleton connection).
- `dry_run(query) -> dict` (base.py:84) — default returns
  `{"affected_rows": 0, "status": "Not implemented"}`.
- `preview_delete(query)` (base.py:94) — default `None`; SQL adapters override.
- `take_snapshot(filepath)` / `restore_snapshot(filepath)` (base.py:104-110) —
  default `raise NotImplementedError`.
- Introspection family: `get_foreign_keys()` (base.py:115, default `[]`),
  `get_indexes()` (base.py:122, default `[]`), `describe_table()` (base.py:129),
  `get_constraints()` (base.py:137, default `[]`), `get_create_table()`
  (base.py:144).

**Property hooks** (base.py:153-172):

- `dialect` — string id (`"sqlite"`, `"mysql"`, `"mongodb"`, …). Used everywhere
  the validator and snapshot engine need to branch.
- `is_nosql` — default `False`; MongoDB/Cassandra/Redis override to `True`. The
  app uses this to skip SQL pagination (`app.py:616`).
- `supports_snapshot` — default `False`; SQL adapters + Mongo override to `True`.
  The snapshot engine refuses to act if this is `False` (`snapshot.py:74`).
- `display_name` — pretty UI label from `DB_DISPLAY_NAMES`.

### 1.3 The registry (how a config string becomes an object)

File: `core/adapters/__init__.py`. A dict `ADAPTER_REGISTRY` (lines 15-24) maps
the eight dialect strings to their classes; `DB_TYPES` is the key list;
`DB_DISPLAY_NAMES` (29-38) the UI labels; `DB_CONNECTION_FIELDS` (41-93) drives
dynamic connection-form rendering (host/port/user/etc. per engine).
`get_adapter(db_type)` (96-101) is the **factory** — returns the class or raises
`ValueError` for an unknown type. This is the single seam the connection
manager uses to instantiate adapters.

```
ADAPTER_REGISTRY = {
  "sqlite": SQLiteAdapter, "mysql": MySQLAdapter, "postgresql": PostgresAdapter,
  "mssql": MSSQLAdapter, "oracle": OracleAdapter, "mongodb": MongoAdapter,
  "cassandra": CassandraAdapter, "redis": RedisAdapter,
}
```

### 1.4 How each concrete adapter implements the interface

| Adapter | File | Driver | Connection model / pooling | Snapshot mechanism |
|---|---|---|---|---|
| **SQLite** | `sqlite_adapter.py` | `sqlite3` (stdlib) | Single persistent connection, `check_same_thread=False` for Flask threads, `row_factory=Row` (lines 24-31). No pool — `release_connection` is a no-op (38-40). | **File copy** via `shutil.copy` of the `.db` file (314-328). |
| **PostgreSQL** | `postgres_adapter.py` | `psycopg2` | **Thread-safe pool** `psycopg2.pool.ThreadedConnectionPool(1, 10, …)` (36). `get_connection` borrows (`getconn`), `release_connection` returns (`putconn`) (43-50). | `pg_dump -F c` (custom format) / `pg_restore -1 -c` via `subprocess`, password via `PGPASSWORD` env (457-500). |
| **MySQL / MariaDB** | `mysql_adapter.py` | `pymysql` | **Hand-rolled pool** using a `queue.Queue(maxsize=10)`; pre-fills one connection, creates extras on demand when the queue is empty, closes surplus on release (26-66). `autocommit=True`, `utf8mb4`. | `mysqldump` / `mysql` CLI via `subprocess` (388-426). |
| **MSSQL / Azure SQL** | `mssql_adapter.py` | `pymssql` | Single connection per call; `connect()`→`execute`→`commit`→`disconnect` each time (no pool) (23-36, 168-183). | `sqlpackage` BACPAC `/Action:Export` and `/Action:Publish` (408-466). Code comments note remote-path limitations. |
| **Oracle** | `oracle_adapter.py` | `oracledb` (thin mode, no Instant Client) | Single connection per call, DSN `host:port/service_name` (18-25). | **No snapshot** (`supports_snapshot` left at base default `False`); no snapshot methods. |
| **MongoDB** | `mongo_adapter.py` | `pymongo` | `MongoClient` with `serverSelectionTimeoutMS=5000`; per-call connect/disconnect (28-49). `is_nosql=True`, `supports_snapshot=True`. | `mongodump --gzip --archive` / `mongorestore --gzip --drop` (226-275). |
| **Cassandra** | `cassandra_adapter.py` | `cassandra-driver` | `Cluster(...).connect(keyspace)`; optional `PlainTextAuthProvider`; per-call connect/disconnect (22-47). `is_nosql=True`. | **No snapshot** (base default `False`). |
| **Redis** | `redis_adapter.py` | `redis-py` | `redis.Redis(...)` client, `decode_responses=True`, `socket_timeout=5` (24-33). `is_nosql=True`. | **No snapshot** (base default `False`). |

**SQL adapters** implement full schema introspection by querying the engine
catalog: SQLite uses `PRAGMA table_info / foreign_key_list / index_list /
index_info` (sqlite_adapter.py:72-98); Postgres/MySQL/MSSQL use
`information_schema` plus engine catalogs (`pg_index`, `sys.foreign_key_columns`,
etc.); Oracle uses the `user_tables / user_cons_columns / user_constraints /
user_ind_columns` views. All of them emit the **same normalised dict shapes**
(e.g. FK = `{from_table, from_column, to_table, to_column}`) so downstream code
(ER-diagram builder, join centre, schema text) is engine-agnostic.

**NoSQL adapters** map the same interface onto non-relational concepts:
- Mongo `get_schema()` *infers* a schema by sampling up to 5 documents per
  collection and collecting `(field, python_type)` pairs (mongo_adapter.py:63-87)
  — there is no fixed schema to read.
- Mongo `execute()` expects the LLM to emit a **JSON command object** with an
  `operation` field (`find`/`aggregate`/`count`/`insertOne`/`updateMany`/
  `deleteMany`/…) and dispatches accordingly (98-201).
- Redis `get_schema()` SCANs up to 100 keys and groups them by `TYPE`
  (redis_adapter.py:52-79); `execute()` expects JSON `{command, args}` or a
  multi-step `{commands:[...]}` form (94-150).
- Cassandra takes raw CQL and reads `system_schema.tables / .columns` for schema.

**Net effect:** the same five-method contract gives the app uniform NL→SQL
across relational and NoSQL stores; pooling is present where the driver supports
it cheaply (Postgres native pool, MySQL queue pool, SQLite singleton) and absent
where per-call connections are simpler/safer (MSSQL, Oracle, the NoSQL trio).

---

## 2. SQL Safety / Validation — `core/validator.py`

The validator is the **first guardrail**: every generated query passes through
`is_safe()` before it is allowed near a database, and `classify_query()` decides
whether it is a read, write, schema-change, or system/introspection call (which
in turn drives the role check and the human-review gate).

### 2.1 What is blocked

**SQL dangerous-keyword blocklist** `SQL_DANGEROUS` (validator.py:11-22) —
substring match, case-insensitive:

```
"drop ", "truncate ", "alter ", "shutdown", "attach ", "detach ",
"pragma ", "--", "/*", "*/"
```

So **DDL destruction (DROP / TRUNCATE / ALTER)**, **SQLite file attach/detach**,
**raw PRAGMA**, server **SHUTDOWN**, and **SQL comment markers** (`--`, `/*`,
`*/`, classic injection/comment-out vectors) are all rejected.

**Statement-stacking is blocked**: any `;` in a SQL query returns `False`
(validator.py:73). This stops chaining a benign statement with a destructive one
(`SELECT 1; DROP TABLE x`).

**NoSQL dangerous-keyword blocklist** `NOSQL_DANGEROUS` (24-36):
```
dropDatabase, dropCollection, drop_collection, drop_database,
FLUSHALL, FLUSHDB, CONFIG, SHUTDOWN, DEBUG, SLAVEOF, REPLICAOF
```
This blocks Mongo collection/db drops and Redis destructive/admin commands
(`FLUSHALL`/`FLUSHDB`/`CONFIG`/`SLAVEOF`/etc.). For MongoDB the query must also
parse as JSON, and any `operation` containing `"drop"` is rejected
(validator.py:55-63); invalid JSON is treated as unsafe (62-63).

### 2.2 Read vs write classification — `classify_query()`

Returns one of `READ`, `WRITE`, `SCHEMA`, `SYSTEM`, `UNKNOWN`
(validator.py:108-182).

- **MongoDB** (117-128): JSON `operation` → `find/aggregate/count` = READ;
  `insert*/update*/delete*` = WRITE; else UNKNOWN.
- **Redis** (131-158): JSON `command` checked against an explicit `READ_CMDS`
  set (GET, MGET, HGETALL, LRANGE, KEYS, SCAN, TTL, DBSIZE, INFO, …) and
  `WRITE_CMDS` set (SET, HSET, LPUSH, SADD, DEL, EXPIRE, INCR, …). A multi-step
  `commands` batch is classified WRITE if *any* step is a write (146-150).
- **SQL family** (160-182):
  - **SYSTEM** first: prefixes like `show tables`, `show create table`,
    `describe `, `desc `, `explain `, `pragma `, `\d`, `list tables`, … (162-169)
    OR presence of metadata identifiers `sqlite_master`, `information_schema`,
    `pg_catalog`, `sys.tables`, `db.getCollectionNames`, `db.listCollections`
    (172-174).
  - `select` → **READ** (176).
  - `insert` / `update` / `delete` → **WRITE** (178).
  - `create` / `alter` / `drop` → **SCHEMA** (180-181).
  - otherwise **UNKNOWN** (182).

`is_write()` (188-189) is a thin helper = `classify_query(...) == "WRITE"`.
`classify_sql()` (195-197) is a legacy alias defaulting to the SQLite dialect.

### 2.3 The validation gate as pseudocode

```text
function is_safe(query, dialect = "sqlite"):
    q       = trim(query)
    q_lower = lowercase(q)

    # ---- NoSQL branch (MongoDB / Redis) ----
    if dialect in {mongodb, redis}:
        for kw in NOSQL_DANGEROUS:                 # dropDatabase, FLUSHALL, CONFIG, ...
            if kw.lower() in q_lower: return UNSAFE
        if dialect == mongodb:
            try: cmd = json_parse(q)
            except: return UNSAFE                  # invalid JSON = unsafe
            if "drop" in lower(cmd.operation): return UNSAFE
        return SAFE

    # ---- SQL branch ----
    for kw in SQL_DANGEROUS:                        # drop , truncate , alter , --, /*, ...
        if kw in q_lower: return UNSAFE
    if ";" in q: return UNSAFE                       # no statement stacking

    if q_lower starts_with "select":          return SAFE
    if q_lower starts_with (insert|update|delete): return SAFE
    if classify_query(q, dialect) == SYSTEM:  return SAFE   # introspection allowed

    # plain-text fallback: harmless AI text response with no SQL danger chars
    DANGER_CHARS = (";", "--", "/*", "*/", "xp_", "drop", "truncate", "alter")
    if none of DANGER_CHARS in q_lower:       return SAFE

    if dialect == cassandra and q_lower starts_with (select|insert|update|delete):
        return SAFE

    return UNSAFE
```

> **Note (accuracy / limitation worth reporting):** the safety gate is a
> keyword/prefix heuristic, not a SQL parser. The "plain-text fallback"
> (validator.py:88-95) is deliberately permissive so that conversational AI
> replies are not shown as "Execution Failed"; this is a documented trade-off in
> the code comments. Also note `is_safe` returns at the SQL `select/insert/...`
> checks *before* reaching the Cassandra-specific block (97-101), so that block
> is effectively only reached for Cassandra queries that did not already match —
> a minor dead-branch detail. Defence-in-depth is provided by the role
> permissions and the human review step (Section 5), not by the validator alone.

---

## 3. Connection Manager — `core/connection_manager.py`

Responsible for persisting, encrypting, listing, testing, and instantiating
database connections.

### 3.1 Encrypted credential storage (Fernet)

Yes — it uses the **`cryptography` library's `Fernet`** symmetric cipher
(connection_manager.py:10).

- **Key management** `_get_key()` (24-33): the key lives in `db/.secret_key`. If
  the file exists it is read; otherwise a fresh key is generated with
  `Fernet.generate_key()` and written to disk. (So the encryption is only as
  strong as the on-disk key file — worth noting in a security discussion.)
- `_encrypt(text)` (36-40) → `Fernet(key).encrypt(...)`, returns a string token;
  empty input returns `""`.
- `_decrypt(token)` (43-47) → reverse.

Only the **password** field is encrypted; host/port/username/db remain
plaintext. On save, `add_connection()` copies the config and replaces
`config["password"]` with its ciphertext before persisting (104-106).

### 3.2 JSON persistence

- Connections file: `CONN_FILE = "db/connections.json"` (17).
- Key file: `KEY_FILE = "db/.secret_key"` (18).
- `_load_connections()` (53-57) → returns `{}` if the file is missing.
- `_save_connections(data)` (60-63) → `json.dump(..., indent=2)`, creating the
  `db/` directory if needed.

Stored shape per connection:
`{ "<name>": { "db_type": "...", "config": { ...encrypted password... } } }`.

### 3.3 Public API & lifecycle

- `list_connections()` (69-87): returns all connections for display with the
  password **masked** to `"••••••••"` (never returns plaintext or ciphertext to
  the UI).
- `add_connection(name, db_type, config)` (90-113): validates `db_type ∈
  DB_TYPES` and a non-empty name; encrypts the password; saves.
- `delete_connection(name)` (116-122).
- `get_adapter_for_connection(name)` (125-146): loads the record, **decrypts the
  password** (best-effort — silently keeps the stored value if decryption fails,
  to tolerate plaintext/legacy entries, 139-143), then `get_adapter(db_type)`
  (the factory from §1.3) and returns an *instantiated* adapter with the
  decrypted config. This is the bridge from stored credentials → live adapter.
- `test_connection(name)` (149-159) and `test_new_connection(db_type, config)`
  (162-173): build an adapter and call `adapter.test_connection()`, returning a
  `{success, message}` dict. `test_new_connection` lets the UI verify a
  connection *before* saving it.
- `ensure_default_sqlite()` (176-187): on startup, guarantees a `"Default
  SQLite"` connection pointing at `db/main.db` exists.

---

## 4. Snapshot / Rollback Engine — `core/snapshot.py`

A cross-database backup registry that takes a backup **before** any risky write
and supports restore/undo.

### 4.1 Storage layout

- `SNAP_DIR = "db/snapshots"` (12), created at import (16).
- Registry: `REGISTRY_FILE = "db/snapshots.json"` (13) — a JSON **list** of
  snapshot metadata dicts.
- Retention: `MAX_SNAPS_PER_DB = 5` (14) per connection.

### 4.2 Taking a snapshot — `take_snapshot(adapter, connection_name)` (69-112)

1. Guard: if `adapter` is missing or `adapter.supports_snapshot` is False →
   return `None` (74). (So Oracle/Cassandra/Redis silently no-op.)
2. **Retention**: count existing snapshots for this connection; if `>= 5`, delete
   the **oldest** before adding a new one (80-86).
3. Build a filename `"{connection}_{YYYYMMDD_HHMMSS}_{uuid8}.{ext}"`, where the
   extension is `db` for SQLite, `gz` for MongoDB, else `dump`; the name is
   sanitised (spaces→`_`, `/`→`-`) (88-97).
4. Delegate the actual backup to the adapter: `adapter.take_snapshot(filepath)`
   (99) — i.e. file copy (SQLite), `pg_dump` (Postgres), `mysqldump` (MySQL),
   `mongodump` (Mongo), `sqlpackage` (MSSQL).
5. On success append a metadata record `{id, connection_name, db_type,
   timestamp(ISO), formatted_time, file_path}` to the registry and save
   (101-111).

### 4.3 Restore / undo flow

- `restore_snapshot(snap_id, adapter)` (115-126): look up the record (raises if
  not found), re-check `supports_snapshot`, then `adapter.restore_snapshot(
  snap["file_path"])` — file copy back / `pg_restore` / `mysql` / `mongorestore
  --drop` / `sqlpackage Publish`.
- `undo(steps=1, adapter, connection_name="Default SQLite")` (129-143):
  backward-compatible helper. Lists snapshots newest-first, picks the
  `steps`-th most recent (`snaps[steps-1]`), and restores it; raises if no
  snapshots or `steps` out of range.
- Helpers: `get_snapshot` (34-39), `list_snapshots(connection_name)` filtered +
  sorted newest-first (42-47), `delete_snapshot` removes file + registry entry
  (50-66), `has_snapshots` (146-148).

---

## 5. Human-in-the-loop write review & dry-run — `app.py`

The validator (§2) and the role model are combined in the main `/` route, and a
dedicated review page + execute/dry-run endpoints implement the human gate.

### 5.1 Role model (defence layer)

`app.py:93-100`:
```
ROLE_VIEWER = {"READ", "SYSTEM"}
ROLE_EDITOR = {"READ", "WRITE", "SYSTEM"}
ROLE_ADMIN  = {"READ", "WRITE", "SCHEMA", "SYSTEM"}
```
`is_allowed(role, task)` (111-112) is a simple set-membership test. So only
ADMIN may run SCHEMA (CREATE/ALTER/DROP) tasks, only EDITOR/ADMIN may run WRITE,
and VIEWER is read-only.

### 5.2 Flow in the main `/` POST handler

1. The LLM generates `query, explanation` from the NL command + live schema
   (`app.py:565`).
2. `task = classify_query(query, dialect)` and `safe_check = is_safe(query,
   dialect)` (575-576).
3. A guard treats a *safe* `UNKNOWN` as `READ` for ADMIN/EDITOR so harmless
   introspection isn't blocked (580-581).
4. Role check: if `not is_allowed(role, effective_task)` → history entry
   `BLOCKED (ROLE)` and an error page (583-593).
5. **READ / SYSTEM / safe-UNKNOWN** → re-checks `is_safe` (597), then executes
   directly with pagination (`paginate_sql`, `safe_count`) for SQL or directly
   for NoSQL (615-628).
6. **WRITE / SCHEMA** → does **NOT** execute. It records a `PENDING REVIEW`
   history entry, stashes the SQL/task/explanation in the session, and renders
   `review.html` (737-751). This is the human-in-the-loop gate — the user sees
   the exact generated SQL and must confirm.

### 5.3 `/dry-run` (POST) — `app.py:843-856`

Takes `sql` (from JSON/form/session), gets the active adapter, and calls
`adapter.dry_run(query)`, returning the JSON result. The adapter executes the
statement **inside a transaction and rolls it back**, reporting
`affected_rows` without persisting:
- SQLite (`sqlite_adapter.py:269-293`): `BEGIN` → execute → read
  `conn.total_changes` → `rollback()`.
- Postgres (`postgres_adapter.py:201-223`): `autocommit=False` → execute →
  `cur.rowcount` → `rollback()`.
- MySQL (`mysql_adapter.py:195-217`): `conn.begin()` → execute →
  `cur.rowcount` → `rollback()`.

So a user can preview "this UPDATE would affect N rows" before committing.

### 5.4 `/execute` (POST) — `app.py:910-940`

The confirmation endpoint reached from the review page:
1. Reads `sql` from the form (allowing the human to **edit** the SQL before
   running) or session; reads `task` from session.
2. Re-validates: `if not query or not is_allowed(role, task) or not
   is_safe(query, dialect)` → "Permission denied or unsafe query" and redirect
   (920-922). (The safety + role checks run a second time at execution time.)
3. **If task is WRITE or SCHEMA → `take_snapshot(adapter, active_db)` is called
   first** (924-925) — an automatic backup immediately before the mutation,
   enabling later undo.
4. For DELETEs it calls `adapter.preview_delete(query)` (928-929) to compute the
   affected-row count, then `adapter.execute(query)` (931).
5. Clears the staged session keys (936-938).

There is also `/refine` (859-907) — the user can give natural-language feedback
to regenerate/improve the staged SQL before executing — and
`/api/command-center/execute-raw` (2327-2349) which takes a `take_snapshot`
flag and snapshots before running raw SQL.

**Summary of the write pipeline:**
`NL prompt → LLM SQL → classify_query → is_safe → role check → (READ: run) /
(WRITE|SCHEMA: review.html) → human confirms/edits → /dry-run preview →
/execute (re-validate → snapshot → run) → undo if needed`.

---

## 6. Sample SQLite databases (for ER diagram & Dataset Description)

Three SQLite files live in `db/`. Extraction performed with the `sqlite3` CLI on
2026-05-25.

### 6.1 `main.db` — the default working DB

`main.db` is a **clone of the Chinook schema** (identical 11 tables and FKs,
see §6.2) plus one extra throwaway table `DummyTableTest(id INTEGER PRIMARY
KEY)`. It is the `"Default SQLite"` connection target
(`connection_manager.py:185`). For the ER diagram it can be treated as identical
to Chinook (ignore `DummyTableTest`).

### 6.2 `chinook.db` — digital media store (11 tables)

A music-store sample DB. Row counts:

| Table | Rows | PK | Notes |
|---|---:|---|---|
| Artist | 275 | ArtistId | |
| Album | 347 | AlbumId | belongs to an Artist |
| Track | 3,503 | TrackId | song; links Album, Genre, MediaType |
| Genre | 25 | GenreId | |
| MediaType | 5 | MediaTypeId | |
| Playlist | 18 | PlaylistId | |
| PlaylistTrack | 8,715 | (PlaylistId, TrackId) | junction (M:N) |
| Employee | 8 | EmployeeId | self-referencing (ReportsTo) |
| Customer | 59 | CustomerId | assigned a support rep |
| Invoice | 412 | InvoiceId | a customer's order |
| InvoiceLine | 2,240 | InvoiceLineId | line item of an invoice |

**Foreign keys (FROM.col → TO.col), per the authoritative DDL:**

- `Album.ArtistId → Artist.ArtistId`
- `Track.AlbumId → Album.AlbumId`
- `Track.GenreId → Genre.GenreId`
- `Track.MediaTypeId → MediaType.MediaTypeId`
- `PlaylistTrack.PlaylistId → Playlist.PlaylistId`
- `PlaylistTrack.TrackId → Track.TrackId`
- `Customer.SupportRepId → Employee.EmployeeId`
- `Employee.ReportsTo → Employee.EmployeeId` (self-reference)
- `Invoice.CustomerId → Customer.CustomerId`
- `InvoiceLine.InvoiceId → Invoice.InvoiceId`
- `InvoiceLine.TrackId → Track.TrackId`

(11 FK relationships. Note: SQLite `PRAGMA foreign_key_list` reports the
`from`/`to` columns in a swapped order for the self-reference and the
`Customer→Employee` link; the directions above follow the `CREATE TABLE` DDL,
which is correct.)

### 6.3 `northwind.db` — trading company (LARGEST sample DB)

13 **base tables** + 17 **views** (the report/`Qry` entries from `.tables` such
as "Sales by Category", "Quarterly Orders", "Order Subtotals" are SQL *views*,
not tables — exclude them from the ER diagram). This is by far the largest DB:
`Order Details` alone has **609,283 rows** and `Orders` **16,282**.

Base-table row counts:

| Table | Rows | PK |
|---|---:|---|
| Categories | 8 | CategoryID (AUTOINCREMENT) |
| Suppliers | 29 | SupplierID (AUTOINCREMENT) |
| Products | 77 | ProductID (AUTOINCREMENT) |
| Customers | 94 | CustomerID (TEXT) |
| CustomerDemographics | 0 | CustomerTypeID (TEXT) |
| CustomerCustomerDemo | 0 | (CustomerID, CustomerTypeID) |
| Employees | 9 | EmployeeID (AUTOINCREMENT) |
| Regions | 4 | RegionID |
| Territories | 53 | TerritoryID (TEXT) |
| EmployeeTerritories | 49 | (EmployeeID, TerritoryID) |
| Shippers | 4 | ShipperID (AUTOINCREMENT) |
| Orders | 16,282 | OrderID (AUTOINCREMENT) |
| Order Details | 609,283 | (OrderID, ProductID) |

Key columns / constraints of note: `Order Details` carries CHECK constraints
(`Discount BETWEEN 0 AND 1`, `Quantity > 0`, `UnitPrice >= 0`); `Products` has
CHECKs on price/stock ≥ 0; junction tables (`CustomerCustomerDemo`,
`EmployeeTerritories`, `Order Details`) use composite PKs.

**Full foreign-key relationship list (FROM.col → TO.col), per the DDL —
this is the largest DB's relationship set for the ER diagram:**

- `Products.SupplierID → Suppliers.SupplierID`
- `Products.CategoryID → Categories.CategoryID`
- `Orders.CustomerID → Customers.CustomerID`
- `Orders.EmployeeID → Employees.EmployeeID`
- `Orders.ShipVia → Shippers.ShipperID`
- `Order Details.OrderID → Orders.OrderID`
- `Order Details.ProductID → Products.ProductID`
- `Employees.ReportsTo → Employees.EmployeeID` (self-reference, org hierarchy)
- `Territories.RegionID → Regions.RegionID`
- `EmployeeTerritories.EmployeeID → Employees.EmployeeID`
- `EmployeeTerritories.TerritoryID → Territories.TerritoryID`
- `CustomerCustomerDemo.CustomerID → Customers.CustomerID`
- `CustomerCustomerDemo.CustomerTypeID → CustomerDemographics.CustomerTypeID`

(13 FK relationships across 13 base tables. As with Chinook, `PRAGMA
foreign_key_list` reports `Orders.ShipVia`/`Employees.ReportsTo` column pairs
in swapped order; directions above follow the authoritative `CREATE TABLE`
statements.)

**ER reading of Northwind:** Suppliers 1—N Products N—1 Categories; Customers
1—N Orders N—1 Employees (and Orders N—1 Shippers); Orders 1—N "Order Details"
N—1 Products (the central fact/junction table); Employees self-hierarchy via
ReportsTo; Regions 1—N Territories, with Employees M—N Territories via
EmployeeTerritories; Customers M—N CustomerDemographics via
CustomerCustomerDemo.
