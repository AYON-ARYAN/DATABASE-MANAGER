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
        self.connect()
        cur = self._conn.cursor()

        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        tables = cur.fetchall()

        schema = ""
        for (table_name,) in tables:
            schema += f"\nTABLE {table_name}:\n"
            cur.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                ORDER BY ordinal_position
            """, (table_name,))
            for col_name, data_type in cur.fetchall():
                schema += f"  - {col_name} ({data_type})\n"

        cur.close()
        self.disconnect()
        return schema

    def list_tables(self) -> list:
        self.connect()
        cur = self._conn.cursor()
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        tables = [row[0] for row in cur.fetchall()]
        cur.close()
        self.disconnect()
        return tables

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

    # --------------------------------------------------
    # Safety
    # --------------------------------------------------
    def preview_delete(self, query: str):
        q = query.strip().rstrip(";")
        if not q.lower().startswith("delete"):
            return None

        count_sql = q.lower().replace("delete", "select count(*)", 1)
        self.connect()
        cur = self._conn.cursor()
        cur.execute(count_sql)
        row = cur.fetchone()
        cur.close()
        self.disconnect()
        return row[0] if row else 0

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
