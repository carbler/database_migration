import pytest
from unittest.mock import MagicMock, patch, call
from src.infrastructure.connectors.mysql_connector import MySQLConnector
from src.infrastructure.connectors.postgresql_connector import PostgreSQLConnector
from src.core.domain.value_objects import ConnectionConfig, DatabaseType
from src.core.domain.entities import Table, Column, ForeignKey

@pytest.fixture
def mysql_config():
    return ConnectionConfig(
        db_type=DatabaseType.MYSQL,
        host='localhost',
        port=3306,
        database='test_db',
        user='root',
        password='password'
    )

@pytest.fixture
def postgres_config():
    return ConnectionConfig(
        db_type=DatabaseType.POSTGRESQL,
        host='localhost',
        port=5432,
        database='test_db',
        user='postgres',
        password='password'
    )

def test_mysql_connector_connect(mysql_config):
    with patch('src.infrastructure.connectors.mysql_connector.pymysql') as mock_pymysql:
        mock_conn = MagicMock()
        mock_pymysql.connect.return_value = mock_conn

        connector = MySQLConnector(mysql_config)
        connector.connect()
        mock_pymysql.connect.assert_called_once()

        connector.disconnect()
        mock_conn.close.assert_called_once()

def test_mysql_get_tables(mysql_config):
    with patch('src.infrastructure.connectors.mysql_connector.pymysql') as mock_pymysql:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_pymysql.connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Mock sequence
        mock_cursor.fetchall.side_effect = [
            [{'Tables_in_test_db': 'users'}], # SHOW TABLES
            [{'Field': 'id', 'Type': 'int', 'Null': 'NO', 'Key': 'PRI', 'Default': None, 'Extra': 'auto_increment'}], # DESCRIBE users
            [] # get_foreign_keys
        ]

        mock_cursor.fetchone.side_effect = [
            {'Create Table': 'CREATE TABLE `users` ...'}, # SHOW CREATE TABLE
            {'count': 100} # count_rows (if called)
        ]

        connector = MySQLConnector(mysql_config)
        connector.connect()
        tables = connector.get_tables()

        assert len(tables) == 1
        assert tables[0].name == 'users'
        assert len(tables[0].columns) == 1
        assert tables[0].columns[0].name == 'id'
        assert tables[0].raw_create_statement == 'CREATE TABLE `users` ...'

def test_postgresql_connector_connect(postgres_config):
    with patch('src.infrastructure.connectors.postgresql_connector.psycopg2') as mock_psycopg2:
        mock_conn = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn

        connector = PostgreSQLConnector(postgres_config)
        connector.connect()
        mock_psycopg2.connect.assert_called_once()

        connector.disconnect()
        mock_conn.close.assert_called_once()
