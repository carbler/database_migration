import pytest
from src.infrastructure.config.settings import Settings

@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("SOURCE_DB_TYPE", "mysql")
    monkeypatch.setenv("TARGET_DB_TYPE", "mysql")
    monkeypatch.setenv("BATCH_SIZE", "10")
    monkeypatch.setenv("MAX_WORKERS", "1")
    monkeypatch.setenv("ENABLE_VALIDATION", "false")
