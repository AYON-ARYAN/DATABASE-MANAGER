"""
Database Adapter Registry
Maps database type strings to their adapter classes.
"""

from core.adapters.sqlite_adapter import SQLiteAdapter
from core.adapters.mysql_adapter import MySQLAdapter
from core.adapters.postgres_adapter import PostgresAdapter
from core.adapters.mssql_adapter import MSSQLAdapter
from core.adapters.oracle_adapter import OracleAdapter
from core.adapters.mongo_adapter import MongoAdapter
from core.adapters.cassandra_adapter import CassandraAdapter
from core.adapters.redis_adapter import RedisAdapter

ADAPTER_REGISTRY = {
    "sqlite":     SQLiteAdapter,
    "mysql":      MySQLAdapter,
    "postgresql": PostgresAdapter,
    "mssql":      MSSQLAdapter,
    "oracle":     OracleAdapter,
    "mongodb":    MongoAdapter,
    "cassandra":  CassandraAdapter,
    "redis":      RedisAdapter,
}

DB_TYPES = list(ADAPTER_REGISTRY.keys())

# Display names for the UI
DB_DISPLAY_NAMES = {
    "sqlite":     "SQLite",
    "mysql":      "MySQL",
    "postgresql": "PostgreSQL",
    "mssql":      "Microsoft SQL Server",
    "oracle":     "Oracle Database",
    "mongodb":    "MongoDB",
    "cassandra":  "Apache Cassandra",
    "redis":      "Redis",
}

# Connection field definitions per DB type (for dynamic form rendering)
DB_CONNECTION_FIELDS = {
    "sqlite": [
        {"name": "db_path", "label": "Database File Path", "type": "text", "placeholder": "db/main.db"}
    ],
    "mysql": [
        {"name": "host", "label": "Host", "type": "text", "placeholder": "localhost"},
        {"name": "port", "label": "Port", "type": "number", "placeholder": "3306"},
        {"name": "username", "label": "Username", "type": "text", "placeholder": "root"},
        {"name": "password", "label": "Password", "type": "password", "placeholder": ""},
        {"name": "database", "label": "Database Name", "type": "text", "placeholder": "mydb"},
    ],
    "postgresql": [
        {"name": "host", "label": "Host", "type": "text", "placeholder": "localhost"},
        {"name": "port", "label": "Port", "type": "number", "placeholder": "5432"},
        {"name": "username", "label": "Username", "type": "text", "placeholder": "postgres"},
        {"name": "password", "label": "Password", "type": "password", "placeholder": ""},
        {"name": "database", "label": "Database Name", "type": "text", "placeholder": "mydb"},
    ],
    "mssql": [
        {"name": "host", "label": "Host", "type": "text", "placeholder": "localhost"},
        {"name": "port", "label": "Port", "type": "number", "placeholder": "1433"},
        {"name": "username", "label": "Username", "type": "text", "placeholder": "sa"},
        {"name": "password", "label": "Password", "type": "password", "placeholder": ""},
        {"name": "database", "label": "Database Name", "type": "text", "placeholder": "mydb"},
    ],
    "oracle": [
        {"name": "host", "label": "Host", "type": "text", "placeholder": "localhost"},
        {"name": "port", "label": "Port", "type": "number", "placeholder": "1521"},
        {"name": "username", "label": "Username", "type": "text", "placeholder": "system"},
        {"name": "password", "label": "Password", "type": "password", "placeholder": ""},
        {"name": "service_name", "label": "Service Name", "type": "text", "placeholder": "XEPDB1"},
    ],
    "mongodb": [
        {"name": "host", "label": "Host", "type": "text", "placeholder": "localhost"},
        {"name": "port", "label": "Port", "type": "number", "placeholder": "27017"},
        {"name": "username", "label": "Username (optional)", "type": "text", "placeholder": ""},
        {"name": "password", "label": "Password (optional)", "type": "password", "placeholder": ""},
        {"name": "database", "label": "Database Name", "type": "text", "placeholder": "mydb"},
    ],
    "cassandra": [
        {"name": "host", "label": "Host", "type": "text", "placeholder": "127.0.0.1"},
        {"name": "port", "label": "Port", "type": "number", "placeholder": "9042"},
        {"name": "username", "label": "Username (optional)", "type": "text", "placeholder": ""},
        {"name": "password", "label": "Password (optional)", "type": "password", "placeholder": ""},
        {"name": "keyspace", "label": "Keyspace", "type": "text", "placeholder": "my_keyspace"},
    ],
    "redis": [
        {"name": "host", "label": "Host", "type": "text", "placeholder": "localhost"},
        {"name": "port", "label": "Port", "type": "number", "placeholder": "6379"},
        {"name": "password", "label": "Password (optional)", "type": "password", "placeholder": ""},
        {"name": "db_number", "label": "DB Number", "type": "number", "placeholder": "0"},
    ],
}


def get_adapter(db_type: str):
    """Returns the adapter CLASS for a given database type string."""
    cls = ADAPTER_REGISTRY.get(db_type)
    if not cls:
        raise ValueError(f"Unsupported database type: {db_type}")
    return cls
