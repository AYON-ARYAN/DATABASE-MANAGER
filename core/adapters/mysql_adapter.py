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
        self.connect()
        cur = self._conn.cursor()
        db = self.config.get("database", "")

        cur.execute("""
            SELECT TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'
        """, (db,))
        tables = cur.fetchall()

        schema = ""
        for (table_name,) in tables:
            schema += f"\nTABLE {table_name}:\n"
            cur.execute("""
                SELECT COLUMN_NAME, DATA_TYPE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                ORDER BY ORDINAL_POSITION
            """, (db, table_name))
            for col_name, data_type in cur.fetchall():
                schema += f"  - {col_name} ({data_type})\n"

        self.disconnect()
        return schema

    def list_tables(self) -> list:
        self.connect()
        cur = self._conn.cursor()
        db = self.config.get("database", "")
        cur.execute("""
            SELECT TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'
        """, (db,))
        tables = [row[0] for row in cur.fetchall()]
        self.disconnect()
        return tables

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
        self.disconnect()
        return row[0] if row else 0

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
