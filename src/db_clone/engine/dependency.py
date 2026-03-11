"""Dependency graph and topological sort for migration ordering."""

from __future__ import annotations

from collections import defaultdict, deque

from db_clone.logging_config import get_logger
from db_clone.models import DbObject

log = get_logger(__name__)


def topological_sort(objects: list[DbObject]) -> list[DbObject]:
    """Sort objects respecting dependencies (Kahn's algorithm).

    Objects without dependencies come first. If there's a cycle,
    remaining objects are appended at the end with a warning.
    """
    if not objects:
        return []

    # Build adjacency and in-degree
    name_to_obj: dict[str, DbObject] = {}
    for obj in objects:
        name_to_obj[obj.full_name] = obj

    in_degree: dict[str, int] = defaultdict(int)
    graph: dict[str, list[str]] = defaultdict(list)

    for obj in objects:
        fn = obj.full_name
        if fn not in in_degree:
            in_degree[fn] = 0
        for dep in obj.dependencies:
            if dep in name_to_obj:
                graph[dep].append(fn)
                in_degree[fn] += 1

    # Kahn's
    queue: deque[str] = deque()
    for fn, deg in in_degree.items():
        if deg == 0:
            queue.append(fn)

    sorted_names: list[str] = []
    while queue:
        node = queue.popleft()
        sorted_names.append(node)
        for neighbor in graph[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # Handle cycles
    remaining = set(name_to_obj.keys()) - set(sorted_names)
    if remaining:
        log.warning("dependency_cycle_detected", objects=list(remaining))
        sorted_names.extend(remaining)

    return [name_to_obj[n] for n in sorted_names if n in name_to_obj]
