from typing import List, Optional
from src.core.domain.interfaces import DatabaseConnector
from src.core.domain.entities import Table

class SchemaRepository:
    def __init__(self, connector: DatabaseConnector):
        self.connector = connector

    def get_tables(self) -> List[Table]:
        return self.connector.get_tables()

    def get_table(self, table_name: str) -> Table:
        return self.connector.get_schema(table_name)

    def create_table(self, table: Table) -> None:
        self.connector.create_table(table)

    def drop_table(self, table_name: str) -> None:
        self.connector.drop_table(table_name)

    def get_foreign_keys(self, table_name: str):
        return self.connector.get_foreign_keys(table_name)
