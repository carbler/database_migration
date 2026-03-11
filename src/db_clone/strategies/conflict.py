"""Conflict resolution strategies for database cloning."""

from __future__ import annotations

from db_clone.connectors.base import BaseConnector
from db_clone.logging_config import get_logger
from db_clone.models import ConflictStrategy, DbObject

log = get_logger(__name__)


def resolve_conflict(
    target: BaseConnector,
    obj: DbObject,
    strategy: ConflictStrategy,
) -> bool:
    """Resolve a conflict when an object already exists.

    Returns True if we should proceed with creation, False to skip.
    """
    if strategy == ConflictStrategy.FAIL:
        raise ConflictError(
            f"Object {obj.full_name} already exists in target "
            f"(strategy=fail)"
        )
    elif strategy == ConflictStrategy.SKIP:
        log.info("conflict_skip", object=obj.full_name)
        return False
    elif strategy == ConflictStrategy.OVERWRITE:
        log.info("conflict_overwrite", object=obj.full_name)
        target.drop_object(obj)
        return True
    return True


class ConflictError(Exception):
    """Raised when a conflict cannot be resolved."""
