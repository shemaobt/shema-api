"""ENG-1509 — a case that swaps the canon forgets it through the harness, and never by hand.

A fixture that clears two of the loader's caches by hand has named two of sixteen, and the
fourteen it left alone keep whatever the made-up book put in them. The one list lives in
`tests/canon_harness.py`, where a cache the loader gains is added once and a test is red until
it is.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator
from pathlib import Path

import pytest

from tests.canon_harness import (
    THE_CACHES_THAT_READ_NO_CANON,
    THE_CACHES_THAT_READ_THE_CANON_FROM_OUTSIDE_IT,
    the_caches_of_the_prompts,
    the_caches_the_loader_holds,
    the_names_the_prompts_are_reached_by,
)

TESTS = Path(__file__).resolve().parent
APP = TESTS.parent / "app"
THE_CANON_PACKAGE = "app.services.internalization_room.canon."


def _the_caches_the_harness_forgets() -> set[str]:
    canon = {name for name, _ in the_caches_the_loader_holds()}
    return canon | the_names_the_prompts_are_reached_by()


def _names_in(expression: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(expression):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
            if isinstance(node.value, ast.Name):
                names.add(f"{node.value.id}.{node.attr}")
    return names


def _outermost_functions(node: ast.AST) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
            yield child
        else:
            yield from _outermost_functions(child)


def _outside_every_function(node: ast.AST) -> Iterator[ast.AST]:
    for child in ast.iter_child_nodes(node):
        if not isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
            yield child
            yield from _outside_every_function(child)


def _fed_by(nodes: Iterable[ast.AST]) -> dict[str, set[str]]:
    fed_by: dict[str, set[str]] = {}
    for node in nodes:
        if isinstance(node, ast.For) and isinstance(node.target, ast.Name):
            fed_by.setdefault(node.target.id, set()).update(_names_in(node.iter))
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    fed_by.setdefault(target.id, set()).update(_names_in(node.value))
    return fed_by


def _the_clears_in(module: Path, canon_caches: set[str]) -> tuple[list[int], list[int]]:
    tree = ast.parse(module.read_text(encoding="utf-8"))
    at_the_top = list(_outside_every_function(tree))
    scopes = [(at_the_top, _fed_by(at_the_top))]
    for function in _outermost_functions(tree):
        within = list(ast.walk(function))
        scopes.append((within, _fed_by(at_the_top) | _fed_by(within)))
    of_the_canon: list[int] = []
    of_something_else: list[int] = []
    for nodes, fed_by in scopes:
        for node in nodes:
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "cache_clear"
            ):
                cleared = _names_in(node.func.value)
                for name in list(cleared):
                    cleared |= fed_by.get(name, set())
                (of_the_canon if cleared & canon_caches else of_something_else).append(node.lineno)
    return sorted(of_the_canon), sorted(of_something_else)


CLEARS_ONE_THING_AND_NAMES_ANOTHER = """\
from app.core.config import get_settings
from app.services.internalization_room.canon.parse_map import load_map


def test_a_case() -> None:
    assert load_map("P01")
    get_settings.cache_clear()
"""

A_NAME_ANOTHER_CASE_FEEDS_FROM_THE_CANON = """\
from app.core.config import get_settings
from app.services.internalization_room.canon import parse_map


def test_a_case() -> None:
    cached = parse_map.load_map
    assert cached("P01")


def test_another_case() -> None:
    cached = get_settings
    cached.cache_clear()
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

CLEARS_THROUGH_A_NAME_FED_AT_THE_TOP = """\
from app.services.internalization_room.canon import book_material

cached = book_material.preservation_rules


def test_a_case() -> None:
    cached.cache_clear()
"""

CLEARS_THROUGH_A_NAME_FED_BY_THE_CASE_AROUND_IT = """\
from app.services.internalization_room.canon import book_material


def test_a_case() -> None:
    cached = book_material.preservation_rules

    def forget() -> None:
        cached.cache_clear()

    forget()
"""

CLEARS_THE_FAIL_SAFE_SECTIONS = """\
from app.services.internalization_room import fail_safe


def test_a_case() -> None:
    fail_safe._sections.cache_clear()
"""

CLEARS_THE_FAIL_SAFE_FILE_THROUGH_AN_ALIAS = """\
from app.services.internalization_room import fail_safe


def test_a_case() -> None:
    real_loader = fail_safe.fail_safe_utterances
    real_loader.cache_clear()
"""

CLEARS_TWO_CACHES_THAT_SHARE_A_NAME = """\
from app.services.internalization_room import fail_safe, passage_lines


def test_a_case() -> None:
    passage_lines._sections.cache_clear()
    fail_safe._sections.cache_clear()
"""

