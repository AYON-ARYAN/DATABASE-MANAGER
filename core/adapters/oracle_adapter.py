"""
Oracle Database Adapter
Uses oracledb (thin mode — no Instant Client required).
"""

from core.adapters.base import DatabaseAdapter


class OracleAdapter(DatabaseAdapter):

    @property
    def dialect(self):
        return "oracle"

    # --------------------------------------------------
    # Connection
    # --------------------------------------------------
    def connect(self):
        import oracledb
        dsn = f"{self.config.get('host', 'localhost')}:{self.config.get('port', 1521)}/{self.config.get('service_name', 'XEPDB1')}"
        self._conn = oracledb.connect(
            user=self.config.get("username", "system"),
            password=self.config.get("password", ""),
            dsn=dsn,
        )

    def disconnect(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def test_connection(self) -> bool:
        try:
            self.connect()
            cur = self._conn.cursor()
            cur.execute("SELECT 1 FROM DUAL")
            cur.close()
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

        cur.execute("""
            SELECT table_name FROM user_tables ORDER BY table_name
        """)
        tables = cur.fetchall()

        schema = ""
        for (table_name,) in tables:
            schema += f"\nTABLE {table_name}:\n"
            cur.execute("""
                SELECT column_name, data_type
                FROM user_tab_columns
                WHERE table_name = :1
                ORDER BY column_id
            """, (table_name,))
            for col_name, data_type in cur.fetchall():
                schema += f"  - {col_name} ({data_type})\n"

        cur.close()
        self.disconnect()
        return schema

    def list_tables(self) -> list:
        self.connect()
        cur = self._conn.cursor()
        cur.execute("SELECT table_name FROM user_tables ORDER BY table_name")
        tables = [row[0] for row in cur.fetchall()]
        cur.close()
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
        cur.close()
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
        cur.close()
        self.disconnect()
        return row[0] if row else 0
