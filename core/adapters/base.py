"""
Abstract Base Adapter
All database adapters implement this interface.
"""

from abc import ABC, abstractmethod


class DatabaseAdapter(ABC):
    """
    Universal interface for all database backends.
    Each adapter connects to a specific database engine and
    provides schema introspection, query execution, and safety features.
    """

    def __init__(self, config: dict):
        self.config = config
        self._conn = None

    # --------------------------------------------------
    # Connection
    # --------------------------------------------------
    @abstractmethod
    def connect(self):
        """Establish a live connection to the database."""
        ...

    @abstractmethod
    def disconnect(self):
        """Close the connection."""
        ...

    @abstractmethod
    def test_connection(self) -> bool:
        """Return True if the connection works, False otherwise."""
        ...

    def get_connection(self):
        """Borrow a connection from the pool (or the single persistent one)."""
        if not self._conn:
            self.connect()
        return self._conn

    def release_connection(self, conn):
        """Return a connection to the pool."""
        pass

    # --------------------------------------------------
    # Schema
    # --------------------------------------------------
    @abstractmethod
    def get_schema(self) -> str:
        """
        Return a human-readable schema string for LLM context.
        Example:
            TABLE customers:
              - id (INTEGER)
              - name (TEXT)
        """
        ...

    @abstractmethod
    def list_tables(self) -> list:
        """Return a list of table/collection names."""
        ...

    # --------------------------------------------------
    # Execution
    # --------------------------------------------------
    @abstractmethod
    def execute(self, query: str) -> tuple:
        """
        Execute a query/command.
        Returns (columns: list[str], rows: list[list]) for reads.
        Returns ([], []) for writes.
        """
        ...

    # --------------------------------------------------
    # Safety
    # --------------------------------------------------
    def preview_delete(self, query: str):
        """
        For DELETE queries, return the count of rows that would be affected.
        Override in SQL adapters. Returns None by default.
        """
        return None

    # --------------------------------------------------
    # Snapshots
    # --------------------------------------------------
    def take_snapshot(self, filepath: str) -> bool:
        """Take a database snapshot and save it to filepath. Override if supported."""
        raise NotImplementedError

    def restore_snapshot(self, filepath: str) -> bool:
        """Restore a database snapshot from filepath. Override if supported."""
        raise NotImplementedError

    # --------------------------------------------------
    # Properties
    # --------------------------------------------------
    @property
    def dialect(self) -> str:
        """Return the dialect name, e.g. 'sqlite', 'mysql', 'mongodb'."""
        raise NotImplementedError

    @property
    def is_nosql(self) -> bool:
        """Return True for NoSQL databases."""
        return False

    @property
    def supports_snapshot(self) -> bool:
        """Return True if file-based snapshots are supported."""
        return False

    @property
    def display_name(self) -> str:
        """Human-readable name for UI."""
        from core.adapters import DB_DISPLAY_NAMES
        return DB_DISPLAY_NAMES.get(self.dialect, self.dialect)
