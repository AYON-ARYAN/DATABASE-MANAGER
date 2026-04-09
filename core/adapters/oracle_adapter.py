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

        cur.execute("SELECT table_name FROM user_tables ORDER BY table_name")
        tables = [r[0] for r in cur.fetchall()]

        schema = ""
        for table_name in tables:
            schema += f"\nTABLE {table_name}:\n"

            # Columns with PK, NOT NULL, defaults
            cur.execute("""
                SELECT c.column_name, c.data_type, c.nullable, c.data_default,
                       CASE WHEN pk.column_name IS NOT NULL THEN 1 ELSE 0 END
                FROM user_tab_columns c
                LEFT JOIN (
                    SELECT cc.column_name
                    FROM user_cons_columns cc
                    JOIN user_constraints uc ON cc.constraint_name = uc.constraint_name
                    WHERE uc.constraint_type = 'P' AND uc.table_name = :1
                ) pk ON pk.column_name = c.column_name
                WHERE c.table_name = :2
                ORDER BY c.column_id
            """, (table_name, table_name))
            col_info = cur.fetchall()
            col_names = []
            for col_name, dtype, nullable, default, is_pk in col_info:
                col_names.append(col_name)
                notnull = " NOT NULL" if nullable == "N" else ""
                default_str = f" DEFAULT {str(default).strip()}" if default else ""
                pk_marker = " [PRIMARY KEY]" if is_pk else ""
                schema += f"  - {col_name} ({dtype}{notnull}{default_str}{pk_marker})\n"

            # Foreign keys
            cur.execute("""
                SELECT a.column_name, c_pk.table_name, b.column_name
                FROM user_cons_columns a
                JOIN user_constraints c ON a.constraint_name = c.constraint_name
                JOIN user_cons_columns b ON c.r_constraint_name = b.constraint_name
                JOIN user_constraints c_pk ON c.r_constraint_name = c_pk.constraint_name
                WHERE c.constraint_type = 'R' AND c.table_name = :1
            """, (table_name,))
            fks = cur.fetchall()
            if fks:
                schema += "  FOREIGN KEYS:\n"
                for fk_col, ref_table, ref_col in fks:
                    schema += f"    - {fk_col} -> {ref_table}.{ref_col}\n"

            # Indexes
            cur.execute("""
                SELECT i.index_name, i.uniqueness,
                       LISTAGG(ic.column_name, ', ') WITHIN GROUP (ORDER BY ic.column_position)
                FROM user_indexes i
                JOIN user_ind_columns ic ON i.index_name = ic.index_name
                WHERE i.table_name = :1
                GROUP BY i.index_name, i.uniqueness
            """, (table_name,))
            indexes = cur.fetchall()
            if indexes:
                schema += "  INDEXES:\n"
                for idx_name, uniqueness, idx_cols in indexes:
                    unique = "UNIQUE " if uniqueness == "UNIQUE" else ""
                    schema += f"    - {unique}{idx_name} ({idx_cols})\n"

            # Sample data (3 rows)
            try:
                cur.execute(f'SELECT * FROM "{table_name}" WHERE ROWNUM <= 3')
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
    # Introspection
    # --------------------------------------------------
    def get_foreign_keys(self) -> list:
        self.connect()
        cur = self._conn.cursor()
        cur.execute("""
            SELECT a.table_name, a.column_name,
                   c_pk.table_name, b.column_name
            FROM user_cons_columns a
            JOIN user_constraints c ON a.constraint_name = c.constraint_name
            JOIN user_cons_columns b ON c.r_constraint_name = b.constraint_name
            JOIN user_constraints c_pk ON c.r_constraint_name = c_pk.constraint_name
            WHERE c.constraint_type = 'R'
            ORDER BY a.table_name
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
            SELECT i.table_name, i.index_name, i.uniqueness,
                   LISTAGG(ic.column_name, ',') WITHIN GROUP (ORDER BY ic.column_position)
            FROM user_indexes i
            JOIN user_ind_columns ic ON i.index_name = ic.index_name
            GROUP BY i.table_name, i.index_name, i.uniqueness
            ORDER BY i.table_name, i.index_name
        """)
        results = [
            {"table": r[0], "index_name": r[1],
             "unique": r[2] == "UNIQUE",
             "columns": r[3].split(",") if r[3] else []}
            for r in cur.fetchall()
        ]
        cur.close()
        self.disconnect()
        return results

    def describe_table(self, table_name: str) -> dict:
        self.connect()
        cur = self._conn.cursor()
        tn = table_name.upper()

        # Columns
        cur.execute("""
            SELECT c.column_name, c.data_type, c.nullable,
                   c.data_default,
                   CASE WHEN pk.column_name IS NOT NULL THEN 1 ELSE 0 END
            FROM user_tab_columns c
            LEFT JOIN (
                SELECT cc.column_name
                FROM user_cons_columns cc
                JOIN user_constraints uc ON cc.constraint_name = uc.constraint_name
                WHERE uc.constraint_type = 'P' AND uc.table_name = :1
            ) pk ON pk.column_name = c.column_name
            WHERE c.table_name = :2
            ORDER BY c.column_id
        """, (tn, tn))
        columns = [
            {"name": r[0], "type": r[1],
             "not_null": r[2] == "N",
             "default": r[3], "primary_key": bool(r[4])}
            for r in cur.fetchall()
        ]

        # Foreign keys
        cur.execute("""
            SELECT a.column_name, c_pk.table_name, b.column_name
            FROM user_cons_columns a
            JOIN user_constraints c ON a.constraint_name = c.constraint_name
            JOIN user_cons_columns b ON c.r_constraint_name = b.constraint_name
            JOIN user_constraints c_pk ON c.r_constraint_name = c_pk.constraint_name
            WHERE c.constraint_type = 'R' AND c.table_name = :1
        """, (tn,))
        fks = [{"from": r[0], "to_table": r[1], "to_column": r[2]}
               for r in cur.fetchall()]

        # Indexes
        cur.execute("""
            SELECT i.index_name, i.uniqueness,
                   LISTAGG(ic.column_name, ',') WITHIN GROUP (ORDER BY ic.column_position)
            FROM user_indexes i
            JOIN user_ind_columns ic ON i.index_name = ic.index_name
            WHERE i.table_name = :1
            GROUP BY i.index_name, i.uniqueness
        """, (tn,))
        indexes = [
            {"name": r[0], "unique": r[1] == "UNIQUE",
             "columns": r[2].split(",") if r[2] else []}
            for r in cur.fetchall()
        ]

        # Row count
        cur.execute(f'SELECT COUNT(*) FROM "{tn}"')
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
            SELECT uc.table_name,
                   CASE uc.constraint_type
                       WHEN 'P' THEN 'PRIMARY KEY'
                       WHEN 'R' THEN 'FOREIGN KEY'
                       WHEN 'U' THEN 'UNIQUE'
                       WHEN 'C' THEN 'CHECK'
                   END,
                   uc.constraint_name,
                   LISTAGG(ucc.column_name, ', ') WITHIN GROUP (ORDER BY ucc.position)
            FROM user_constraints uc
            JOIN user_cons_columns ucc ON uc.constraint_name = ucc.constraint_name
            WHERE uc.constraint_type IN ('P', 'R', 'U')
            GROUP BY uc.table_name, uc.constraint_type, uc.constraint_name
            ORDER BY uc.table_name
        """)
        for r in cur.fetchall():
            constraints.append({"table": r[0], "type": r[1], "details": f"{r[2]} ({r[3]})"})

        # NOT NULL
        cur.execute("""
            SELECT table_name, column_name
            FROM user_tab_columns
            WHERE nullable = 'N'
            ORDER BY table_name, column_id
        """)
        for r in cur.fetchall():
            constraints.append({"table": r[0], "type": "NOT NULL", "details": r[1]})

        cur.close()
        self.disconnect()
        return constraints

    def get_create_table(self, table_name: str) -> str:
        self.connect()
        cur = self._conn.cursor()
        tn = table_name.upper()

        cur.execute("""
            SELECT column_name, data_type, data_length, nullable, data_default
            FROM user_tab_columns
            WHERE table_name = :1
            ORDER BY column_id
        """, (tn,))
        cols = cur.fetchall()
        if not cols:
            cur.close()
            self.disconnect()
            return f"-- Table '{table_name}' not found"

        lines = []
        for col_name, dtype, data_len, nullable, default in cols:
            col_def = f"  {col_name} {dtype}"
            if dtype in ("VARCHAR2", "CHAR", "NVARCHAR2", "RAW") and data_len:
                col_def += f"({data_len})"
            if nullable == "N":
                col_def += " NOT NULL"
            if default:
                col_def += f" DEFAULT {str(default).strip()}"
            lines.append(col_def)

        # Primary key
        cur.execute("""
            SELECT LISTAGG(ucc.column_name, ', ') WITHIN GROUP (ORDER BY ucc.position)
            FROM user_constraints uc
            JOIN user_cons_columns ucc ON uc.constraint_name = ucc.constraint_name
            WHERE uc.table_name = :1 AND uc.constraint_type = 'P'
        """, (tn,))
        pk_row = cur.fetchone()
        if pk_row and pk_row[0]:
            lines.append(f"  PRIMARY KEY ({pk_row[0]})")

        cur.close()
        self.disconnect()
        return f'CREATE TABLE "{tn}" (\n' + ",\n".join(lines) + "\n);"

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
