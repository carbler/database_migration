"""Tests for conflict strategies."""

import pytest

from db_clone.models import ConflictStrategy, DbObject, ObjectType
from db_clone.strategies.conflict import ConflictError, resolve_conflict
from unittest.mock import MagicMock


@pytest.fixture
def target():
    return MagicMock()


@pytest.fixture
def obj():
    return DbObject(name="users", schema="public", object_type=ObjectType.TABLE)


class TestConflictResolution:
    def test_fail_strategy(self, target, obj):
        with pytest.raises(ConflictError):
            resolve_conflict(target, obj, ConflictStrategy.FAIL)

    def test_skip_strategy(self, target, obj):
        result = resolve_conflict(target, obj, ConflictStrategy.SKIP)
        assert result is False
        target.drop_object.assert_not_called()

    def test_overwrite_strategy(self, target, obj):
        result = resolve_conflict(target, obj, ConflictStrategy.OVERWRITE)
        assert result is True
        target.drop_object.assert_called_once_with(obj)
