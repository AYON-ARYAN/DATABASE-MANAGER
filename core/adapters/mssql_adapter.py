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
        tables = [r[0] for r in cur.fetchall()]

        schema = ""
        for table_name in tables:
            schema += f"\nTABLE {table_name}:\n"

            # Columns with PK, NOT NULL, defaults
            cur.execute("""
                SELECT c.COLUMN_NAME, c.DATA_TYPE, c.IS_NULLABLE,
                       c.COLUMN_DEFAULT,
                       CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 1 ELSE 0 END
                FROM INFORMATION_SCHEMA.COLUMNS c
                LEFT JOIN (
                    SELECT kcu.COLUMN_NAME
                    FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                    JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                        ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
                    WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY' AND tc.TABLE_NAME = %s
                ) pk ON pk.COLUMN_NAME = c.COLUMN_NAME
                WHERE c.TABLE_NAME = %s
                ORDER BY c.ORDINAL_POSITION
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
                SELECT cp.name, tr.name, cr.name
                FROM sys.foreign_key_columns fkc
                JOIN sys.tables tp ON fkc.parent_object_id = tp.object_id
                JOIN sys.columns cp ON fkc.parent_object_id = cp.object_id
                    AND fkc.parent_column_id = cp.column_id
                JOIN sys.tables tr ON fkc.referenced_object_id = tr.object_id
                JOIN sys.columns cr ON fkc.referenced_object_id = cr.object_id
                    AND fkc.referenced_column_id = cr.column_id
                WHERE tp.name = %s
            """, (table_name,))
            fks = cur.fetchall()
            if fks:
                schema += "  FOREIGN KEYS:\n"
                for fk_col, ref_table, ref_col in fks:
                    schema += f"    - {fk_col} -> {ref_table}.{ref_col}\n"

            # Indexes
            cur.execute("""
                SELECT i.name, i.is_unique,
                       STRING_AGG(c.name, ', ') WITHIN GROUP (ORDER BY ic.key_ordinal)
                FROM sys.indexes i
                JOIN sys.tables t ON i.object_id = t.object_id
                JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
                JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
                WHERE t.name = %s AND i.name IS NOT NULL
                GROUP BY i.name, i.is_unique
            """, (table_name,))
            indexes = cur.fetchall()
            if indexes:
                schema += "  INDEXES:\n"
                for idx_name, is_unique, idx_cols in indexes:
                    unique = "UNIQUE " if is_unique else ""
                    schema += f"    - {unique}{idx_name} ({idx_cols})\n"

            # Sample data (3 rows)
            try:
                cur.execute(f"SELECT TOP 3 * FROM [{table_name}]")
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
    # Introspection
    # --------------------------------------------------
    def get_foreign_keys(self) -> list:
        self.connect()
        cur = self._conn.cursor()
        cur.execute("""
            SELECT
                tp.name  AS from_table,
                cp.name  AS from_column,
                tr.name  AS to_table,
                cr.name  AS to_column
            FROM sys.foreign_key_columns fkc
            JOIN sys.tables tp ON fkc.parent_object_id = tp.object_id
            JOIN sys.columns cp ON fkc.parent_object_id = cp.object_id
                AND fkc.parent_column_id = cp.column_id
            JOIN sys.tables tr ON fkc.referenced_object_id = tr.object_id
            JOIN sys.columns cr ON fkc.referenced_object_id = cr.object_id
                AND fkc.referenced_column_id = cr.column_id
        """)
        results = [
            {"from_table": r[0], "from_column": r[1],
             "to_table": r[2], "to_column": r[3]}
            for r in cur.fetchall()
        ]
        cur.close()
        self.disconnect()
        return results

    def get_indexes(self) -> list:
        self.connect()
        cur = self._conn.cursor()
        cur.execute("""
            SELECT
                t.name AS table_name,
                i.name AS index_name,
                i.is_unique,
                STRING_AGG(c.name, ',') WITHIN GROUP (ORDER BY ic.key_ordinal) AS columns
            FROM sys.indexes i
            JOIN sys.tables t ON i.object_id = t.object_id
            JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
            JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
            WHERE i.name IS NOT NULL AND t.is_ms_shipped = 0
            GROUP BY t.name, i.name, i.is_unique
            ORDER BY t.name, i.name
        """)
        results = [
            {"table": r[0], "index_name": r[1],
             "unique": bool(r[2]),
             "columns": r[3].split(",") if r[3] else []}
            for r in cur.fetchall()
        ]
        cur.close()
        self.disconnect()
        return results

    def describe_table(self, table_name: str) -> dict:
        self.connect()
        cur = self._conn.cursor()

        # Columns
        cur.execute("""
            SELECT c.COLUMN_NAME, c.DATA_TYPE, c.IS_NULLABLE,
                   c.COLUMN_DEFAULT,
                   CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 1 ELSE 0 END AS is_pk
            FROM INFORMATION_SCHEMA.COLUMNS c
            LEFT JOIN (
                SELECT kcu.COLUMN_NAME
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                    ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
                WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
                  AND tc.TABLE_NAME = %s
            ) pk ON pk.COLUMN_NAME = c.COLUMN_NAME
            WHERE c.TABLE_NAME = %s
            ORDER BY c.ORDINAL_POSITION
        """, (table_name, table_name))
        columns = [
            {"name": r[0], "type": r[1],
             "not_null": r[2] == "NO",
             "default": r[3], "primary_key": bool(r[4])}
            for r in cur.fetchall()
        ]

        # Foreign keys
        cur.execute("""
            SELECT cp.name, tr.name, cr.name
            FROM sys.foreign_key_columns fkc
            JOIN sys.tables tp ON fkc.parent_object_id = tp.object_id
            JOIN sys.columns cp ON fkc.parent_object_id = cp.object_id
                AND fkc.parent_column_id = cp.column_id
            JOIN sys.tables tr ON fkc.referenced_object_id = tr.object_id
            JOIN sys.columns cr ON fkc.referenced_object_id = cr.object_id
                AND fkc.referenced_column_id = cr.column_id
            WHERE tp.name = %s
        """, (table_name,))
        fks = [{"from": r[0], "to_table": r[1], "to_column": r[2]}
               for r in cur.fetchall()]

        # Indexes
        cur.execute("""
            SELECT i.name, i.is_unique,
                   STRING_AGG(c.name, ',') WITHIN GROUP (ORDER BY ic.key_ordinal)
            FROM sys.indexes i
            JOIN sys.tables t ON i.object_id = t.object_id
            JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
            JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
            WHERE t.name = %s AND i.name IS NOT NULL
            GROUP BY i.name, i.is_unique
        """, (table_name,))
        indexes = [
            {"name": r[0], "unique": bool(r[1]),
             "columns": r[2].split(",") if r[2] else []}
            for r in cur.fetchall()
        ]

        # Row count
        cur.execute(f"SELECT COUNT(*) FROM [{table_name}]")
        row_count = cur.fetchone()[0]

        cur.close()
        self.disconnect()
        return {"table": table_name, "columns": columns,
                "foreign_keys": fks, "indexes": indexes,
                "row_count": row_count}

    def get_constraints(self) -> list:
        self.connect()
        cur = self._conn.cursor()
        constraints = []

        cur.execute("""
            SELECT tc.TABLE_NAME, tc.CONSTRAINT_TYPE, tc.CONSTRAINT_NAME,
                   STRING_AGG(kcu.COLUMN_NAME, ', ') WITHIN GROUP (ORDER BY kcu.ORDINAL_POSITION)
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
            WHERE tc.CONSTRAINT_TYPE IN ('PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE')
            GROUP BY tc.TABLE_NAME, tc.CONSTRAINT_TYPE, tc.CONSTRAINT_NAME
            ORDER BY tc.TABLE_NAME
        """)
        for r in cur.fetchall():
            constraints.append({"table": r[0], "type": r[1], "details": f"{r[2]} ({r[3]})"})

        # NOT NULL
        cur.execute("""
            SELECT TABLE_NAME, COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE IS_NULLABLE = 'NO'
            ORDER BY TABLE_NAME, ORDINAL_POSITION
        """)
        for r in cur.fetchall():
            constraints.append({"table": r[0], "type": "NOT NULL", "details": r[1]})

        cur.close()
        self.disconnect()
        return constraints

    def get_create_table(self, table_name: str) -> str:
        self.connect()
        cur = self._conn.cursor()

        cur.execute("""
            SELECT c.COLUMN_NAME, c.DATA_TYPE, c.CHARACTER_MAXIMUM_LENGTH,
                   c.IS_NULLABLE, c.COLUMN_DEFAULT
            FROM INFORMATION_SCHEMA.COLUMNS c
            WHERE c.TABLE_NAME = %s
            ORDER BY c.ORDINAL_POSITION
        """, (table_name,))
        cols = cur.fetchall()
        if not cols:
            cur.close()
            self.disconnect()
            return f"-- Table '{table_name}' not found"

        lines = []
        for col_name, dtype, max_len, nullable, default in cols:
            col_def = f"  [{col_name}] {dtype}"
            if max_len and max_len > 0:
                col_def += f"({max_len})"
            if nullable == "NO":
                col_def += " NOT NULL"
            if default:
                col_def += f" DEFAULT {default}"
            lines.append(col_def)

        # Primary key
        cur.execute("""
            SELECT STRING_AGG(kcu.COLUMN_NAME, ', ')
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
            WHERE tc.TABLE_NAME = %s AND tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
        """, (table_name,))
        pk_row = cur.fetchone()
        if pk_row and pk_row[0]:
            lines.append(f"  PRIMARY KEY ({pk_row[0]})")

        cur.close()
        self.disconnect()
        return f"CREATE TABLE [{table_name}] (\n" + ",\n".join(lines) + "\n);"

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
