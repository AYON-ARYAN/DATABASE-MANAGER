"""
MySQL Adapter
Uses pymysql for MySQL / MariaDB connections.
"""

from core.adapters.base import DatabaseAdapter


class MySQLAdapter(DatabaseAdapter):

    @property
    def dialect(self):
        return "mysql"

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
        import pymysql
        from queue import Queue
        self._pool = Queue(maxsize=10)
        
        # Pre-fill with one connection
        self._pool.put(self._create_new_conn())

    def _create_new_conn(self):
        import pymysql
        return pymysql.connect(
            host=self.config.get("host", "localhost"),
            port=int(self.config.get("port", 3306)),
            user=self.config.get("username", "root"),
            password=self.config.get("password", ""),
            database=self.config.get("database", ""),
            charset="utf8mb4",
            cursorclass=pymysql.cursors.Cursor,
            autocommit=True
        )

    def disconnect(self):
        if self._pool:
            while not self._pool.empty():
                conn = self._pool.get()
                conn.close()
            self._pool = None

    def get_connection(self):
        if not self._pool:
            self.connect()
        
        if self._pool.empty():
            return self._create_new_conn()
        return self._pool.get()

    def release_connection(self, conn):
        if self._pool and not self._pool.full():
            self._pool.put(conn)
        else:
            conn.close()

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
                db = self.config.get("database", "")
                cur.execute("""
                    SELECT TABLE_NAME
                    FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'
                """, (db,))
                tables = [r[0] for r in cur.fetchall()]

                schema = ""
                for table_name in tables:
                    schema += f"\nTABLE {table_name}:\n"

                    # Columns with PK, NOT NULL, defaults
                    cur.execute("""
                        SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE,
                               COLUMN_DEFAULT, COLUMN_KEY
                        FROM INFORMATION_SCHEMA.COLUMNS
                        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                        ORDER BY ORDINAL_POSITION
                    """, (db, table_name))
                    col_info = cur.fetchall()
                    col_names = []
                    for col_name, col_type, nullable, default, col_key in col_info:
                        col_names.append(col_name)
                        notnull = " NOT NULL" if nullable == "NO" else ""
                        default_str = f" DEFAULT {default}" if default is not None else ""
                        pk_marker = " [PRIMARY KEY]" if col_key == "PRI" else ""
                        schema += f"  - {col_name} ({col_type}{notnull}{default_str}{pk_marker})\n"

                    # Foreign keys
                    cur.execute("""
                        SELECT COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                          AND REFERENCED_TABLE_NAME IS NOT NULL
                    """, (db, table_name))
                    fks = cur.fetchall()
                    if fks:
                        schema += "  FOREIGN KEYS:\n"
                        for fk_col, ref_table, ref_col in fks:
                            schema += f"    - {fk_col} -> {ref_table}.{ref_col}\n"

                    # Indexes
                    cur.execute("""
                        SELECT INDEX_NAME, NON_UNIQUE,
                               GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX)
                        FROM INFORMATION_SCHEMA.STATISTICS
                        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                        GROUP BY INDEX_NAME, NON_UNIQUE
                    """, (db, table_name))
                    indexes = cur.fetchall()
                    if indexes:
                        schema += "  INDEXES:\n"
                        for idx_name, non_unique, idx_cols in indexes:
                            unique = "" if non_unique else "UNIQUE "
                            schema += f"    - {unique}{idx_name} ({idx_cols})\n"

                    # Sample data (3 rows)
                    try:
                        cur.execute(f"SELECT * FROM `{table_name}` LIMIT 3")
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
                db = self.config.get("database", "")
                cur.execute("""
                    SELECT TABLE_NAME
                    FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'
                """, (db,))
                return [row[0] for row in cur.fetchall()]
        finally:
            self.release_connection(conn)

    # --------------------------------------------------
    # Execution
    # --------------------------------------------------
    def execute(self, query: str) -> tuple:
        conn = self.get_connection()
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
            conn.begin()
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
                db = self.config.get("database", "")
                cur.execute("""
                    SELECT TABLE_NAME, COLUMN_NAME,
                           REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                    FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                    WHERE TABLE_SCHEMA = %s
                      AND REFERENCED_TABLE_NAME IS NOT NULL
                """, (db,))
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
                db = self.config.get("database", "")
                cur.execute("""
                    SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE,
                           GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX)
                    FROM INFORMATION_SCHEMA.STATISTICS
                    WHERE TABLE_SCHEMA = %s
                    GROUP BY TABLE_NAME, INDEX_NAME, NON_UNIQUE
                    ORDER BY TABLE_NAME, INDEX_NAME
                """, (db,))
                return [
                    {"table": r[0], "index_name": r[1],
                     "unique": not bool(r[2]),
                     "columns": r[3].split(",") if r[3] else []}
                    for r in cur.fetchall()
                ]
        finally:
            self.release_connection(conn)

    def describe_table(self, table_name: str) -> dict:
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                db = self.config.get("database", "")

                # Columns
                cur.execute("""
                    SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE,
                           COLUMN_DEFAULT, COLUMN_KEY
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                    ORDER BY ORDINAL_POSITION
                """, (db, table_name))
                columns = [
                    {"name": r[0], "type": r[1],
                     "not_null": r[2] == "NO",
                     "default": r[3], "primary_key": r[4] == "PRI"}
                    for r in cur.fetchall()
                ]

                # Foreign keys
                cur.execute("""
                    SELECT COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                    FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                      AND REFERENCED_TABLE_NAME IS NOT NULL
                """, (db, table_name))
                fks = [{"from": r[0], "to_table": r[1], "to_column": r[2]}
                       for r in cur.fetchall()]

                # Indexes
                cur.execute("""
                    SELECT INDEX_NAME, NON_UNIQUE,
                           GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX)
                    FROM INFORMATION_SCHEMA.STATISTICS
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                    GROUP BY INDEX_NAME, NON_UNIQUE
                """, (db, table_name))
                indexes = [
                    {"name": r[0], "unique": not bool(r[1]),
                     "columns": r[2].split(",") if r[2] else []}
                    for r in cur.fetchall()
                ]

                # Row count
                cur.execute(f"SELECT COUNT(*) FROM `{table_name}`")
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
                db = self.config.get("database", "")
                constraints = []

                # PK, FK, UNIQUE
                cur.execute("""
                    SELECT tc.TABLE_NAME, tc.CONSTRAINT_TYPE, tc.CONSTRAINT_NAME,
                           GROUP_CONCAT(kcu.COLUMN_NAME ORDER BY kcu.ORDINAL_POSITION)
                    FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                    JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                        ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
                        AND tc.TABLE_SCHEMA = kcu.TABLE_SCHEMA
                        AND tc.TABLE_NAME = kcu.TABLE_NAME
                    WHERE tc.TABLE_SCHEMA = %s
                      AND tc.CONSTRAINT_TYPE IN ('PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE')
                    GROUP BY tc.TABLE_NAME, tc.CONSTRAINT_TYPE, tc.CONSTRAINT_NAME
                    ORDER BY tc.TABLE_NAME
                """, (db,))
                for r in cur.fetchall():
                    constraints.append({"table": r[0], "type": r[1], "details": f"{r[2]} ({r[3]})"})

                # NOT NULL
                cur.execute("""
                    SELECT TABLE_NAME, COLUMN_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = %s AND IS_NULLABLE = 'NO'
                    ORDER BY TABLE_NAME, ORDINAL_POSITION
                """, (db,))
                for r in cur.fetchall():
                    constraints.append({"table": r[0], "type": "NOT NULL", "details": r[1]})

                return constraints
        finally:
            self.release_connection(conn)

    def get_create_table(self, table_name: str) -> str:
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(f"SHOW CREATE TABLE `{table_name}`")
                row = cur.fetchone()
                return row[1] if row else f"-- Table '{table_name}' not found"
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
        try:
            cmd = [
                "mysqldump",
                "-h", self.config.get("host", "localhost"),
                "-P", str(self.config.get("port", 3306)),
                "-u", self.config.get("username", "root")
            ]
            password = self.config.get("password", "")
            if password:
                cmd.append(f"-p{password}")
            cmd.append(self.config.get("database", ""))

            with open(filepath, "w") as f:
                subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, check=True)
            return True
        except Exception:
            return False

    def restore_snapshot(self, filepath: str) -> bool:
        import subprocess
        try:
            cmd = [
                "mysql",
                "-h", self.config.get("host", "localhost"),
                "-P", str(self.config.get("port", 3306)),
                "-u", self.config.get("username", "root")
            ]
            password = self.config.get("password", "")
            if password:
                cmd.append(f"-p{password}")
            cmd.append(self.config.get("database", ""))

            with open(filepath, "r") as f:
                subprocess.run(cmd, stdin=f, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return True
        except Exception:
            return False
