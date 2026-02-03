from typing import List, Dict, Any
from src.core.domain.interfaces import DatabaseConnector
from src.core.domain.entities import Table
import structlog
import hashlib

logger = structlog.get_logger()

class ValidationReport:
    def __init__(self):
        self.row_counts: Dict[str, Dict[str, int]] = {}
        self.checksums: Dict[str, Dict[str, str]] = {}
        self.errors: List[str] = []
        self.success = True

    def add_count_check(self, table: str, source_count: int, target_count: int):
        self.row_counts[table] = {'source': source_count, 'target': target_count}
        if source_count != target_count:
            self.success = False
            self.errors.append(f"Table {table}: Row count mismatch (Source: {source_count}, Target: {target_count})")

    def add_checksum(self, table: str, match: bool):
        self.checksums[table] = {'match': match}
        if not match:
            self.success = False
            self.errors.append(f"Table {table}: Checksum mismatch")

class ValidationService:
    def __init__(self, source_connector: DatabaseConnector, target_connector: DatabaseConnector):
        self.source = source_connector
        self.target = target_connector

    def validate_migration(self, tables: List[Table]) -> ValidationReport:
        report = ValidationReport()

        for table in tables:
            try:
                # Row counts
                source_count = self.source.count_rows(table.name)
                target_count = self.target.count_rows(table.name)
                report.add_count_check(table.name, source_count, target_count)

                # Checksum sample (simplified)
                if table.primary_key:
                    source_rows = self.source.fetch_sample_rows(table.name, table.primary_key, 1000)
                    target_rows = self.target.fetch_sample_rows(table.name, table.primary_key, 1000)

                    # Normalize rows to list of values
                    source_vals = [tuple(r.values()) if isinstance(r, dict) else tuple(r) for r in source_rows]
                    target_vals = [tuple(r.values()) if isinstance(r, dict) else tuple(r) for r in target_rows]

                    # Hash
                    source_hash = hashlib.md5(str(source_vals).encode()).hexdigest()
                    target_hash = hashlib.md5(str(target_vals).encode()).hexdigest()

                    report.add_checksum(table.name, source_hash == target_hash)
            except Exception as e:
                logger.error("validation_error", table=table.name, error=str(e))
                report.errors.append(f"Validation error for {table.name}: {str(e)}")
                report.success = False

        return report
