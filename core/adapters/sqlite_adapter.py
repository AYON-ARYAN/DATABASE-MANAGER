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
        # check_same_thread=False is needed for multi-threaded Flask apps
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def get_connection(self):
        if not self._conn:
            self.connect()
        return self._conn

    def release_connection(self, conn):
        # We keep the singleton alive for SQLite
        pass

    def disconnect(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def test_connection(self) -> bool:
        try:
            conn = self.get_connection()
            conn.execute("SELECT 1")
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
        conn = self.get_connection()
        cur = conn.cursor()
        try:
            cur.execute(query)
            if cur.description:
                columns = [desc[0] for desc in cur.description]
                rows = [list(r) for r in cur.fetchall()]
            else:
                columns = []
                rows = []
            conn.commit()
            return columns, rows
        finally:
            cur.close()
    def dry_run(self, query: str) -> dict:
        conn = self.get_connection()
        # SQLite doesn't support easy dry-run with cursor alone without commit,
        # but we can wrap in a transaction and rollback.
        try:
            conn.execute("BEGIN")
            cur = conn.cursor()
            cur.execute(query)
            affected = conn.total_changes
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
            cur.close()

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
        import shutil
        db_path = self.config.get("db_path", "db/main.db")
        if not os.path.exists(db_path):
            return False
        shutil.copy(db_path, filepath)
        return True

    def restore_snapshot(self, filepath: str) -> bool:
        import shutil
        db_path = self.config.get("db_path", "db/main.db")
        if not os.path.exists(filepath):
            return False
        shutil.copy(filepath, db_path)
        return True
