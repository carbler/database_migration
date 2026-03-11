"""Tests for discovery module."""

from unittest.mock import MagicMock

import pytest

from db_clone.engine.discovery import Discovery
from db_clone.models import DbObject, DbType, ObjectType


@pytest.fixture
def mock_connector():
    connector = MagicMock()
    connector.db_type = DbType.POSTGRESQL
    connector.discover_all.return_value = {
        ObjectType.SCHEMA: [],
        ObjectType.EXTENSION: [],
        ObjectType.CUSTOM_TYPE: [],
        ObjectType.SEQUENCE: [],
        ObjectType.TABLE: [
            DbObject(name="users", schema="public", object_type=ObjectType.TABLE),
            DbObject(name="orders", schema="public", object_type=ObjectType.TABLE),
            DbObject(name="temp_data", schema="public", object_type=ObjectType.TABLE),
            DbObject(name="log_entries", schema="public", object_type=ObjectType.TABLE),
        ],
        ObjectType.INDEX: [
            DbObject(name="idx_users", schema="public", object_type=ObjectType.INDEX),
            DbObject(name="idx_temp", schema="public", object_type=ObjectType.INDEX),
        ],
        ObjectType.FOREIGN_KEY: [],
        ObjectType.VIEW: [
            DbObject(name="active_users", schema="public", object_type=ObjectType.VIEW),
        ],
        ObjectType.FUNCTION: [],
        ObjectType.TRIGGER: [],
    }
    return connector


class TestDiscovery:
    def test_discover_all(self, mock_connector):
        d = Discovery(mock_connector)
        result = d.discover()
        assert len(result[ObjectType.TABLE]) == 4

    def test_include_tables(self, mock_connector):
        d = Discovery(mock_connector)
        result = d.discover(include_tables=["users", "orders"])
        assert len(result[ObjectType.TABLE]) == 2
        names = {o.name for o in result[ObjectType.TABLE]}
        assert names == {"users", "orders"}

    def test_exclude_tables(self, mock_connector):
        d = Discovery(mock_connector)
        result = d.discover(exclude_tables=["temp_*", "log_*"])
        assert len(result[ObjectType.TABLE]) == 2
        names = {o.name for o in result[ObjectType.TABLE]}
        assert names == {"users", "orders"}

    def test_views_not_filtered(self, mock_connector):
        """Views are not affected by table filters."""
        d = Discovery(mock_connector)
        result = d.discover(include_tables=["users"])
        assert len(result[ObjectType.VIEW]) == 1
