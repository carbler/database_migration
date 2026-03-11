"""Post-migration validation."""

from __future__ import annotations

from dataclasses import dataclass, field

from db_clone.connectors.base import BaseConnector
from db_clone.logging_config import get_logger
from db_clone.models import ObjectType

log = get_logger(__name__)


@dataclass
class ValidationResult:
    passed: bool = True
    checks: list[ValidationCheck] = field(default_factory=list)


@dataclass
class ValidationCheck:
    name: str
    passed: bool
    details: str = ""


class Validator:
    """Validates that source and target databases match."""

    def __init__(self, source: BaseConnector, target: BaseConnector) -> None:
        self.source = source
        self.target = target

    def validate(self) -> ValidationResult:
        result = ValidationResult()

        # Compare object counts
        source_objects = self.source.discover_all()
        target_objects = self.target.discover_all()

        for otype in ObjectType:
            if otype == ObjectType.DATA:
                continue
            src_count = len(source_objects.get(otype, []))
            tgt_count = len(target_objects.get(otype, []))
            check = ValidationCheck(
                name=f"{otype.value}_count",
                passed=src_count == tgt_count,
                details=f"source={src_count}, target={tgt_count}",
            )
            result.checks.append(check)
            if not check.passed:
                result.passed = False
                log.warning("validation_mismatch", type=otype.value,
                           source=src_count, target=tgt_count)

        # Compare row counts per table
        source_tables = source_objects.get(ObjectType.TABLE, [])
        for table_obj in source_tables:
            src_rows = self.source.get_row_count(table_obj.schema, table_obj.name)
            tgt_rows = self.target.get_row_count(table_obj.schema, table_obj.name)
            check = ValidationCheck(
                name=f"rows_{table_obj.full_name}",
                passed=src_rows == tgt_rows,
                details=f"source={src_rows}, target={tgt_rows}",
            )
            result.checks.append(check)
            if not check.passed:
                result.passed = False

        return result
