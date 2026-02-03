from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Set
import structlog
import time
from src.core.domain.interfaces import DatabaseConnector, MigrationObserver
from src.core.domain.entities import Table
from src.infrastructure.connectors.connector_factory import ConnectorFactory
from src.core.domain.value_objects import ConnectionConfig, DatabaseType
from src.infrastructure.config.settings import Settings
from src.application.services.conflict_resolver import ConflictResolver
from src.application.services.validation_service import ValidationService
import os

logger = structlog.get_logger()

class MigrationService:
    def __init__(self, observer: Optional[MigrationObserver] = None):
        self.observer = observer
        self.source_config = Settings.get_source_config()
        self.target_config = Settings.get_target_config()
        self.batch_size = Settings.BATCH_SIZE
        self.max_workers = Settings.MAX_WORKERS
        self.strategy_name = Settings.CONFLICT_STRATEGY
        self.strategy = ConflictResolver(self.strategy_name).get_strategy()

    def migrate(self):
        # 1. Validate DB Types (No Cross-DB)
        if self.source_config.db_type != self.target_config.db_type:
            raise ValueError("Cross-database migrations not supported")

        # Main connector for schema operations
        main_source = ConnectorFactory.create_connector(self.source_config)
        main_target = ConnectorFactory.create_connector(self.target_config)

        try:
            main_source.connect()
            main_target.connect()

            # 2. Get Tables and Sort
            logger.info("Fetching schema...")
            tables = main_source.get_tables()
            sorted_tables = self._topological_sort(tables)
            logger.info(f"Found {len(tables)} tables to migrate.")

            if self.observer:
                self.observer.on_start(len(sorted_tables))

            # 3. Migrate Schema (Sequential)
            logger.info("Migrating schema...")
            # Disable FKs on main connection for schema operations if needed (e.g. drop table order)
            main_target.disable_foreign_keys()

            for table in sorted_tables:
                self._migrate_schema(main_target, table)

            # 4. Migrate Data (Parallel)
            logger.info("Migrating data...")
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self._migrate_table_data, table): table
                    for table in sorted_tables
                }

                for future in as_completed(futures):
                    table = futures[future]
                    try:
                        future.result()
                    except Exception as e:
                        logger.error("table_migration_failed", table=table.name, error=str(e))
                        if self.observer:
                            self.observer.on_error(table.name, str(e))
                        # Depending on strategy, we might abort. For now log.

            # 5. Enable FKs (on main connection, verifies integrity if global check, but session based won't verify)
            # To verify integrity, we need to run a check or rely on validation.
            main_target.enable_foreign_keys()

            # 6. Extensions Documentation (if source is Postgres)
            if self.source_config.db_type == DatabaseType.POSTGRESQL:
                self._document_extensions(main_source)

            # 7. Validation
            if Settings.ENABLE_VALIDATION:
                logger.info("Validating migration...")
                validator = ValidationService(main_source, main_target)
                report = validator.validate_migration(tables)
                if self.observer:
                    self.observer.on_complete(report)
            else:
                if self.observer:
                    self.observer.on_complete(None)

        finally:
            main_source.disconnect()
            main_target.disconnect()

    def _migrate_schema(self, target: DatabaseConnector, table: Table):
        if self.strategy_name == 'overwrite':
             target.drop_table(table.name)

        # Create table
        # If table exists and not overwrite, create_table usually fails or does nothing if IF NOT EXISTS used.
        # But our connectors create_table logic might vary.
        # Assuming create_table handles existence gracefully or fails.
        # If it fails, we catch it?
        try:
            target.create_table(table)
        except Exception as e:
            logger.warning(f"Schema creation for {table.name} skipped/failed: {e}")

        # Prepare (truncate)
        if self.strategy_name == 'overwrite':
             target.truncate_table(table.name)

        # Other strategies don't need prepare usually.
        self.strategy.prepare(target, table.name)


    def _migrate_table_data(self, table: Table):
        # Worker function: creates its own connections
        source = ConnectorFactory.create_connector(self.source_config)
        target = ConnectorFactory.create_connector(self.target_config)

        start_time = time.time()
        try:
            source.connect()
            target.connect()

            # Disable FK checks for this session to allow inserting data without order constraints (if parallel)
            # Even with topological sort, circular dependencies might exist.
            target.disable_foreign_keys()

            # Fetch total rows for progress tracking
            # This is extra query but needed for progress bar
            total_rows = source.count_rows(table.name)
            if self.observer:
                self.observer.on_table_start(table.name, total_rows)

            count = 0
            columns = [col.name for col in table.columns]

            # Fetch and Insert
            # Note: fetch_data yields batches
            for batch in source.fetch_data(table.name, self.batch_size):
                if not batch:
                    break

                # Resolve conflict / Insert
                self.strategy.resolve(target, table.name, batch, columns, table.primary_key)

                count += len(batch)
                if self.observer:
                    self.observer.on_batch_processed(table.name, count)

            duration = time.time() - start_time
            if self.observer:
                self.observer.on_table_complete(table.name, duration)

        finally:
            source.disconnect()
            target.disconnect()

    def _document_extensions(self, connector: DatabaseConnector):
        try:
            extensions = connector.get_installed_extensions()
            if extensions:
                with open("EXTENSIONS.md", "w") as f:
                    f.write("# PostgreSQL Extensions\n\n")
                    f.write("The following extensions were detected in the source database:\n\n")
                    for ext in extensions:
                        f.write(f"- {ext}\n")
                logger.info("Documented PostgreSQL extensions in EXTENSIONS.md")
        except Exception as e:
            logger.warning(f"Failed to document extensions: {e}")

    def _topological_sort(self, tables: List[Table]) -> List[Table]:
        # Sort tables by FK dependencies
        table_map = {t.name: t for t in tables}
        dependencies = {t.name: set() for t in tables}

        for table in tables:
            for fk in table.foreign_keys:
                # Only if referenced table is in the list of tables we are migrating
                if fk.referenced_table in table_map:
                    dependencies[table.name].add(fk.referenced_table)

        sorted_list = []
        visited = set()
        temp_visited = set()

        def visit(name):
            if name in temp_visited:
                # Cycle detected (circular dependency)
                # Just add it and continue, FK checks disabled anyway
                return
            if name in visited:
                return

            temp_visited.add(name)

            # Visit dependencies first
            for dep in dependencies.get(name, []):
                visit(dep)

            temp_visited.remove(name)
            visited.add(name)
            if name in table_map:
                sorted_list.append(table_map[name])

        for table in tables:
            visit(table.name)

        return sorted_list
