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

            # Column info with PK marker
            cur.execute(f'PRAGMA table_info("{table_name}");')
            cols = cur.fetchall()
            for col in cols:
                pk_marker = " [PRIMARY KEY]" if col[5] else ""
                notnull = " NOT NULL" if col[3] else ""
                default = f" DEFAULT {col[4]}" if col[4] is not None else ""
                schema += f"  - {col[1]} ({col[2]}{notnull}{default}{pk_marker})\n"

            # Foreign keys
            cur.execute(f'PRAGMA foreign_key_list("{table_name}");')
            fks = cur.fetchall()
            if fks:
                schema += f"  FOREIGN KEYS:\n"
                for fk in fks:
                    schema += f"    - {fk[3]} -> {fk[2]}.{fk[4]}\n"

            # Indexes
            cur.execute(f'PRAGMA index_list("{table_name}");')
            indexes = cur.fetchall()
            if indexes:
                schema += f"  INDEXES:\n"
                for idx in indexes:
                    idx_name = idx[1]
                    unique = "UNIQUE " if idx[2] else ""
                    cur.execute(f'PRAGMA index_info("{idx_name}");')
                    idx_cols = [ic[2] for ic in cur.fetchall()]
                    schema += f"    - {unique}{idx_name} ({', '.join(idx_cols)})\n"

            # Sample data (3 rows) for context - skip binary/blob columns
            try:
                cur.execute(f'SELECT * FROM "{table_name}" LIMIT 3;')
                sample_rows = cur.fetchall()
                if sample_rows:
                    col_names = [c[1] for c in cols]
                    col_types = [c[2].upper() for c in cols]
                    schema += f"  SAMPLE DATA ({len(sample_rows)} rows):\n"
                    for sr in sample_rows:
                        pairs = []
                        for i in range(min(len(col_names), len(sr))):
                            if col_types[i] in ("BLOB", "BINARY", "VARBINARY", "IMAGE"):
                                continue
                            val = sr[i]
                            if isinstance(val, bytes):
                                continue
                            val_str = str(val)[:60]
                            pairs.append(f"{col_names[i]}={val_str}")
                        schema += f"    {', '.join(pairs)}\n"
            except Exception:
                pass

        self.disconnect()
        return schema

    def get_foreign_keys(self) -> list:
        """Returns all foreign key relationships across all tables."""
        self.connect()
        cur = self._conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [r[0] for r in cur.fetchall()]
        fk_list = []
        for table in tables:
            cur.execute(f'PRAGMA foreign_key_list("{table}");')
            for fk in cur.fetchall():
                fk_list.append({
                    "from_table": table,
                    "from_column": fk[3],
                    "to_table": fk[2],
                    "to_column": fk[4],
                })
        self.disconnect()
        return fk_list

    def get_indexes(self) -> list:
        """Returns all indexes across all tables."""
        self.connect()
        cur = self._conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [r[0] for r in cur.fetchall()]
        idx_list = []
        for table in tables:
            cur.execute(f'PRAGMA index_list("{table}");')
            for idx in cur.fetchall():
                cur.execute(f'PRAGMA index_info("{idx[1]}");')
                cols = [ic[2] for ic in cur.fetchall()]
                idx_list.append({
                    "table": table,
                    "index_name": idx[1],
                    "unique": bool(idx[2]),
                    "columns": cols,
                })
        self.disconnect()
        return idx_list

    def describe_table(self, table_name: str) -> dict:
        """Returns detailed info about a single table."""
        self.connect()
        cur = self._conn.cursor()

        # Columns
        cur.execute(f'PRAGMA table_info("{table_name}");')
        columns = []
        for col in cur.fetchall():
            columns.append({
                "name": col[1], "type": col[2],
                "not_null": bool(col[3]), "default": col[4],
                "primary_key": bool(col[5]),
            })

        # Foreign keys
        cur.execute(f'PRAGMA foreign_key_list("{table_name}");')
        fks = [{"from": fk[3], "to_table": fk[2], "to_column": fk[4]} for fk in cur.fetchall()]

        # Indexes
        cur.execute(f'PRAGMA index_list("{table_name}");')
        indexes = []
        for idx in cur.fetchall():
            cur.execute(f'PRAGMA index_info("{idx[1]}");')
            cols = [ic[2] for ic in cur.fetchall()]
            indexes.append({"name": idx[1], "unique": bool(idx[2]), "columns": cols})

        # Row count
        cur.execute(f'SELECT COUNT(*) FROM "{table_name}";')
        row_count = cur.fetchone()[0]

        self.disconnect()
        return {
            "table": table_name, "columns": columns,
            "foreign_keys": fks, "indexes": indexes,
            "row_count": row_count,
        }

    def get_constraints(self) -> list:
        """Returns all constraints (PK, FK, NOT NULL, UNIQUE) across all tables."""
        self.connect()
        cur = self._conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [r[0] for r in cur.fetchall()]
        constraints = []
        for t in tables:
            cur.execute(f'PRAGMA table_info("{t}");')
            for col in cur.fetchall():
                if col[5]:
                    constraints.append({"table": t, "type": "PRIMARY KEY", "details": col[1]})
            cur.execute(f'PRAGMA foreign_key_list("{t}");')
            for fk in cur.fetchall():
                constraints.append({"table": t, "type": "FOREIGN KEY", "details": f"{fk[3]} -> {fk[2]}.{fk[4]}"})
            cur.execute(f'PRAGMA table_info("{t}");')
            for col in cur.fetchall():
                if col[3]:
                    constraints.append({"table": t, "type": "NOT NULL", "details": col[1]})
            cur.execute(f'PRAGMA index_list("{t}");')
            for idx in cur.fetchall():
                if idx[2]:
                    cur.execute(f'PRAGMA index_info("{idx[1]}");')
                    idx_cols = [ic[2] for ic in cur.fetchall()]
                    constraints.append({"table": t, "type": "UNIQUE", "details": f"{idx[1]} ({', '.join(idx_cols)})"})
        self.disconnect()
        return constraints

    def get_create_table(self, table_name: str) -> str:
        """Returns the DDL / CREATE TABLE statement for a table."""
        self.connect()
        cur = self._conn.cursor()
        cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        row = cur.fetchone()
        self.disconnect()
        return row[0] if row and row[0] else f"-- Table '{table_name}' not found"

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
