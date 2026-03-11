"""Integration test fixtures using testcontainers."""

import pytest

# Mark all tests in this directory as integration
pytestmark = pytest.mark.integration


def pytest_collection_modifyitems(config, items):
    """Skip integration tests unless --run-integration is passed."""
    if not config.getoption("--run-integration", default=False):
        skip = pytest.mark.skip(reason="need --run-integration option to run")
        for item in items:
            if "integration" in str(item.fspath):
                item.add_marker(skip)


def pytest_addoption(parser):
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests (requires Docker).",
    )
