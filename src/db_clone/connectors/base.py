"""Abstract base connector for database operations."""

from __future__ import annotations

import abc
from typing import Any, Iterator

from db_clone.models import DbObject, DbType, ObjectType, TableInfo


class BaseConnector(abc.ABC):
    """Abstract base class for database connectors."""

    db_type: DbType

    def __init__(self, url: str) -> None:
        self.url = url
        self._connection: Any = None

    @abc.abstractmethod
    def connect(self) -> None:
        """Establish connection to the database."""

    @abc.abstractmethod
    def disconnect(self) -> None:
        """Close connection."""

    @abc.abstractmethod
    def test_connection(self) -> bool:
        """Test if the connection is alive."""

    def __enter__(self) -> BaseConnector:
        self.connect()
        return self

    def __exit__(self, *args: Any) -> None:
        self.disconnect()

    # --- Discovery ---

    @abc.abstractmethod
    def discover_schemas(self) -> list[DbObject]:
        """List all user schemas."""

    @abc.abstractmethod
    def discover_extensions(self) -> list[DbObject]:
        """List extensions (PostgreSQL) or empty for MySQL."""

    @abc.abstractmethod
    def discover_custom_types(self) -> list[DbObject]:
        """List custom types and enums."""

    @abc.abstractmethod
    def discover_sequences(self) -> list[DbObject]:
        """List sequences."""

    @abc.abstractmethod
    def discover_tables(self) -> list[DbObject]:
        """List tables (structure only, no FKs in DDL)."""

    @abc.abstractmethod
    def discover_indexes(self) -> list[DbObject]:
        """List indexes (non-PK, non-unique-constraint)."""

    @abc.abstractmethod
    def discover_foreign_keys(self) -> list[DbObject]:
        """List foreign key constraints."""

    @abc.abstractmethod
    def discover_views(self) -> list[DbObject]:
        """List views."""

    @abc.abstractmethod
    def discover_functions(self) -> list[DbObject]:
        """List functions and procedures."""

    @abc.abstractmethod
    def discover_triggers(self) -> list[DbObject]:
        """List triggers."""

    def discover_all(self) -> dict[ObjectType, list[DbObject]]:
        """Discover all objects grouped by type."""
        return {
            ObjectType.SCHEMA: self.discover_schemas(),
            ObjectType.EXTENSION: self.discover_extensions(),
            ObjectType.CUSTOM_TYPE: self.discover_custom_types(),
            ObjectType.SEQUENCE: self.discover_sequences(),
            ObjectType.TABLE: self.discover_tables(),
            ObjectType.INDEX: self.discover_indexes(),
            ObjectType.FOREIGN_KEY: self.discover_foreign_keys(),
            ObjectType.VIEW: self.discover_views(),
            ObjectType.FUNCTION: self.discover_functions(),
            ObjectType.TRIGGER: self.discover_triggers(),
        }

    # --- Table info ---

    @abc.abstractmethod
    def get_table_info(self, schema: str, table: str) -> TableInfo:
        """Get table metadata for data transfer."""

    @abc.abstractmethod
    def get_row_count(self, schema: str, table: str) -> int:
        """Get estimated row count."""

    # --- Data reading ---

    @abc.abstractmethod
    def read_rows(
        self, schema: str, table: str, batch_size: int, offset: int = 0
    ) -> Iterator[list[tuple]]:
        """Yield batches of rows using server-side cursor."""

    @abc.abstractmethod
    def get_columns(self, schema: str, table: str) -> list[str]:
        """Get ordered column names for a table."""

    # --- Writing ---

    @abc.abstractmethod
    def execute_ddl(self, sql: str) -> None:
        """Execute a DDL statement."""

    @abc.abstractmethod
    def insert_rows(
        self, schema: str, table: str, columns: list[str], rows: list[tuple]
    ) -> int:
        """Insert a batch of rows. Returns count inserted."""

    @abc.abstractmethod
    def disable_fk_checks(self) -> None:
        """Disable FK constraint checking for the session."""

    @abc.abstractmethod
    def enable_fk_checks(self) -> None:
        """Re-enable FK constraint checking."""

    @abc.abstractmethod
    def update_sequences(self, schema: str, table: str) -> None:
        """Update auto-increment/sequence values after data load."""

    @abc.abstractmethod
    def drop_object(self, obj: DbObject) -> None:
        """Drop an object (for overwrite strategy)."""

    @abc.abstractmethod
    def object_exists(self, obj: DbObject) -> bool:
        """Check if an object exists in the target."""

    @abc.abstractmethod
    def get_database_info(self) -> dict[str, Any]:
        """Get database metadata (version, size, etc.)."""
