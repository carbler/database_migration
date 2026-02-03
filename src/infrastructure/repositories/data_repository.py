from typing import List, Generator, Any
from src.core.domain.interfaces import DatabaseConnector

class DataRepository:
    def __init__(self, connector: DatabaseConnector):
        self.connector = connector

    def fetch_data(self, table_name: str, batch_size: int = 1000) -> Generator[List[Any], None, None]:
        return self.connector.fetch_data(table_name, batch_size)

    def insert_data(self, table_name: str, data: List[Any], columns: List[str]) -> int:
        return self.connector.insert_data(table_name, data, columns)

    def disable_foreign_keys(self) -> None:
        self.connector.disable_foreign_keys()

    def enable_foreign_keys(self) -> None:
        self.connector.enable_foreign_keys()

    def count_rows(self, table_name: str) -> int:
        return self.connector.count_rows(table_name)
