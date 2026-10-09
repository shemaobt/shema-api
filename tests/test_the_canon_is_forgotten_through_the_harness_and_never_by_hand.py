"""ENG-1509 — a case that swaps the canon forgets it through the harness, and never by hand.

A fixture that clears two of the loader's caches by hand has named two of sixteen, and the
fourteen it left alone keep whatever the made-up book put in them. The one list lives in
`tests/canon_harness.py`, where a cache the loader gains is added once and a test is red until
it is.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.canon_harness import the_caches_the_loader_holds

TESTS = Path(__file__).resolve().parent


def _names_in(expression: ast.AST) -> set[str]:
    return {
        node.attr if isinstance(node, ast.Attribute) else node.id
        for node in ast.walk(expression)
        if isinstance(node, ast.Attribute | ast.Name)
    }


def _the_clears_in(module: Path, canon_caches: set[str]) -> tuple[list[int], list[int]]:
    tree = ast.parse(module.read_text(encoding="utf-8"))
    fed_by: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.For) and isinstance(node.target, ast.Name):
            fed_by.setdefault(node.target.id, set()).update(_names_in(node.iter))
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    fed_by.setdefault(target.id, set()).update(_names_in(node.value))
    of_the_canon: list[int] = []
    of_something_else: list[int] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "cache_clear"
        ):
            cleared = _names_in(node.func.value)
            for name in list(cleared):
                cleared |= fed_by.get(name, set())
            (of_the_canon if cleared & canon_caches else of_something_else).append(node.lineno)
    return of_the_canon, of_something_else


CLEARS_ONE_THING_AND_NAMES_ANOTHER = """\
from app.services.internalization_room import fail_safe
from app.services.internalization_room.canon.parse_map import load_map


def test_a_case() -> None:
    assert load_map("P01")
    fail_safe._sections.cache_clear()
"""

CLEARS_THE_LOADER_DIRECTLY = """\
from app.services.internalization_room.canon import parse_map


def test_a_case() -> None:
    parse_map.load_map.cache_clear()
"""

CLEARS_THROUGH_A_LOOP_VARIABLE = """\
from app.services.internalization_room.canon import book_material


def test_a_case() -> None:
    for cached in (book_material.preservation_rules, book_material._register_complete):
        cached.cache_clear()
"""


def _planted(tmp_path: Path, source: str) -> Path:
    module = tmp_path / "test_a_planted_case.py"
    module.write_text(source, encoding="utf-8")
    return module


def test_a_clear_of_another_cache_is_not_a_clear_of_the_canon_for_naming_one(
    tmp_path: Path,
) -> None:
    canon_caches = {name for name, _ in the_caches_the_loader_holds()}

    of_the_canon, of_something_else = _the_clears_in(
        _planted(tmp_path, CLEARS_ONE_THING_AND_NAMES_ANOTHER), canon_caches
    )

    assert (of_the_canon, of_something_else) == ([], [7])


@pytest.mark.parametrize(
    ("source", "line"),
    [(CLEARS_THE_LOADER_DIRECTLY, 5), (CLEARS_THROUGH_A_LOOP_VARIABLE, 6)],
    ids=["named at the clear", "named by the loop that feeds it"],
)
def test_a_clear_of_a_canon_cache_is_read_whichever_way_it_names_it(
    tmp_path: Path, source: str, line: int
) -> None:
    canon_caches = {name for name, _ in the_caches_the_loader_holds()}

    of_the_canon, of_something_else = _the_clears_in(_planted(tmp_path, source), canon_caches)

    assert (of_the_canon, of_something_else) == ([line], [])


def test_no_test_clears_a_cache_of_the_canon_by_hand() -> None:
    canon_caches = {name for name, _ in the_caches_the_loader_holds()}
    by_hand: list[str] = []
    of_something_else: list[str] = []
    for module in sorted(TESTS.rglob("*.py")):
        if module.name == "canon_harness.py":
            continue
        of_the_canon, of_something_other = _the_clears_in(module, canon_caches)
        by_hand.extend(f"{module.relative_to(TESTS)}:{line}" for line in of_the_canon)
        of_something_else.extend(
            f"{module.relative_to(TESTS)}:{line}" for line in of_something_other
        )

    assert of_something_else, "no clear of any cache was read: the detector is what is broken"
    assert by_hand == [], "the canon is forgotten through canon_harness.forget_the_canon"
