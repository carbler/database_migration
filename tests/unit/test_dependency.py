"""Tests for dependency graph and topological sort."""

from db_clone.engine.dependency import topological_sort
from db_clone.models import DbObject, ObjectType


class TestTopologicalSort:
    def test_empty(self):
        assert topological_sort([]) == []

    def test_no_dependencies(self):
        objs = [
            DbObject(name="a", schema="s", object_type=ObjectType.TABLE),
            DbObject(name="b", schema="s", object_type=ObjectType.TABLE),
        ]
        result = topological_sort(objs)
        assert len(result) == 2

    def test_linear_dependency(self):
        a = DbObject(name="a", schema="s", object_type=ObjectType.TABLE)
        b = DbObject(name="b", schema="s", object_type=ObjectType.INDEX,
                     dependencies=["s.a"])
        result = topological_sort([b, a])
        names = [o.name for o in result]
        assert names.index("a") < names.index("b")

    def test_diamond_dependency(self):
        a = DbObject(name="a", schema="s", object_type=ObjectType.TABLE)
        b = DbObject(name="b", schema="s", object_type=ObjectType.TABLE,
                     dependencies=["s.a"])
        c = DbObject(name="c", schema="s", object_type=ObjectType.TABLE,
                     dependencies=["s.a"])
        d = DbObject(name="d", schema="s", object_type=ObjectType.TABLE,
                     dependencies=["s.b", "s.c"])
        result = topological_sort([d, c, b, a])
        names = [o.name for o in result]
        assert names.index("a") < names.index("b")
        assert names.index("a") < names.index("c")
        assert names.index("b") < names.index("d")
        assert names.index("c") < names.index("d")

    def test_cycle_still_returns_all(self):
        a = DbObject(name="a", schema="s", object_type=ObjectType.TABLE,
                     dependencies=["s.b"])
        b = DbObject(name="b", schema="s", object_type=ObjectType.TABLE,
                     dependencies=["s.a"])
        result = topological_sort([a, b])
        assert len(result) == 2

    def test_external_dependency_ignored(self):
        """Dependencies on objects not in the input list are ignored."""
        a = DbObject(name="a", schema="s", object_type=ObjectType.INDEX,
                     dependencies=["s.nonexistent"])
        result = topological_sort([a])
        assert len(result) == 1
