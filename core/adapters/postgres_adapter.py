"""
PostgreSQL Adapter
Uses psycopg2 for PostgreSQL connections.
"""

from core.adapters.base import DatabaseAdapter


class PostgresAdapter(DatabaseAdapter):

    @property
    def dialect(self):
        return "postgresql"

    @property
    def supports_snapshot(self) -> bool:
        return True

    # --------------------------------------------------
    # Connection
    # --------------------------------------------------
    def __init__(self, config: dict):
        super().__init__(config)
        self._pool = None

    def connect(self):
        from psycopg2 import pool
        params = {
            "host": self.config.get("host", "localhost"),
            "port": int(self.config.get("port", 5432)),
            "user": self.config.get("username", "postgres"),
            "password": self.config.get("password", ""),
            "dbname": self.config.get("database", "postgres"),
        }
        # Create a thread-safe pool
        self._pool = pool.ThreadedConnectionPool(1, 10, **params)

    def disconnect(self):
        if self._pool:
            self._pool.closeall()
            self._pool = None

    def get_connection(self):
        if not self._pool:
            self.connect()
        return self._pool.getconn()

    def release_connection(self, conn):
        if self._pool:
            self._pool.putconn(conn)

    def test_connection(self) -> bool:
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            self.release_connection(conn)
            return True
        except Exception:
            return False

    # --------------------------------------------------
    # Schema
    # --------------------------------------------------
    def get_schema(self) -> str:
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """)
                tables = [r[0] for r in cur.fetchall()]

                schema = ""
                for table_name in tables:
                    schema += f"\nTABLE {table_name}:\n"

                    # Columns with PK markers, NOT NULL, defaults
                    cur.execute("""
                        SELECT c.column_name, c.data_type, c.is_nullable,
                               c.column_default,
                               CASE WHEN pk.column_name IS NOT NULL THEN TRUE ELSE FALSE END
                        FROM information_schema.columns c
                        LEFT JOIN (
                            SELECT kcu.column_name
                            FROM information_schema.table_constraints tc
                            JOIN information_schema.key_column_usage kcu
                                ON tc.constraint_name = kcu.constraint_name
                                AND tc.table_schema = kcu.table_schema
                            WHERE tc.constraint_type = 'PRIMARY KEY'
                              AND tc.table_schema = 'public' AND tc.table_name = %s
                        ) pk ON pk.column_name = c.column_name
                        WHERE c.table_schema = 'public' AND c.table_name = %s
                        ORDER BY c.ordinal_position
                    """, (table_name, table_name))
                    col_info = cur.fetchall()
                    col_names = []
                    for col_name, dtype, nullable, default, is_pk in col_info:
                        col_names.append(col_name)
                        notnull = " NOT NULL" if nullable == "NO" else ""
                        default_str = f" DEFAULT {default}" if default else ""
                        pk_marker = " [PRIMARY KEY]" if is_pk else ""
                        schema += f"  - {col_name} ({dtype}{notnull}{default_str}{pk_marker})\n"

                    # Foreign keys
                    cur.execute("""
                        SELECT kcu.column_name, ccu.table_name, ccu.column_name
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage kcu
                            ON tc.constraint_name = kcu.constraint_name
                            AND tc.table_schema = kcu.table_schema
                        JOIN information_schema.constraint_column_usage ccu
                            ON ccu.constraint_name = tc.constraint_name
                            AND ccu.table_schema = tc.table_schema
                        WHERE tc.constraint_type = 'FOREIGN KEY'
                          AND tc.table_schema = 'public' AND tc.table_name = %s
                    """, (table_name,))
                    fks = cur.fetchall()
                    if fks:
                        schema += "  FOREIGN KEYS:\n"
                        for fk_col, ref_table, ref_col in fks:
                            schema += f"    - {fk_col} -> {ref_table}.{ref_col}\n"

                    # Indexes
                    cur.execute("""
                        SELECT i.relname, ix.indisunique,
                               array_agg(a.attname ORDER BY k.n)
                        FROM pg_index ix
                        JOIN pg_class t ON t.oid = ix.indrelid
                        JOIN pg_class i ON i.oid = ix.indexrelid
                        JOIN pg_namespace ns ON ns.oid = t.relnamespace
                        JOIN LATERAL unnest(ix.indkey) WITH ORDINALITY AS k(attnum, n) ON TRUE
                        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = k.attnum
                        WHERE ns.nspname = 'public' AND t.relname = %s
                        GROUP BY i.relname, ix.indisunique
                    """, (table_name,))
                    indexes = cur.fetchall()
                    if indexes:
                        schema += "  INDEXES:\n"
                        for idx_name, is_unique, idx_cols in indexes:
                            unique = "UNIQUE " if is_unique else ""
                            schema += f"    - {unique}{idx_name} ({', '.join(idx_cols)})\n"

                    # Sample data (3 rows)
                    try:
                        cur.execute(f'SELECT * FROM "{table_name}" LIMIT 3')
                        sample_rows = cur.fetchall()
                        if sample_rows and col_names:
                            schema += f"  SAMPLE DATA ({len(sample_rows)} rows):\n"
                            for sr in sample_rows:
                                pairs = []
                                for i, val in enumerate(sr):
                                    if i >= len(col_names):
                                        break
                                    if isinstance(val, (bytes, memoryview)):
                                        continue
                                    pairs.append(f"{col_names[i]}={str(val)[:60]}")
                                schema += f"    {', '.join(pairs)}\n"
                    except Exception:
                        pass

                return schema
        finally:
            self.release_connection(conn)

    def list_tables(self) -> list:
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """)
                return [row[0] for row in cur.fetchall()]
        finally:
            self.release_connection(conn)

    # --------------------------------------------------
    # Execution
    # --------------------------------------------------
    def execute(self, query: str) -> tuple:
        conn = self.get_connection()
        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                cur.execute(query)
                if cur.description:
                    columns = [desc[0] for desc in cur.description]
                    rows = [list(r) for r in cur.fetchall()]
                else:
                    columns = []
                    rows = []
                return columns, rows
        finally:
            self.release_connection(conn)
    def dry_run(self, query: str) -> dict:
        conn = self.get_connection()
        try:
            conn.autocommit = False
            with conn.cursor() as cur:
                cur.execute(query)
                affected = cur.rowcount
                conn.rollback()
                return {
                    "affected_rows": affected,
                    "status": "Success (Rolled back)",
                    "success": True
                }
        except Exception as e:
            try: conn.rollback()
            except: pass
            return {
                "affected_rows": 0,
                "status": f"Error: {str(e)}",
                "success": False
            }
        finally:
            self.release_connection(conn)

    # --------------------------------------------------
    # Introspection
    # --------------------------------------------------
    def get_foreign_keys(self) -> list:
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        tc.table_name   AS from_table,
                        kcu.column_name AS from_column,
                        ccu.table_name  AS to_table,
                        ccu.column_name AS to_column
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                        ON tc.constraint_name = kcu.constraint_name
                        AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage ccu
                        ON ccu.constraint_name = tc.constraint_name
                        AND ccu.table_schema = tc.table_schema
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                      AND tc.table_schema = 'public'
                """)
                return [
                    {"from_table": r[0], "from_column": r[1],
                     "to_table": r[2], "to_column": r[3]}
                    for r in cur.fetchall()
                ]
        finally:
            self.release_connection(conn)

    def get_indexes(self) -> list:
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        t.relname AS table_name,
                        i.relname AS index_name,
                        ix.indisunique AS is_unique,
                        array_agg(a.attname ORDER BY k.n) AS columns
                    FROM pg_index ix
                    JOIN pg_class t ON t.oid = ix.indrelid
                    JOIN pg_class i ON i.oid = ix.indexrelid
                    JOIN pg_namespace ns ON ns.oid = t.relnamespace
                    JOIN LATERAL unnest(ix.indkey) WITH ORDINALITY AS k(attnum, n) ON TRUE
                    JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = k.attnum
                    WHERE ns.nspname = 'public'
                    GROUP BY t.relname, i.relname, ix.indisunique
                    ORDER BY t.relname, i.relname
                """)
                return [
                    {"table": r[0], "index_name": r[1],
                     "unique": bool(r[2]), "columns": list(r[3])}
                    for r in cur.fetchall()
                ]
        finally:
            self.release_connection(conn)

    def describe_table(self, table_name: str) -> dict:
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                # Columns
                cur.execute("""
                    SELECT c.column_name, c.data_type, c.is_nullable,
                           c.column_default,
                           CASE WHEN pk.column_name IS NOT NULL THEN TRUE ELSE FALSE END AS is_pk
                    FROM information_schema.columns c
                    LEFT JOIN (
                        SELECT kcu.column_name
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage kcu
                            ON tc.constraint_name = kcu.constraint_name
                            AND tc.table_schema = kcu.table_schema
                        WHERE tc.constraint_type = 'PRIMARY KEY'
                          AND tc.table_schema = 'public'
                          AND tc.table_name = %s
                    ) pk ON pk.column_name = c.column_name
                    WHERE c.table_schema = 'public' AND c.table_name = %s
                    ORDER BY c.ordinal_position
                """, (table_name, table_name))
                columns = [
                    {"name": r[0], "type": r[1],
                     "not_null": r[2] == "NO",
                     "default": r[3], "primary_key": bool(r[4])}
                    for r in cur.fetchall()
                ]

                # Foreign keys
                cur.execute("""
                    SELECT kcu.column_name, ccu.table_name, ccu.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                        ON tc.constraint_name = kcu.constraint_name
                        AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage ccu
                        ON ccu.constraint_name = tc.constraint_name
                        AND ccu.table_schema = tc.table_schema
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                      AND tc.table_schema = 'public'
                      AND tc.table_name = %s
                """, (table_name,))
                fks = [{"from": r[0], "to_table": r[1], "to_column": r[2]}
                       for r in cur.fetchall()]

                # Indexes
                cur.execute("""
                    SELECT i.relname, ix.indisunique,
                           array_agg(a.attname ORDER BY k.n)
                    FROM pg_index ix
                    JOIN pg_class t ON t.oid = ix.indrelid
                    JOIN pg_class i ON i.oid = ix.indexrelid
                    JOIN pg_namespace ns ON ns.oid = t.relnamespace
                    JOIN LATERAL unnest(ix.indkey) WITH ORDINALITY AS k(attnum, n) ON TRUE
                    JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = k.attnum
                    WHERE ns.nspname = 'public' AND t.relname = %s
                    GROUP BY i.relname, ix.indisunique
                """, (table_name,))
                indexes = [{"name": r[0], "unique": bool(r[1]), "columns": list(r[2])}
                           for r in cur.fetchall()]

                # Row count
                cur.execute(f'SELECT COUNT(*) FROM "{table_name}"')
                row_count = cur.fetchone()[0]

                return {"table": table_name, "columns": columns,
                        "foreign_keys": fks, "indexes": indexes,
                        "row_count": row_count}
        finally:
            self.release_connection(conn)

    def get_constraints(self) -> list:
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                constraints = []
                cur.execute("""
                    SELECT tc.table_name, tc.constraint_type, tc.constraint_name,
                           string_agg(kcu.column_name, ', ' ORDER BY kcu.ordinal_position)
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                        ON tc.constraint_name = kcu.constraint_name
                        AND tc.table_schema = kcu.table_schema
                    WHERE tc.table_schema = 'public'
                      AND tc.constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE')
                    GROUP BY tc.table_name, tc.constraint_type, tc.constraint_name
                    ORDER BY tc.table_name, tc.constraint_type
                """)
                for r in cur.fetchall():
                    constraints.append({"table": r[0], "type": r[1], "details": f"{r[2]} ({r[3]})"})

                # NOT NULL constraints
                cur.execute("""
                    SELECT table_name, column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND is_nullable = 'NO'
                    ORDER BY table_name, ordinal_position
                """)
                for r in cur.fetchall():
                    constraints.append({"table": r[0], "type": "NOT NULL", "details": r[1]})

                return constraints
        finally:
            self.release_connection(conn)

    def get_create_table(self, table_name: str) -> str:
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                # Build DDL from information_schema
                cur.execute("""
                    SELECT column_name, data_type, character_maximum_length,
                           is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                    ORDER BY ordinal_position
                """, (table_name,))
                cols = cur.fetchall()
                if not cols:
                    return f"-- Table '{table_name}' not found"

                lines = []
                for col_name, dtype, max_len, nullable, default in cols:
                    col_def = f"  {col_name} {dtype}"
                    if max_len:
                        col_def += f"({max_len})"
                    if nullable == "NO":
                        col_def += " NOT NULL"
                    if default:
                        col_def += f" DEFAULT {default}"
                    lines.append(col_def)

                # Primary key
                cur.execute("""
                    SELECT string_agg(kcu.column_name, ', ' ORDER BY kcu.ordinal_position)
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                        ON tc.constraint_name = kcu.constraint_name
                    WHERE tc.table_schema = 'public'
                      AND tc.table_name = %s
                      AND tc.constraint_type = 'PRIMARY KEY'
                """, (table_name,))
                pk_row = cur.fetchone()
                if pk_row and pk_row[0]:
                    lines.append(f"  PRIMARY KEY ({pk_row[0]})")

                return f'CREATE TABLE "{table_name}" (\n' + ",\n".join(lines) + "\n);"
        finally:
            self.release_connection(conn)

    # --------------------------------------------------
    # Safety
    # --------------------------------------------------
    def preview_delete(self, query: str):
        q = query.strip().rstrip(";")
        if not q.lower().startswith("delete"):
            return None

        count_sql = q.lower().replace("delete", "select count(*)", 1)
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(count_sql)
                row = cur.fetchone()
                return row[0] if row else 0
        finally:
            self.release_connection(conn)

    # --------------------------------------------------
    # Snapshots
    # --------------------------------------------------
    def take_snapshot(self, filepath: str) -> bool:
        import subprocess
        import os
        try:
            cmd = [
                "pg_dump",
                "-h", self.config.get("host", "localhost"),
                "-p", str(self.config.get("port", 5432)),
                "-U", self.config.get("username", "postgres"),
                "-d", self.config.get("database", "postgres"),
                "-F", "c",  # custom format
                "-f", filepath
            ]
            env = os.environ.copy()
            if self.config.get("password"):
                env["PGPASSWORD"] = self.config["password"]

            subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return True
        except Exception:
            return False

    def restore_snapshot(self, filepath: str) -> bool:
        import subprocess
        import os
        try:
            cmd = [
                "pg_restore",
                "-h", self.config.get("host", "localhost"),
                "-p", str(self.config.get("port", 5432)),
                "-U", self.config.get("username", "postgres"),
                "-d", self.config.get("database", "postgres"),
                "-1",  # single transaction
                "-c",  # clean (drop) before recreating
                filepath
            ]
            env = os.environ.copy()
            if self.config.get("password"):
                env["PGPASSWORD"] = self.config["password"]

            subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return True
        except Exception:
            return False
