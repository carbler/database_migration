"""Tests for data models."""

from db_clone.models import (
    PHASE_ORDER,
    ConflictStrategy,
    DbObject,
    DbType,
    MigrationResult,
    ObjectStatus,
    ObjectType,
    PhaseState,
    PhaseStatus,
    TableInfo,
)


class TestDbObject:
    def test_full_name(self):
        obj = DbObject(name="users", schema="public", object_type=ObjectType.TABLE)
        assert obj.full_name == "public.users"

    def test_default_values(self):
        obj = DbObject(name="x", schema="s", object_type=ObjectType.VIEW)
        assert obj.definition == ""
        assert obj.dependencies == []


class TestTableInfo:
    def test_full_name(self):
        t = TableInfo(name="orders", schema="public")
        assert t.full_name == "public.orders"

    def test_defaults(self):
        t = TableInfo(name="t", schema="s")
        assert t.row_count == 0
        assert t.primary_key == []


class TestPhaseOrder:
    def test_all_phases_present(self):
        assert len(PHASE_ORDER) == 11

    def test_schemas_first(self):
        assert PHASE_ORDER[0] == ObjectType.SCHEMA

    def test_data_after_tables(self):
        table_idx = PHASE_ORDER.index(ObjectType.TABLE)
        data_idx = PHASE_ORDER.index(ObjectType.DATA)
        assert data_idx > table_idx

    def test_fk_after_data(self):
        data_idx = PHASE_ORDER.index(ObjectType.DATA)
        fk_idx = PHASE_ORDER.index(ObjectType.FOREIGN_KEY)
        assert fk_idx > data_idx

    def test_triggers_last(self):
        assert PHASE_ORDER[-1] == ObjectType.TRIGGER


class TestMigrationResult:
    def test_defaults(self):
        r = MigrationResult()
        assert r.success is True
        assert r.errors == []
        assert r.rows_copied == 0


class TestEnums:
    def test_db_types(self):
        assert DbType.POSTGRESQL.value == "postgresql"
        assert DbType.MYSQL.value == "mysql"

    def test_conflict_strategies(self):
        assert ConflictStrategy.FAIL.value == "fail"
        assert ConflictStrategy.OVERWRITE.value == "overwrite"
        assert ConflictStrategy.SKIP.value == "skip"

    def test_phase_statuses(self):
        assert PhaseStatus.PENDING.value == "pending"
        assert PhaseStatus.COMPLETED.value == "completed"
