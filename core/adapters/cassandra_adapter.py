"""
Apache Cassandra Adapter
Uses cassandra-driver. LLM generates CQL (Cassandra Query Language).
"""

from core.adapters.base import DatabaseAdapter


class CassandraAdapter(DatabaseAdapter):

    @property
    def dialect(self):
        return "cassandra"

    @property
    def is_nosql(self):
        return True

    # --------------------------------------------------
    # Connection
    # --------------------------------------------------
    def connect(self):
        from cassandra.cluster import Cluster
        from cassandra.auth import PlainTextAuthProvider

        host = self.config.get("host", "127.0.0.1")
        port = int(self.config.get("port", 9042))
        username = self.config.get("username", "")
        password = self.config.get("password", "")
        keyspace = self.config.get("keyspace", "")

        auth = None
        if username and password:
            auth = PlainTextAuthProvider(username=username, password=password)

        self._cluster = Cluster(
            contact_points=[host],
            port=port,
            auth_provider=auth,
        )
        self._session = self._cluster.connect(keyspace if keyspace else None)

    def disconnect(self):
        if hasattr(self, "_cluster") and self._cluster:
            self._cluster.shutdown()
            self._cluster = None
            self._session = None

    def test_connection(self) -> bool:
        try:
            self.connect()
            # Simple connectivity check
            self._session.execute("SELECT release_version FROM system.local")
            self.disconnect()
            return True
        except Exception:
            return False

    # --------------------------------------------------
    # Schema
    # --------------------------------------------------
    def get_schema(self) -> str:
        keyspace = self.config.get("keyspace", "")
        if not keyspace:
            return "(no keyspace selected)"

        self.connect()
        rows = self._session.execute("""
            SELECT table_name FROM system_schema.tables
            WHERE keyspace_name = %s
        """, (keyspace,))

        tables = [row.table_name for row in rows]
        schema = ""

        for table_name in tables:
            schema += f"\nTABLE {table_name}:\n"
            cols = self._session.execute("""
                SELECT column_name, type FROM system_schema.columns
                WHERE keyspace_name = %s AND table_name = %s
            """, (keyspace, table_name))
            for col in cols:
                schema += f"  - {col.column_name} ({col.type})\n"

        self.disconnect()
        return schema

    def list_tables(self) -> list:
        keyspace = self.config.get("keyspace", "")
        if not keyspace:
            return []

        self.connect()
        rows = self._session.execute("""
            SELECT table_name FROM system_schema.tables
            WHERE keyspace_name = %s
        """, (keyspace,))
        tables = [row.table_name for row in rows]
        self.disconnect()
        return tables

    # --------------------------------------------------
    # Execution
    # --------------------------------------------------
    def execute(self, query: str) -> tuple:
        self.connect()
        result = self._session.execute(query)

        if result.column_names:
            columns = list(result.column_names)
            rows = [list(row) for row in result]
        else:
            columns = []
            rows = []

        self.disconnect()
        return columns, rows

    # --------------------------------------------------
    # Safety
    # --------------------------------------------------
    def preview_delete(self, query: str):
        q = query.strip().rstrip(";")
        if not q.lower().startswith("delete"):
            return None

        # CQL DELETE → SELECT COUNT(*)
        count_cql = q.lower().replace("delete", "select count(*)", 1)
        try:
            self.connect()
            result = self._session.execute(count_cql)
            row = result.one()
            self.disconnect()
            return row[0] if row else 0
        except Exception:
            self.disconnect()
            return None
