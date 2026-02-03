from src.core.domain.interfaces import ConflictResolutionStrategy, DatabaseConnector
from typing import List, Any, Optional
import structlog

logger = structlog.get_logger()

class BaseStrategy(ConflictResolutionStrategy):
    def prepare(self, target_connector: DatabaseConnector, table: str) -> None:
        pass

    def resolve(self, target_connector: DatabaseConnector, table: str, data: List[Any], columns: List[str], primary_key: Optional[List[str]] = None) -> None:
        raise NotImplementedError