CLEARS_THE_PROMPT_LOADER = """\
from app.services.internalization_room import _default_prompts


def test_a_case() -> None:
    _default_prompts.load_prompt.cache_clear()
"""


def _decorator_name(decorator: ast.expr) -> str | None:
    target = decorator.func if isinstance(decorator, ast.Call) else decorator
    if isinstance(target, ast.Attribute):
        return target.attr
    return target.id if isinstance(target, ast.Name) else None


def _unlisted_caches(root: Path, listed: set[str]) -> list[str]:
    unlisted: list[str] = []
    for module in sorted(root.rglob("*.py")):
        relative = module.relative_to(root.parent)
        dotted = ".".join(relative.with_suffix("").parts)
        for node in ast.walk(ast.parse(module.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            kinds = {_decorator_name(decorator) for decorator in node.decorator_list}
            qualified = f"{dotted}.{node.name}"
            if (
                not kinds & {"lru_cache", "cache"}
                or dotted.startswith(THE_CANON_PACKAGE)
                or qualified in listed
            ):
                continue
            unlisted.append(
                f"{relative.as_posix()}:{node.lineno} `{node.name}` is a cache the harness "
                "does not know. Ask: does it read anything under canon/, directly or "
                f'through a call? If it does, list "{qualified}" in '
                "THE_CACHES_THAT_READ_THE_CANON_FROM_OUTSIDE_IT in tests/canon_harness.py; "
                "if it does not, list it in THE_CACHES_THAT_READ_NO_CANON, in the same file."
            )
    return unlisted


A_CACHE_NOBODY_LISTED = """\
from functools import lru_cache


@lru_cache(maxsize=1)
def read_the_map_again() -> str:
    return "the map"
"""

A_CACHE_THE_LOADER_FINDS_BY_ITSELF = """\
from app.services.internalization_room.canon import kept


@kept.per_canon(maxsize=1)
def read_the_map_again() -> str:
    return "the map"
"""

A_CACHE_UNDER_THE_CANON = """\
from functools import lru_cache


@lru_cache(maxsize=1)
def read_the_map_again() -> str:
    return "the map"
"""

A_BARE_CACHE_NOBODY_LISTED = """\
import functools


@functools.cache
def read_the_map_again() -> str:
    return "the map"
"""


def _planted(tmp_path: Path, source: str) -> Path:
    module = tmp_path / "test_a_planted_case.py"
    module.write_text(source, encoding="utf-8")
    return module


def test_a_clear_of_another_cache_is_not_a_clear_of_the_canon_for_naming_one(
    tmp_path: Path,
) -> None:
    canon_caches = _the_caches_the_harness_forgets()

    of_the_canon, of_something_else = _the_clears_in(
        _planted(tmp_path, CLEARS_ONE_THING_AND_NAMES_ANOTHER), canon_caches
    )

    assert (of_the_canon, of_something_else) == ([], [7])


def test_a_name_fed_from_the_canon_in_another_case_does_not_flag_this_ones_clear(
    tmp_path: Path,
) -> None:
    canon_caches = _the_caches_the_harness_forgets()

    of_the_canon, of_something_else = _the_clears_in(
        _planted(tmp_path, A_NAME_ANOTHER_CASE_FEEDS_FROM_THE_CANON), canon_caches
    )

    assert (of_the_canon, of_something_else) == ([], [12])


@pytest.mark.parametrize(
    ("source", "line"),
    [
        (CLEARS_THE_LOADER_DIRECTLY, 5),
        (CLEARS_THROUGH_A_LOOP_VARIABLE, 6),
        (CLEARS_THROUGH_A_NAME_FED_AT_THE_TOP, 7),
        (CLEARS_THROUGH_A_NAME_FED_BY_THE_CASE_AROUND_IT, 8),
    ],
    ids=[
        "named at the clear",
        "named by the loop that feeds it",
        "named by the module that feeds it",
        "named by the case around the function that clears it",
    ],
)
def test_a_clear_of_a_canon_cache_is_read_whichever_way_it_names_it(
    tmp_path: Path, source: str, line: int
) -> None:
    canon_caches = _the_caches_the_harness_forgets()

    of_the_canon, of_something_else = _the_clears_in(_planted(tmp_path, source), canon_caches)

    assert (of_the_canon, of_something_else) == ([line], [])


@pytest.mark.parametrize(
    ("source", "line"),
    [
        (CLEARS_THE_FAIL_SAFE_SECTIONS, 5),
        (CLEARS_THE_FAIL_SAFE_FILE_THROUGH_AN_ALIAS, 6),
        (CLEARS_THE_PROMPT_LOADER, 5),
    ],
    ids=["the fail-safe sections", "the fail-safe file by an alias", "the prompt loader"],
)
def test_a_clear_of_a_prompt_cache_is_read_as_one_the_harness_owns(
    tmp_path: Path, source: str, line: int
) -> None:
    of_the_harness, of_something_else = _the_clears_in(
        _planted(tmp_path, source), _the_caches_the_harness_forgets()
    )

    assert (of_the_harness, of_something_else) == ([line], [])


def _an_app_holding(tmp_path: Path, at: str, source: str) -> Path:
    module = tmp_path / "app" / at
    module.parent.mkdir(parents=True, exist_ok=True)
    module.write_text(source, encoding="utf-8")
    return tmp_path / "app"


def test_a_cache_nobody_listed_is_reported_with_where_it_is_and_what_to_do(
    tmp_path: Path,
) -> None:
    app = _an_app_holding(tmp_path, "services/a_new_cache.py", A_CACHE_NOBODY_LISTED)

    assert _unlisted_caches(app, set()) == [
        "app/services/a_new_cache.py:5 `read_the_map_again` is a cache the harness does not "
        "know. Ask: does it read anything under canon/, directly or through a call? If it "
        'does, list "app.services.a_new_cache.read_the_map_again" in '
        "THE_CACHES_THAT_READ_THE_CANON_FROM_OUTSIDE_IT in tests/canon_harness.py; if it does "
        "not, list it in THE_CACHES_THAT_READ_NO_CANON, in the same file."
    ]


def test_a_bare_functools_cache_is_a_cache_too(tmp_path: Path) -> None:
    app = _an_app_holding(tmp_path, "services/a_new_cache.py", A_BARE_CACHE_NOBODY_LISTED)

    assert len(_unlisted_caches(app, set())) == 1


def test_a_cache_that_is_listed_by_name_is_not_reported(tmp_path: Path) -> None:
    app = _an_app_holding(tmp_path, "services/a_new_cache.py", A_CACHE_NOBODY_LISTED)

    assert _unlisted_caches(app, {"app.services.a_new_cache.read_the_map_again"}) == []


@pytest.mark.parametrize(
    ("at", "source"),
    [
        ("services/a_new_cache.py", A_CACHE_THE_LOADER_FINDS_BY_ITSELF),
        ("services/internalization_room/canon/a_new_cache.py", A_CACHE_UNDER_THE_CANON),
    ],
    ids=["declared per canon", "declared under the canon package"],
)
def test_a_cache_the_loader_finds_by_itself_is_not_reported(
    tmp_path: Path, at: str, source: str
) -> None:
    assert _unlisted_caches(_an_app_holding(tmp_path, at, source), set()) == []


def test_every_cache_in_app_is_found_by_the_loader_or_listed_in_the_harness() -> None:
    prompts = {
        f"{cache.__module__}.{cache.__qualname__}" for _, cache in the_caches_of_the_prompts()
    }
    listed = (
        prompts
        | set(THE_CACHES_THAT_READ_THE_CANON_FROM_OUTSIDE_IT)
        | set(THE_CACHES_THAT_READ_NO_CANON)
    )

    assert _unlisted_caches(APP, listed) == []


def test_a_cache_that_shares_the_name_of_a_prompt_cache_is_not_the_harness_to_forget(
    tmp_path: Path,
) -> None:
    of_the_harness, of_something_else = _the_clears_in(
        _planted(tmp_path, CLEARS_TWO_CACHES_THAT_SHARE_A_NAME), _the_caches_the_harness_forgets()
    )

    assert (of_the_harness, of_something_else) == ([6], [5])


def test_no_test_clears_a_cache_the_harness_forgets_by_hand() -> None:
    owned = _the_caches_the_harness_forgets()
    by_hand: list[str] = []
    for module in sorted(TESTS.rglob("*.py")):
        if module.name == "canon_harness.py":
            continue
        of_the_harness, _ = _the_clears_in(module, owned)
        by_hand.extend(f"{module.relative_to(TESTS)}:{line}" for line in of_the_harness)
    in_the_harness, _ = _the_clears_in(TESTS / "canon_harness.py", owned)

    assert in_the_harness, "no clear was read in the harness: the detector is what is broken"
    assert by_hand == [], (
        "the canon is forgotten through canon_harness.forget_the_canon "
        "and the prompts through canon_harness.forget_the_prompts"
    )
