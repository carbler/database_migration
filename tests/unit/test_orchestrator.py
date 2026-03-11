"""Tests for orchestrator (mocked connectors)."""

from unittest.mock import MagicMock, patch

import pytest

from db_clone.config import Settings
from db_clone.engine.orchestrator import Orchestrator
from db_clone.models import ConflictStrategy, DbObject, ObjectType


@pytest.fixture
def settings():
    return Settings(
        source_url="postgresql://localhost/src",
        target_url="postgresql://localhost/tgt",
        batch_size=100,
        strategy=ConflictStrategy.OVERWRITE,
    )


class TestOrchestrator:
    @patch("db_clone.engine.orchestrator.create_connector")
    def test_get_phases_default(self, mock_create, settings):
        orch = Orchestrator(settings)
        phases = orch._get_phases()
        assert ObjectType.DATA in phases
        assert ObjectType.TABLE in phases

    @patch("db_clone.engine.orchestrator.create_connector")
    def test_get_phases_schema_only(self, mock_create, settings):
        settings.schema_only = True
        orch = Orchestrator(settings)
        phases = orch._get_phases()
        assert ObjectType.DATA not in phases
        assert ObjectType.TABLE in phases

    @patch("db_clone.engine.orchestrator.create_connector")
    def test_get_phases_data_only(self, mock_create, settings):
        settings.data_only = True
        orch = Orchestrator(settings)
        phases = orch._get_phases()
        assert phases == [ObjectType.DATA]
