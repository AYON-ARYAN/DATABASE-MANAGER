"""
SQLite Adapter
Wraps the existing SQLite logic into the adapter interface.
"""

import sqlite3
import os
from core.adapters.base import DatabaseAdapter


class SQLiteAdapter(DatabaseAdapter):

    @property
    def dialect(self):
        return "sqlite"

    @property
    def supports_snapshot(self):
        return True

    # --------------------------------------------------
    # Connection
    # --------------------------------------------------
    def connect(self):
        path = self.config.get("db_path", "db/main.db")
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row

    def disconnect(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def test_connection(self) -> bool:
        try:
            self.connect()
            self._conn.execute("SELECT 1")
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
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%';
        """)
        tables = cur.fetchall()
        schema = ""
        for row in tables:
            table_name = row[0]
            schema += f"\nTABLE {table_name}:\n"
            cur.execute(f'PRAGMA table_info("{table_name}");')
            for col in cur.fetchall():
                schema += f"  - {col[1]} ({col[2]})\n"
        self.disconnect()
        return schema

    def list_tables(self) -> list:
        self.connect()
        cur = self._conn.cursor()
        cur.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%';
        """)
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
