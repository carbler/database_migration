import pytest
from unittest.mock import MagicMock, patch
from src.application.services.migration_service import MigrationService
from src.core.domain.entities import Table, Column
from src.infrastructure.config.settings import Settings
from src.core.domain.value_objects import ConnectionConfig, DatabaseType

@pytest.fixture
def mock_settings(monkeypatch):
    monkeypatch.setattr(Settings, 'SOURCE_DB_TYPE', 'mysql')
    monkeypatch.setattr(Settings, 'TARGET_DB_TYPE', 'mysql')
    monkeypatch.setattr(Settings, 'BATCH_SIZE', 10)
    monkeypatch.setattr(Settings, 'MAX_WORKERS', 1)
    monkeypatch.setattr(Settings, 'ENABLE_VALIDATION', False)
    # Also patch connection methods
    monkeypatch.setattr(Settings, 'get_source_config', lambda: ConnectionConfig(db_type='mysql', host='h', port=1, database='d', user='u', password='p'))
    monkeypatch.setattr(Settings, 'get_target_config', lambda: ConnectionConfig(db_type='mysql', host='h', port=1, database='d', user='u', password='p'))

@patch('src.application.services.migration_service.ConnectorFactory')
def test_full_migration_flow(mock_factory, mock_settings):
    # Setup mocks
    source_connector = MagicMock()
    target_connector = MagicMock()

    # We need separate mocks for main thread and worker thread because logic creates new instances
    # But side_effect works sequentially.
    # Main thread: connect source, connect target.
    # Worker thread: connect source, connect target.
    # Total 4 connects.

    # ConnectorFactory.create_connector returns a NEW instance each call.
    # But we can return the same mock for simplicity if we want to verify calls on it, OR list of mocks.
    # Let's use list of mocks to be precise.

    main_source = MagicMock()
    main_target = MagicMock()
    worker_source = MagicMock()
    worker_target = MagicMock()

    mock_factory.create_connector.side_effect = [main_source, main_target, worker_source, worker_target]

    # Tables setup on MAIN source
    table = Table(name='users', columns=[Column('id', 'int'), Column('name', 'varchar')])
    main_source.get_tables.return_value = [table]

    # Worker source behavior
    worker_source.count_rows.return_value = 20
    # fetch_data yields batches
    worker_source.fetch_data.return_value = iter([[(1, 'Alice')], [(2, 'Bob')]])

    service = MigrationService()
    service.migrate()

    # Verification

    # 1. Main connection
    main_source.connect.assert_called_once()
    main_target.connect.assert_called_once()

    # 2. Get Tables
    main_source.get_tables.assert_called_once()

    # 3. Schema Creation
    main_target.create_table.assert_called_with(table)

    # 4. Worker connection
    worker_source.connect.assert_called_once()
    worker_target.connect.assert_called_once()

    # 5. Disable FKs in Worker
    worker_target.disable_foreign_keys.assert_called_once()

    # 6. Data Fetch
    worker_source.fetch_data.assert_called_with('users', 10)

    # 7. Data Insert (Resolve)
    # Strategy calls insert_data on target
    assert worker_target.insert_data.call_count == 2

    # 8. Enable FKs in Main
    main_target.enable_foreign_keys.assert_called_once()

    # 9. Disconnect
    main_source.disconnect.assert_called_once()
    main_target.disconnect.assert_called_once()
    worker_source.disconnect.assert_called_once()
    worker_target.disconnect.assert_called_once()
