from src.core.domain.value_objects import ConnectionConfig, DatabaseType
from src.core.domain.interfaces import DatabaseConnector
from src.infrastructure.connectors.mysql_connector import MySQLConnector
from src.infrastructure.connectors.postgresql_connector import PostgreSQLConnector

class ConnectorFactory:
    @staticmethod
    def create_connector(config: ConnectionConfig) -> DatabaseConnector:
        if config.db_type == DatabaseType.MYSQL:
            return MySQLConnector(config)
        elif config.db_type == DatabaseType.POSTGRESQL:
            return PostgreSQLConnector(config)
        else:
            raise ValueError(f"Unsupported database type: {config.db_type}")
