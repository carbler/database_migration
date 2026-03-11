"""Tests for data transfer module."""

from unittest.mock import MagicMock, call, patch

import pytest

from db_clone.engine.data_transfer import DataTransfer
from db_clone.models import ObjectStatus, PhaseStatus, TableInfo


@pytest.fixture
def source():
    s = MagicMock()
    s.get_columns.return_value = ["id", "name", "email"]
    return s


@pytest.fixture
def target():
    return MagicMock()


@pytest.fixture
def transfer(source, target):
    return DataTransfer(source, target, batch_size=100)


class TestDataTransfer:
    def test_transfer_empty_table(self, transfer, source, target):
        source.read_rows.return_value = iter([])
        info = TableInfo(name="empty", schema="public", row_count=0)
        status = transfer.transfer_table(info)
        assert status.status == PhaseStatus.COMPLETED
        assert status.rows_copied == 0

    def test_transfer_single_batch(self, transfer, source, target):
        rows = [(1, "Alice", "a@b.com"), (2, "Bob", "b@b.com")]
        source.read_rows.return_value = iter([rows])
        target.insert_rows.return_value = 2

        info = TableInfo(name="users", schema="public", row_count=2)
        status = transfer.transfer_table(info)

        assert status.status == PhaseStatus.COMPLETED
        assert status.rows_copied == 2
        target.insert_rows.assert_called_once()
        target.update_sequences.assert_called_once_with("public", "users")

    def test_transfer_multiple_batches(self, transfer, source, target):
        batch1 = [(i,) for i in range(100)]
        batch2 = [(i,) for i in range(100, 150)]
        source.read_rows.return_value = iter([batch1, batch2])
        target.insert_rows.side_effect = [100, 50]

        info = TableInfo(name="big", schema="public", row_count=150)
        status = transfer.transfer_table(info)

        assert status.status == PhaseStatus.COMPLETED
        assert status.rows_copied == 150
        assert target.insert_rows.call_count == 2

    def test_resume_with_offset(self, transfer, source, target):
        rows = [(101, "data")]
        source.read_rows.return_value = iter([rows])
        target.insert_rows.return_value = 1

        info = TableInfo(name="users", schema="public", row_count=200)
        existing = ObjectStatus(status=PhaseStatus.IN_PROGRESS, rows_copied=100)
        status = transfer.transfer_table(info, existing)

        source.read_rows.assert_called_with("public", "users", 100, 100)
        assert status.rows_copied == 101

    def test_on_batch_callback(self, transfer, source, target):
        rows = [(1,), (2,)]
        source.read_rows.return_value = iter([rows])
        target.insert_rows.return_value = 2
        callback = MagicMock()

        info = TableInfo(name="t", schema="s", row_count=2)
        transfer.transfer_table(info, on_batch=callback)

        callback.assert_called_once_with(2)

    def test_interrupt(self, transfer, source, target):
        batch1 = [(1,)]
        batch2 = [(2,)]
        source.read_rows.return_value = iter([batch1, batch2])
        target.insert_rows.return_value = 1

        # Interrupt after first batch
        def interrupt_after_first(*args):
            transfer.interrupt()
            return 1
        target.insert_rows.side_effect = interrupt_after_first

        info = TableInfo(name="t", schema="s", row_count=2)
        status = transfer.transfer_table(info)

        assert status.status == PhaseStatus.IN_PROGRESS
        assert status.rows_copied == 1

    def test_error_with_retry(self, transfer, source, target):
        rows = [(1,)]
        # First attempt fails, retry succeeds
        source.read_rows.side_effect = [
            iter([]),  # Will be replaced below
            iter([rows]),
        ]
        # Override to simulate error on first read
        call_count = 0
        def read_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("connection lost")
            return iter([rows])
        source.read_rows.side_effect = read_side_effect
        target.insert_rows.return_value = 1

        source.get_columns.return_value = ["id"]
        info = TableInfo(name="t", schema="s", row_count=1)
        status = transfer.transfer_table(info)

        assert status.status == PhaseStatus.COMPLETED

    def test_no_columns(self, transfer, source, target):
        source.get_columns.return_value = []
        info = TableInfo(name="empty", schema="public", row_count=0)
        status = transfer.transfer_table(info)
        assert status.status == PhaseStatus.COMPLETED
