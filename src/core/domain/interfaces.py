from abc import ABC, abstractmethod
from typing import List, Generator, Any, Optional
from src.core.domain.entities import Table, Database, ForeignKey
from src.core.domain.value_objects import ConnectionConfig

class DatabaseConnector(ABC):
    @abstractmethod
    def connect(self) -> None:
        pass

    @abstractmethod
    def disconnect(self) -> None:
        pass

    @abstractmethod
    def get_tables(self) -> List[Table]:
        pass

    @abstractmethod
    def get_foreign_keys(self, table_name: str) -> List[ForeignKey]:
        pass

    @abstractmethod
    def get_schema(self, table_name: str) -> Table:
        pass

    @abstractmethod
    def create_table(self, table: Table) -> None:
        pass

    @abstractmethod
    def drop_table(self, table_name: str) -> None:
        pass

    @abstractmethod
    def truncate_table(self, table_name: str) -> None:
        pass

    @abstractmethod
    def fetch_data(self, table_name: str, columns: List[str] = None, batch_size: int = 1000) -> Generator[List[Any], None, None]:
        pass

    @abstractmethod
    def insert_data(self, table_name: str, data: List[Any], columns: List[str], on_conflict: str = 'raise', primary_key: Optional[List[str]] = None) -> int:
        pass

    @abstractmethod
    def disable_foreign_keys(self) -> None:
        pass

    @abstractmethod
    def enable_foreign_keys(self) -> None:
        pass

    @abstractmethod
    def count_rows(self, table_name: str) -> int:
        pass

    def get_installed_extensions(self) -> List[str]:
        return []

    def fetch_sample_rows(self, table_name: str, pk_columns: List[str], limit: int = 1000) -> List[Any]:
        return []

class MigrationObserver(ABC):
    @abstractmethod
    def on_start(self, total_tables: int) -> None:
        pass

    @abstractmethod
    def on_table_start(self, table_name: str, total_rows: int) -> None:
        pass

    @abstractmethod
    def on_batch_processed(self, table_name: str, row_count: int) -> None:
        pass

    @abstractmethod
    def on_table_complete(self, table_name: str, duration: float) -> None:
        pass

    @abstractmethod
    def on_error(self, table_name: str, error: str) -> None:
        pass

    @abstractmethod
    def on_complete(self, stats: Any) -> None:
        pass

class ConflictResolutionStrategy(ABC):
    def prepare(self, target_connector: DatabaseConnector, table: str) -> None:
        pass

    @abstractmethod
    def resolve(self, target_connector: DatabaseConnector, table: str, data: List[Any], columns: List[str], primary_key: Optional[List[str]] = None) -> None:
        pass
