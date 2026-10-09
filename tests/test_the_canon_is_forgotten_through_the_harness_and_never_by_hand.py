"""ENG-1509 — a case that swaps the canon forgets it through the harness, and never by hand.

A fixture that clears two of the loader's caches by hand has named two of sixteen, and the
fourteen it left alone keep whatever the made-up book put in them. The one list lives in
`tests/canon_harness.py`, where a cache the loader gains is added once and a test is red until
it is.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests.canon_harness import the_caches_the_loader_holds

TESTS = Path(__file__).resolve().parent


def _what_a_module_clears_and_names(module: Path) -> tuple[list[int], set[str]]:
    tree = ast.parse(module.read_text(encoding="utf-8"))
    cleared = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "cache_clear"
    ]
    named: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            named.add(node.attr)
        elif isinstance(node, ast.Name):
            named.add(node.id)
        elif isinstance(node, ast.ImportFrom):
            named.update(alias.name for alias in node.names)
    return cleared, named


def test_no_test_clears_a_cache_of_the_canon_by_hand() -> None:
    canon_caches = {name for name, _ in the_caches_the_loader_holds()}
    by_hand: list[str] = []
    of_something_else: list[str] = []
    for module in sorted(TESTS.rglob("*.py")):
        if module.name == "canon_harness.py":
            continue
        cleared, named = _what_a_module_clears_and_names(module)
        where = [f"{module.relative_to(TESTS)}:{line}" for line in cleared]
        (by_hand if named & canon_caches else of_something_else).extend(where)

    assert of_something_else, "no clear of any cache was read: the detector is what is broken"
    assert by_hand == [], "the canon is forgotten through canon_harness.forget_the_canon"
