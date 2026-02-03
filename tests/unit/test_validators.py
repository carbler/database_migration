import pytest
from unittest.mock import MagicMock
from src.application.services.validation_service import ValidationService, ValidationReport
from src.core.domain.interfaces import DatabaseConnector
from src.core.domain.entities import Table

@pytest.fixture
def mock_connectors():
    source = MagicMock(spec=DatabaseConnector)
    target = MagicMock(spec=DatabaseConnector)
    return source, target

def test_validation_success(mock_connectors):
    source, target = mock_connectors
    service = ValidationService(source, target)

    table = Table(name='users')

    source.count_rows.return_value = 100
    target.count_rows.return_value = 100

    report = service.validate_migration([table])

    assert report.success
    assert not report.errors
    assert report.row_counts['users']['source'] == 100
    assert report.row_counts['users']['target'] == 100

def test_validation_failure(mock_connectors):
    source, target = mock_connectors
    service = ValidationService(source, target)

    table = Table(name='users')

    source.count_rows.return_value = 100
    target.count_rows.return_value = 99

    report = service.validate_migration([table])

    assert not report.success
    assert len(report.errors) == 1
    assert "Row count mismatch" in report.errors[0]
