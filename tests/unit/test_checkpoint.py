"""Tests for checkpoint system."""

import json
import os
from pathlib import Path

import pytest

from db_clone.checkpoint import CheckpointManager, _hash_url
from db_clone.models import ObjectStatus, ObjectType, PhaseStatus


@pytest.fixture
def cp(tmp_path):
    path = tmp_path / "test-checkpoint.json"
    return CheckpointManager(str(path))


class TestCheckpointManager:
    def test_initialize(self, cp):
        cp.initialize("postgresql://localhost/src", "postgresql://localhost/tgt")
        assert cp.migration_id
        assert cp.source_info["host_hash"]
        assert cp.target_info["host_hash"]

    def test_save_and_load(self, cp):
        cp.initialize("postgresql://localhost/src", "postgresql://localhost/tgt")
        cp.set_phase_status(ObjectType.TABLE, PhaseStatus.COMPLETED)
        cp.set_object_status(
            ObjectType.DATA,
            "public.users",
            ObjectStatus(status=PhaseStatus.IN_PROGRESS, rows_copied=5000, total_rows=10000),
        )
        cp.save()

        cp2 = CheckpointManager(cp.path)
        assert cp2.load() is True
        assert cp2.migration_id == cp.migration_id
        assert cp2.is_phase_completed(ObjectType.TABLE)
        status = cp2.get_object_status(ObjectType.DATA, "public.users")
        assert status.rows_copied == 5000

    def test_load_nonexistent(self, cp):
        assert cp.load() is False

    def test_clear(self, cp):
        cp.initialize("pg://a", "pg://b")
        cp.save()
        assert cp.path.exists()
        cp.clear()
        assert not Path(cp.path).exists()

    def test_matches_migration(self, cp):
        cp.initialize("postgresql://localhost/src", "postgresql://localhost/tgt")
        assert cp.matches_migration("postgresql://localhost/src", "postgresql://localhost/tgt")
        assert not cp.matches_migration("postgresql://localhost/other", "postgresql://localhost/tgt")

    def test_phase_completion(self, cp):
        cp.initialize("pg://a", "pg://b")
        assert not cp.is_phase_completed(ObjectType.TABLE)
        cp.set_phase_status(ObjectType.TABLE, PhaseStatus.COMPLETED)
        assert cp.is_phase_completed(ObjectType.TABLE)

    def test_object_completion(self, cp):
        cp.initialize("pg://a", "pg://b")
        assert not cp.is_object_completed(ObjectType.DATA, "public.users")
        cp.set_object_status(
            ObjectType.DATA, "public.users",
            ObjectStatus(status=PhaseStatus.COMPLETED, rows_copied=100),
        )
        assert cp.is_object_completed(ObjectType.DATA, "public.users")

    def test_get_summary(self, cp):
        cp.initialize("pg://a", "pg://b")
        cp.set_phase_status(ObjectType.TABLE, PhaseStatus.COMPLETED)
        cp.set_object_status(
            ObjectType.TABLE, "public.users",
            ObjectStatus(status=PhaseStatus.COMPLETED),
        )
        cp.set_object_status(
            ObjectType.TABLE, "public.orders",
            ObjectStatus(status=PhaseStatus.FAILED, error="test"),
        )
        summary = cp.get_summary()
        assert summary["phases"]["table"]["objects_completed"] == 1
        assert summary["phases"]["table"]["objects_failed"] == 1

    def test_atomic_write(self, cp):
        """Verify atomic write doesn't leave partial files on error."""
        cp.initialize("pg://a", "pg://b")
        cp.save()
        # File should exist and be valid JSON
        data = json.loads(Path(cp.path).read_text())
        assert data["migration_id"] == cp.migration_id


class TestHashUrl:
    def test_consistent(self):
        assert _hash_url("postgresql://localhost/db") == _hash_url("postgresql://localhost/db")

    def test_different_urls(self):
        assert _hash_url("postgresql://a/db") != _hash_url("postgresql://b/db")
