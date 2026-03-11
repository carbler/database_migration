"""Checkpoint/resume system for interrupted migrations."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

from db_clone.logging_config import get_logger
from db_clone.models import ObjectStatus, ObjectType, PhaseState, PhaseStatus

log = get_logger(__name__)

DEFAULT_CHECKPOINT_FILE = ".db-clone-checkpoint.json"


class CheckpointManager:
    """Manages migration state for checkpoint/resume."""

    def __init__(self, path: str = DEFAULT_CHECKPOINT_FILE) -> None:
        self.path = Path(path)
        self.migration_id: str = ""
        self.source_info: dict[str, str] = {}
        self.target_info: dict[str, str] = {}
        self.phases: dict[str, PhaseState] = {}

    def initialize(self, source_url: str, target_url: str) -> None:
        """Start a new migration checkpoint."""
        self.migration_id = uuid.uuid4().hex
        self.source_info = {"host_hash": _hash_url(source_url)}
        self.target_info = {"host_hash": _hash_url(target_url)}
        self.phases = {}
        log.info("checkpoint_initialized", migration_id=self.migration_id)

    def load(self) -> bool:
        """Load checkpoint from file. Returns True if loaded successfully."""
        if not self.path.exists():
            return False
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.migration_id = data.get("migration_id", "")
            self.source_info = data.get("source", {})
            self.target_info = data.get("target", {})

            self.phases = {}
            for phase_name, phase_data in data.get("phases", {}).items():
                ps = PhaseState(
                    status=PhaseStatus(phase_data.get("status", "pending")),
                )
                for obj_name, obj_data in phase_data.get("objects", {}).items():
                    if isinstance(obj_data, dict):
                        ps.objects[obj_name] = ObjectStatus(
                            status=PhaseStatus(obj_data.get("status", "pending")),
                            rows_copied=obj_data.get("rows_copied", 0),
                            total_rows=obj_data.get("total_rows", 0),
                            error=obj_data.get("error"),
                        )
                    else:
                        ps.objects[obj_name] = ObjectStatus(
                            status=PhaseStatus(obj_data),
                        )
                self.phases[phase_name] = ps

            log.info("checkpoint_loaded", migration_id=self.migration_id,
                     phases=len(self.phases))
            return True
        except Exception as e:
            log.error("checkpoint_load_error", error=str(e))
            return False

    def save(self) -> None:
        """Atomically save checkpoint to file."""
        data = {
            "migration_id": self.migration_id,
            "source": self.source_info,
            "target": self.target_info,
            "phases": {},
        }
        for phase_name, ps in self.phases.items():
            phase_data: dict[str, Any] = {"status": ps.status.value, "objects": {}}
            for obj_name, obj_status in ps.objects.items():
                phase_data["objects"][obj_name] = {
                    "status": obj_status.status.value,
                    "rows_copied": obj_status.rows_copied,
                    "total_rows": obj_status.total_rows,
                    "error": obj_status.error,
                }
            data["phases"][phase_name] = phase_data

        # Atomic write
        dir_path = self.path.parent
        fd, tmp_path = tempfile.mkstemp(dir=str(dir_path), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, str(self.path))
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def clear(self) -> None:
        """Remove checkpoint file."""
        if self.path.exists():
            self.path.unlink()
            log.info("checkpoint_cleared")

    def get_phase_state(self, phase: ObjectType) -> PhaseState:
        """Get or create state for a phase."""
        key = phase.value
        if key not in self.phases:
            self.phases[key] = PhaseState()
        return self.phases[key]

    def set_phase_status(self, phase: ObjectType, status: PhaseStatus) -> None:
        ps = self.get_phase_state(phase)
        ps.status = status
        self.save()

    def get_object_status(self, phase: ObjectType, obj_name: str) -> ObjectStatus:
        ps = self.get_phase_state(phase)
        if obj_name not in ps.objects:
            ps.objects[obj_name] = ObjectStatus()
        return ps.objects[obj_name]

    def set_object_status(
        self, phase: ObjectType, obj_name: str, status: ObjectStatus
    ) -> None:
        ps = self.get_phase_state(phase)
        ps.objects[obj_name] = status
        self.save()

    def is_phase_completed(self, phase: ObjectType) -> bool:
        key = phase.value
        if key not in self.phases:
            return False
        return self.phases[key].status == PhaseStatus.COMPLETED

    def is_object_completed(self, phase: ObjectType, obj_name: str) -> bool:
        ps = self.get_phase_state(phase)
        obj = ps.objects.get(obj_name)
        return obj is not None and obj.status == PhaseStatus.COMPLETED

    def matches_migration(self, source_url: str, target_url: str) -> bool:
        """Check if checkpoint matches the current source/target."""
        return (
            self.source_info.get("host_hash") == _hash_url(source_url)
            and self.target_info.get("host_hash") == _hash_url(target_url)
        )

    def get_summary(self) -> dict[str, Any]:
        """Get a human-readable summary of checkpoint state."""
        summary: dict[str, Any] = {
            "migration_id": self.migration_id,
            "phases": {},
        }
        for name, ps in self.phases.items():
            completed = sum(
                1 for o in ps.objects.values() if o.status == PhaseStatus.COMPLETED
            )
            failed = sum(
                1 for o in ps.objects.values() if o.status == PhaseStatus.FAILED
            )
            summary["phases"][name] = {
                "status": ps.status.value,
                "objects_total": len(ps.objects),
                "objects_completed": completed,
                "objects_failed": failed,
            }
        return summary


def _hash_url(url: str) -> str:
    """Hash a URL for checkpoint matching (avoids storing credentials)."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]
