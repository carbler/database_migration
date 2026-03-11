"""Streaming batched data transfer between databases."""

from __future__ import annotations

from db_clone.connectors.base import BaseConnector
from db_clone.logging_config import get_logger
from db_clone.models import ObjectStatus, PhaseStatus, TableInfo

log = get_logger(__name__)


class DataTransfer:
    """Handles streaming data transfer between source and target."""

    def __init__(
        self,
        source: BaseConnector,
        target: BaseConnector,
        batch_size: int = 5000,
    ) -> None:
        self.source = source
        self.target = target
        self.batch_size = batch_size
        self._interrupted = False

    def interrupt(self) -> None:
        """Signal to stop after current batch."""
        self._interrupted = True

    def transfer_table(
        self,
        table_info: TableInfo,
        status: ObjectStatus | None = None,
        on_batch: callable | None = None,
    ) -> ObjectStatus:
        """Transfer all data for a single table.

        Args:
            table_info: Table metadata.
            status: Existing status for resume (uses rows_copied as offset).
            on_batch: Callback(rows_copied) after each batch for checkpoint/progress.

        Returns:
            Updated ObjectStatus.
        """
        if status is None:
            status = ObjectStatus()

        schema = table_info.schema
        table = table_info.name
        offset = status.rows_copied
        status.total_rows = table_info.row_count
        status.status = PhaseStatus.IN_PROGRESS

        columns = self.source.get_columns(schema, table)
        if not columns:
            log.warning("no_columns", table=table_info.full_name)
            status.status = PhaseStatus.COMPLETED
            return status

        log.info(
            "data_transfer_start",
            table=table_info.full_name,
            estimated_rows=table_info.row_count,
            offset=offset,
        )

        try:
            for batch in self.source.read_rows(schema, table, self.batch_size, offset):
                if self._interrupted:
                    log.info("data_transfer_interrupted", table=table_info.full_name,
                             rows_copied=status.rows_copied)
                    return status

                inserted = self.target.insert_rows(schema, table, columns, batch)
                status.rows_copied += inserted

                if on_batch:
                    on_batch(status.rows_copied)

            # Update sequences after full transfer
            self.target.update_sequences(schema, table)
            status.status = PhaseStatus.COMPLETED
            log.info("data_transfer_complete", table=table_info.full_name,
                     rows=status.rows_copied)

        except Exception as e:
            log.error("data_transfer_error", table=table_info.full_name,
                      error=str(e), rows_copied=status.rows_copied)
            status.status = PhaseStatus.FAILED
            status.error = str(e)
            # Retry once
            try:
                log.info("data_transfer_retry", table=table_info.full_name)
                for batch in self.source.read_rows(
                    schema, table, self.batch_size, status.rows_copied
                ):
                    if self._interrupted:
                        return status
                    inserted = self.target.insert_rows(schema, table, columns, batch)
                    status.rows_copied += inserted
                    if on_batch:
                        on_batch(status.rows_copied)

                self.target.update_sequences(schema, table)
                status.status = PhaseStatus.COMPLETED
                status.error = None
            except Exception as retry_err:
                log.error("data_transfer_retry_failed", table=table_info.full_name,
                          error=str(retry_err))
                status.status = PhaseStatus.FAILED
                status.error = str(retry_err)

        return status
