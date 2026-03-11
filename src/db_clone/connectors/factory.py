"""Factory for creating database connectors."""

from __future__ import annotations

from db_clone.config import parse_db_type
from db_clone.connectors.base import BaseConnector
from db_clone.models import DbType


def create_connector(url: str) -> BaseConnector:
    """Create the appropriate connector based on the URL scheme."""
    db_type = parse_db_type(url)

    if db_type == DbType.POSTGRESQL:
        from db_clone.connectors.postgresql import PostgreSQLConnector

        return PostgreSQLConnector(url)
    elif db_type == DbType.MYSQL:
        from db_clone.connectors.mysql import MySQLConnector

        return MySQLConnector(url)
    else:
        raise ValueError(f"Unsupported database type: {db_type}")
