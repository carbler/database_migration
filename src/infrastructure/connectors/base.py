from src.core.domain.interfaces import DatabaseConnector
from src.core.domain.value_objects import ConnectionConfig

class BaseConnector(DatabaseConnector):
    def __init__(self, config: ConnectionConfig):
        self.config = config
        self.connection = None
        self.cursor = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
