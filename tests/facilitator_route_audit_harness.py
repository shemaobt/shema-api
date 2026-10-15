"""ENG-1651 — one walker for every audit that reads the mounted facilitator routes.

`test_facilitator_scope_audit.py` and `test_the_consultant_reads_every_team_and_writes_nothing.py`
each keep a hand-written table of facilitator routes, and each table is only as complete as the
last person who remembered to extend it. A table is checked against the routes the application
mounts, and the routes come from here, so a fix to how they are found reaches every table at
once instead of drifting between two copies.
"""

from __future__ import annotations

from fastapi.dependencies.utils import get_flat_dependant


def _dependency_calls(dependant) -> set:
    found = {dependant.call}
    for sub in dependant.dependencies:
        found |= _dependency_calls(sub)
    return found


def _mounted() -> list:
    from app.api.facilitator._deps import facilitator_role, reader_role
    from app.main import app

    gates = {facilitator_role.dependency, reader_role.dependency}
    found = []
    for route in app.routes:
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        calls = {getattr(c, "dependency", c) for c in _dependency_calls(dependant)}
        if gates & calls:
            found.append(route)
    return found


def facilitator_routes() -> list[tuple[str, str]]:
    """Every mounted route behind the facilitator or the reader gate, as (method, path).

    Derived from the gate objects in each route's dependency tree rather than from the path,
    because `/facilitator` in a path is a naming convention and this is not. A route added
    to either family is covered here the moment it is mounted.
    """
    found = []
    for route in _mounted():
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            found.append((method, route.path))
    return sorted(found)


def template_of(method: str, url: str) -> str | None:
    """The mounted path a concrete url is an instance of, or None when no route answers it."""
    for route in _mounted():
        if method in route.methods and route.path_regex.match(url):
            return route.path
    return None


def names_read_by(route) -> set[str]:
    flat = get_flat_dependant(route.dependant)
    return {p.name for p in flat.path_params + flat.query_params}


def parameters_of(method: str, path: str) -> set[str]:
    """The names a mounted route reads from its path and its query string."""
    for route in _mounted():
        if method in route.methods and route.path == path:
            return names_read_by(route)
    return set()
