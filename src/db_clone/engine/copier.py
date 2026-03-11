"""Object copier - creates objects in the target database."""

from __future__ import annotations

from db_clone.connectors.base import BaseConnector
from db_clone.logging_config import get_logger
from db_clone.models import ConflictStrategy, DbObject, ObjectStatus, PhaseStatus

log = get_logger(__name__)


class ObjectCopier:
    """Copies database objects (DDL) from source to target."""

    def __init__(
        self,
        target: BaseConnector,
        strategy: ConflictStrategy = ConflictStrategy.OVERWRITE,
    ) -> None:
        self.target = target
        self.strategy = strategy

    def copy_object(self, obj: DbObject) -> ObjectStatus:
        """Copy a single object to the target database."""
        status = ObjectStatus()
        status.status = PhaseStatus.IN_PROGRESS

        if not obj.definition:
            log.warning("empty_definition", object=obj.full_name, type=obj.object_type.value)
            status.status = PhaseStatus.SKIPPED
            return status

        try:
            exists = self.target.object_exists(obj)

            if exists:
                if self.strategy == ConflictStrategy.FAIL:
                    status.status = PhaseStatus.FAILED
                    status.error = f"Object {obj.full_name} already exists"
                    return status
                elif self.strategy == ConflictStrategy.SKIP:
                    log.info("object_skipped", object=obj.full_name)
                    status.status = PhaseStatus.SKIPPED
                    return status
                elif self.strategy == ConflictStrategy.OVERWRITE:
                    log.debug("dropping_existing", object=obj.full_name)
                    self.target.drop_object(obj)

            log.debug("creating_object", object=obj.full_name,
                      type=obj.object_type.value)
            self.target.execute_ddl(obj.definition)
            status.status = PhaseStatus.COMPLETED

        except Exception as e:
            log.error("copy_object_error", object=obj.full_name,
                      type=obj.object_type.value, error=str(e))
            status.status = PhaseStatus.FAILED
            status.error = str(e)

        return status
