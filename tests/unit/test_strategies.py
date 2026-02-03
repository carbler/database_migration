import pytest
from unittest.mock import MagicMock
from src.application.strategies.fail_strategy import FailStrategy
from src.application.strategies.overwrite_strategy import OverwriteStrategy
from src.application.strategies.skip_strategy import SkipStrategy
from src.application.strategies.merge_strategy import MergeStrategy
from src.core.domain.interfaces import DatabaseConnector

@pytest.fixture
def mock_connector():
    return MagicMock(spec=DatabaseConnector)

def test_fail_strategy_resolve(mock_connector):
    strategy = FailStrategy()
    strategy.resolve(mock_connector, 'users', [], ['id'])
    mock_connector.insert_data.assert_called_with('users', [], ['id'], on_conflict='raise', primary_key=None)

def test_overwrite_strategy_prepare(mock_connector):
    strategy = OverwriteStrategy()
    strategy.prepare(mock_connector, 'users')
    mock_connector.truncate_table.assert_called_with('users')

def test_overwrite_strategy_resolve(mock_connector):
    strategy = OverwriteStrategy()
    strategy.resolve(mock_connector, 'users', [], ['id'])
    mock_connector.insert_data.assert_called_with('users', [], ['id'], on_conflict='raise', primary_key=None)

def test_skip_strategy_resolve(mock_connector):
    strategy = SkipStrategy()
    strategy.resolve(mock_connector, 'users', [], ['id'])
    mock_connector.insert_data.assert_called_with('users', [], ['id'], on_conflict='ignore', primary_key=None)

def test_merge_strategy_resolve(mock_connector):
    strategy = MergeStrategy()
    strategy.resolve(mock_connector, 'users', [], ['id'])
    mock_connector.insert_data.assert_called_with('users', [], ['id'], on_conflict='update', primary_key=None)
