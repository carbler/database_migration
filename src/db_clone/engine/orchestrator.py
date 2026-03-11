"""Main orchestrator that coordinates all migration phases."""

from __future__ import annotations

import signal
import time
from typing import Any

from db_clone.checkpoint import CheckpointManager
from db_clone.config import Settings
from db_clone.connectors import create_connector
from db_clone.connectors.base import BaseConnector
from db_clone.engine.copier import ObjectCopier
from db_clone.engine.data_transfer import DataTransfer
from db_clone.engine.dependency import topological_sort
from db_clone.engine.discovery import Discovery
from db_clone.logging_config import get_logger
from db_clone.models import (
    PHASE_ORDER,
    DbObject,
    MigrationResult,
    ObjectStatus,
    ObjectType,
    PhaseStatus,
)
from db_clone.progress import (
    console,
    create_data_progress,
    create_phase_progress,
    show_migration_summary,
)

log = get_logger(__name__)


class Orchestrator:
    """Coordinates the full database cloning process."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.checkpoint = CheckpointManager()
        self._interrupted = False
        self._data_transfer: DataTransfer | None = None

    def run(self) -> MigrationResult:
        """Execute the full migration."""
        start_time = time.time()
        result = MigrationResult()

        # Signal handling
        original_sigint = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, self._handle_sigint)

        try:
            result = self._run_migration()
        except Exception as e:
            log.error("migration_fatal_error", error=str(e))
            result.success = False
            result.errors.append(str(e))
        finally:
            signal.signal(signal.SIGINT, original_sigint)
            result.duration_seconds = time.time() - start_time

        show_migration_summary(result)
        return result

    def _run_migration(self) -> MigrationResult:
        result = MigrationResult()

        # Handle resume
        if self.settings.resume and self.checkpoint.load():
            if not self.checkpoint.matches_migration(
                self.settings.source_url, self.settings.target_url
            ):
                console.print("[yellow]Checkpoint doesn't match current URLs. Starting fresh.[/]")
                self.checkpoint.initialize(
                    self.settings.source_url, self.settings.target_url
                )
            else:
                console.print("[green]Resuming from checkpoint...[/]")
        else:
            self.checkpoint.initialize(
                self.settings.source_url, self.settings.target_url
            )

        source = create_connector(self.settings.source_url)
        target = create_connector(self.settings.target_url)

        with source, target:
            console.print("[bold]Connecting to databases...[/]")
            if not source.test_connection():
                raise ConnectionError("Cannot connect to source database")
            if not target.test_connection():
                raise ConnectionError("Cannot connect to target database")

            # Discovery
            console.print("[bold]Discovering source objects...[/]")
            discovery = Discovery(source)
            all_objects = discovery.discover(
                include_tables=self.settings.include_table_list or None,
                exclude_tables=self.settings.exclude_table_list or None,
            )

            # Setup components
            copier = ObjectCopier(target, self.settings.strategy)
            self._data_transfer = DataTransfer(
                source, target, self.settings.batch_size
            )

            # Determine which phases to run
            phases = self._get_phases()

            with create_phase_progress() as phase_progress:
                main_task = phase_progress.add_task(
                    "Migration", total=len(phases)
                )

                for phase in phases:
                    if self._interrupted:
                        console.print("\n[yellow]Migration interrupted. Use --resume to continue.[/]")
                        break

                    if self.checkpoint.is_phase_completed(phase):
                        phase_progress.advance(main_task)
                        result.phases_completed += 1
                        continue

                    phase_progress.update(
                        main_task, description=f"Phase: {phase.value}"
                    )

                    if phase == ObjectType.DATA:
                        phase_result = self._run_data_phase(
                            source, target, all_objects, result
                        )
                    else:
                        objects = all_objects.get(phase, [])
                        objects = topological_sort(objects)
                        phase_result = self._run_ddl_phase(
                            phase, objects, copier, result
                        )

                    if phase_result:
                        result.phases_completed += 1
                    else:
                        result.phases_failed += 1

                    phase_progress.advance(main_task)

        result.success = result.phases_failed == 0 and not self._interrupted
        return result

    def _get_phases(self) -> list[ObjectType]:
        """Determine which phases to run based on settings."""
        if self.settings.data_only:
            return [ObjectType.DATA]
        if self.settings.schema_only:
            return [p for p in PHASE_ORDER if p != ObjectType.DATA]
        return list(PHASE_ORDER)

    def _run_ddl_phase(
        self,
        phase: ObjectType,
        objects: list[DbObject],
        copier: ObjectCopier,
        result: MigrationResult,
    ) -> bool:
        """Run a DDL phase (schemas, tables, indexes, etc.)."""
        if not objects:
            self.checkpoint.set_phase_status(phase, PhaseStatus.COMPLETED)
            return True

        self.checkpoint.set_phase_status(phase, PhaseStatus.IN_PROGRESS)
        all_ok = True

        for obj in objects:
            if self._interrupted:
                return False

            if self.checkpoint.is_object_completed(phase, obj.full_name):
                result.objects_copied += 1
                continue

            status = copier.copy_object(obj)
            self.checkpoint.set_object_status(phase, obj.full_name, status)

            if status.status == PhaseStatus.COMPLETED:
                result.objects_copied += 1
            elif status.status == PhaseStatus.FAILED:
                result.objects_failed += 1
                result.errors.append(
                    f"{phase.value}/{obj.full_name}: {status.error}"
                )
                all_ok = False

        final_status = PhaseStatus.COMPLETED if all_ok else PhaseStatus.FAILED
        self.checkpoint.set_phase_status(phase, final_status)
        return all_ok

    def _run_data_phase(
        self,
        source: BaseConnector,
        target: BaseConnector,
        all_objects: dict[ObjectType, list[DbObject]],
        result: MigrationResult,
    ) -> bool:
        """Run the data transfer phase."""
        tables = all_objects.get(ObjectType.TABLE, [])
        if not tables:
            self.checkpoint.set_phase_status(ObjectType.DATA, PhaseStatus.COMPLETED)
            return True

        self.checkpoint.set_phase_status(ObjectType.DATA, PhaseStatus.IN_PROGRESS)

        # Disable FK checks during data load
        target.disable_fk_checks()
        all_ok = True

        try:
            with create_data_progress() as data_progress:
                for table_obj in tables:
                    if self._interrupted:
                        break

                    full_name = table_obj.full_name
                    if self.checkpoint.is_object_completed(ObjectType.DATA, full_name):
                        continue

                    table_info = source.get_table_info(
                        table_obj.schema, table_obj.name
                    )
                    existing_status = self.checkpoint.get_object_status(
                        ObjectType.DATA, full_name
                    )

                    task_id = data_progress.add_task(
                        full_name,
                        total=table_info.row_count or None,
                        completed=existing_status.rows_copied,
                    )

                    def on_batch(rows_copied: int, _tid=task_id, _fn=full_name) -> None:
                        data_progress.update(_tid, completed=rows_copied)
                        status = ObjectStatus(
                            status=PhaseStatus.IN_PROGRESS,
                            rows_copied=rows_copied,
                            total_rows=table_info.row_count,
                        )
                        self.checkpoint.set_object_status(
                            ObjectType.DATA, _fn, status
                        )

                    status = self._data_transfer.transfer_table(
                        table_info, existing_status, on_batch
                    )
                    self.checkpoint.set_object_status(
                        ObjectType.DATA, full_name, status
                    )

                    if status.status == PhaseStatus.COMPLETED:
                        result.objects_copied += 1
                        result.rows_copied += status.rows_copied
                        data_progress.update(task_id, completed=status.rows_copied)
                    else:
                        result.objects_failed += 1
                        all_ok = False
                        if status.error:
                            result.errors.append(
                                f"data/{full_name}: {status.error}"
                            )
        finally:
            target.enable_fk_checks()

        final_status = PhaseStatus.COMPLETED if all_ok else PhaseStatus.FAILED
        self.checkpoint.set_phase_status(ObjectType.DATA, final_status)
        return all_ok

    def _handle_sigint(self, signum: int, frame: Any) -> None:
        """Handle Ctrl+C gracefully."""
        if self._interrupted:
            # Second Ctrl+C: force exit
            raise KeyboardInterrupt
        self._interrupted = True
        if self._data_transfer:
            self._data_transfer.interrupt()
        console.print("\n[yellow]Interrupt received. Finishing current batch...[/]")
        console.print("[yellow]Press Ctrl+C again to force quit.[/]")
