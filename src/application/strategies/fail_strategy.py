from src.application.strategies.base_strategy import BaseStrategy, DatabaseConnector
from typing import List, Any, Optional

class FailStrategy(BaseStrategy):
    def resolve(self, target_connector: DatabaseConnector, table: str, data: List[Any], columns: List[str], primary_key: Optional[List[str]] = None) -> None:
        target_connector.insert_data(table, data, columns, on_conflict='raise', primary_key=primary_key)
