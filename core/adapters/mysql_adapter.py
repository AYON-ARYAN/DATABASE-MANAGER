"""
MySQL Adapter
Uses pymysql for MySQL / MariaDB connections.
"""

from core.adapters.base import DatabaseAdapter


class MySQLAdapter(DatabaseAdapter):

    @property
    def dialect(self):
        return "mysql"

    # --------------------------------------------------
    # Connection
    # --------------------------------------------------
    def connect(self):
        import pymysql
        self._conn = pymysql.connect(
            host=self.config.get("host", "localhost"),
            port=int(self.config.get("port", 3306)),
            user=self.config.get("username", "root"),
            password=self.config.get("password", ""),
            database=self.config.get("database", ""),
            charset="utf8mb4",
            cursorclass=pymysql.cursors.Cursor,
        )

    def disconnect(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def test_connection(self) -> bool:
        try:
            self.connect()
            with self._conn.cursor() as cur:
                cur.execute("SELECT 1")
            self.disconnect()
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
        self.connect()
        cur = self._conn.cursor()
        cur.execute(query)

        if cur.description:
            columns = [desc[0] for desc in cur.description]
            rows = [list(r) for r in cur.fetchall()]
        else:
            columns = []
            rows = []

        self._conn.commit()
        self.disconnect()
        return columns, rows

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
