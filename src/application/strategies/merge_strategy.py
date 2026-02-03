from src.application.strategies.base_strategy import BaseStrategy, DatabaseConnector
from typing import List, Any, Optional

class MergeStrategy(BaseStrategy):
    def resolve(self, target_connector: DatabaseConnector, table: str, data: List[Any], columns: List[str], primary_key: Optional[List[str]] = None) -> None:
        target_connector.insert_data(table, data, columns, on_conflict='update', primary_key=primary_key)
