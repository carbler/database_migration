"""Data models and enums for db-clone."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class DbType(str, enum.Enum):
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"


class ObjectType(str, enum.Enum):
    SCHEMA = "schema"
    EXTENSION = "extension"
    CUSTOM_TYPE = "custom_type"
    SEQUENCE = "sequence"
    TABLE = "table"
    DATA = "data"
    INDEX = "index"
    FOREIGN_KEY = "foreign_key"
    VIEW = "view"
    FUNCTION = "function"
    TRIGGER = "trigger"


class PhaseStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ConflictStrategy(str, enum.Enum):
    FAIL = "fail"
    OVERWRITE = "overwrite"
    SKIP = "skip"


# Ordered phases for migration
PHASE_ORDER: list[ObjectType] = [
    ObjectType.SCHEMA,
    ObjectType.EXTENSION,
    ObjectType.CUSTOM_TYPE,
    ObjectType.SEQUENCE,
    ObjectType.TABLE,
    ObjectType.DATA,
    ObjectType.INDEX,
    ObjectType.FOREIGN_KEY,
    ObjectType.VIEW,
    ObjectType.FUNCTION,
    ObjectType.TRIGGER,
]


@dataclass
class DbObject:
    """Represents a database object (table, view, function, etc.)."""

    name: str
    schema: str
    object_type: ObjectType
    definition: str = ""
    dependencies: list[str] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        return f"{self.schema}.{self.name}"


@dataclass
class TableInfo:
    """Metadata about a table for data transfer."""

    name: str
    schema: str
    row_count: int = 0
    primary_key: list[str] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        return f"{self.schema}.{self.name}"


@dataclass
class ObjectStatus:
    """Status of a single object in a phase."""

    status: PhaseStatus = PhaseStatus.PENDING
    rows_copied: int = 0
    total_rows: int = 0
    error: str | None = None


@dataclass
class PhaseState:
    """Status of a migration phase."""

    status: PhaseStatus = PhaseStatus.PENDING
    objects: dict[str, ObjectStatus] = field(default_factory=dict)


@dataclass
class MigrationResult:
    """Summary of a migration run."""

    success: bool = True
    phases_completed: int = 0
    phases_failed: int = 0
    objects_copied: int = 0
    objects_failed: int = 0
    rows_copied: int = 0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
