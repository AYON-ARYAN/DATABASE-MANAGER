"""
Microsoft SQL Server Adapter
Uses pymssql for MSSQL / Azure SQL connections.
"""

from datetime import datetime
from core.adapters.base import DatabaseAdapter


class MSSQLAdapter(DatabaseAdapter):

    @property
    def dialect(self):
        return "mssql"

    @property
    def supports_snapshot(self) -> bool:
        return True

    # --------------------------------------------------
    # Connection
    # --------------------------------------------------
    def connect(self):
        import pymssql
        self._conn = pymssql.connect(
            server=self.config.get("host", "localhost"),
            port=int(self.config.get("port", 1433)),
            user=self.config.get("username", "sa"),
            password=self.config.get("password", ""),
            database=self.config.get("database", "master"),
        )

    def disconnect(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def test_connection(self) -> bool:
        try:
            self.connect()
            cur = self._conn.cursor()
            cur.execute("SELECT 1")
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
            SELECT TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_NAME
        """)
        tables = cur.fetchall()

        schema = ""
        for (table_name,) in tables:
            schema += f"\nTABLE {table_name}:\n"
            cur.execute("""
                SELECT COLUMN_NAME, DATA_TYPE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = %s
                ORDER BY ORDINAL_POSITION
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
            SELECT TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_NAME
        """)
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

        # T-SQL: DELETE FROM x WHERE y → SELECT COUNT(*) FROM x WHERE y
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
        try:
            # Note: sqlcmd cannot easily take a full database backup to a local file
            # without access to the server's filesystem or using BACPAC tools (sqlpackage).
            # We will use sqlcmd with BACKUP DATABASE if running locally,
            # or sqlpackage if we need a .bacpac. Since sqlcmd BACKUP to disk
            # assumes the path is on the *SQL Server's* machine, this may fail
            # for remote databases unless the path is a shared drive.
            # Assuming a local or shared path context for this simple implementation.
            
            db_name = self.config.get("database", "master")
            server = self.config.get("host", "localhost")
            port = self.config.get("port", 1433)
            user = self.config.get("username", "sa")
            password = self.config.get("password", "")

            # Fallback to sqlpackage if expected to produce a local file from remote
            # Using sqlpackage to export a BACPAC
            cmd = [
                "sqlpackage",
                "/Action:Export",
                f"/ssn:tcp:{server},{port}",
                f"/sdn:{db_name}",
                f"/su:{user}",
                f"/sp:{password}",
                f"/tf:{filepath}"
            ]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return True
        except Exception:
            return False

    def restore_snapshot(self, filepath: str) -> bool:
        import subprocess
        try:
            db_name = self.config.get("database", "master")
            server = self.config.get("host", "localhost")
            port = self.config.get("port", 1433)
            user = self.config.get("username", "sa")
            password = self.config.get("password", "")

            # Using sqlpackage to import a BACPAC
            # Note: sqlpackage Import requires the database to not exist,
            # so we'd technically need to drop it first, or use Publish instead of Import.
            # Using Publish to overwrite existing:
            cmd = [
                "sqlpackage",
                "/Action:Publish",
                f"/tsn:tcp:{server},{port}",
                f"/tdn:{db_name}",
                f"/tu:{user}",
                f"/tp:{password}",
                f"/sf:{filepath}"
            ]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return True
        except Exception:
            return False
