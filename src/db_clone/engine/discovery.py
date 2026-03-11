"""Database object discovery and introspection."""

from __future__ import annotations

import fnmatch

from db_clone.connectors.base import BaseConnector
from db_clone.logging_config import get_logger
from db_clone.models import DbObject, ObjectType

log = get_logger(__name__)


class Discovery:
    """Discovers and catalogs all objects in a database."""

    def __init__(self, connector: BaseConnector) -> None:
        self.connector = connector

    def discover(
        self,
        include_tables: list[str] | None = None,
        exclude_tables: list[str] | None = None,
    ) -> dict[ObjectType, list[DbObject]]:
        """Discover all database objects, with optional table filtering."""
        log.info("discovery_start", db_type=self.connector.db_type.value)
        objects = self.connector.discover_all()

        if include_tables or exclude_tables:
            objects = self._filter_tables(objects, include_tables, exclude_tables)

        total = sum(len(v) for v in objects.values())
        log.info("discovery_complete", total_objects=total)
        for otype, objs in objects.items():
            if objs:
                log.debug("discovered", type=otype.value, count=len(objs))

        return objects

    def _filter_tables(
        self,
        objects: dict[ObjectType, list[DbObject]],
        include: list[str] | None,
        exclude: list[str] | None,
    ) -> dict[ObjectType, list[DbObject]]:
        """Filter tables and related objects by include/exclude patterns."""
        table_types = {ObjectType.TABLE, ObjectType.DATA, ObjectType.INDEX,
                       ObjectType.FOREIGN_KEY, ObjectType.TRIGGER}

        for otype in table_types:
            if otype not in objects:
                continue
            filtered = []
            for obj in objects[otype]:
                name = obj.name
                if include and not any(fnmatch.fnmatch(name, p) for p in include):
                    continue
                if exclude and any(fnmatch.fnmatch(name, p) for p in exclude):
                    continue
                filtered.append(obj)
            objects[otype] = filtered

        return objects
