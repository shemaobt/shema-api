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
    the_names_the_forgotten_caches_are_reached_by,
)

TESTS = Path(__file__).resolve().parent
APP = TESTS.parent / "app"
THE_CANON_PACKAGE = "app.services.internalization_room.canon."


def _the_caches_the_harness_forgets() -> set[str]:
    return the_names_the_forgotten_caches_are_reached_by()


def _imports_of(tree: ast.AST) -> dict[str, str]:
    imports: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.partition(".")[0]
                imports[alias.asname or root] = alias.name if alias.asname else root
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imports[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return imports


def _chain(node: ast.expr) -> tuple[str, str] | None:
    attributes: list[str] = []
    while isinstance(node, ast.Attribute):
        attributes.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        return node.id, "".join(f".{attribute}" for attribute in reversed(attributes))
    return None


def _names_in(
    expression: ast.AST, imports: dict[str, str], fed_by: dict[str, set[str]]
) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(expression):
        if isinstance(node, ast.Name | ast.Attribute) and (chain := _chain(node)):
            root, path = chain
            for base in fed_by.get(root, set()) | {imports.get(root, root)}:
                names.add(base + path)
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


def _bindings(nodes: Iterable[ast.AST]) -> Iterator[tuple[list[str], ast.AST]]:
    for node in nodes:
        if isinstance(node, ast.For):
            yield (
                [bound.id for bound in ast.walk(node.target) if isinstance(bound, ast.Name)],
                (node.iter),
            )
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    yield [target.id], node.value
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.value is not None
        ):
            yield [node.target.id], node.value


def _fed_by(
    nodes: Iterable[ast.AST], imports: dict[str, str], seed: dict[str, set[str]]
) -> dict[str, set[str]]:
    fed_by = {name: set(fed) for name, fed in seed.items()}
    bindings = list(_bindings(nodes))
    for _ in range(len(bindings) + 1):
        grew = False
        for bound, source in bindings:
            fed = _names_in(source, imports, fed_by)
            for name in bound:
                before = len(fed_by.setdefault(name, set()))
                fed_by[name] |= fed
                grew = grew or len(fed_by[name]) != before
        if not grew:
            break
    return fed_by


def _the_clears_in(module: Path, canon_caches: set[str]) -> tuple[list[int], list[int]]:
    tree = ast.parse(module.read_text(encoding="utf-8"))
    imports = _imports_of(tree)
    at_the_top = list(_outside_every_function(tree))
    at_the_top_fed = _fed_by(at_the_top, imports, {})
    scopes = [(at_the_top, at_the_top_fed)]
    for function in _outermost_functions(tree):
        within = list(ast.walk(function))
        scopes.append((within, _fed_by(within, imports, at_the_top_fed)))
    of_the_canon: list[int] = []
    of_something_else: list[int] = []
    for nodes, fed_by in scopes:
        for node in nodes:
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "cache_clear"
            ):
                cleared = _names_in(node.func.value, imports, fed_by)
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

CLEARS_THROUGH_A_TUPLE_LOOP = """\
from app.services.internalization_room.canon import book_material, parse_map


def test_a_case() -> None:
    for named, cached in (("one", book_material.preservation_rules), ("two", parse_map.load_map)):
        cached.cache_clear()
"""

CLEARS_THROUGH_AN_ANNOTATED_NAME = """\
from app.services.internalization_room.canon import book_material

cached: object = book_material.preservation_rules


def test_a_case() -> None:
    cached.cache_clear()
"""

CLEARS_THROUGH_A_NAME_FED_BY_A_NAME = """\
from app.services.internalization_room.canon import book_material


def test_a_case() -> None:
    first = book_material.preservation_rules
    second = first
    second.cache_clear()
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

CLEARS_THROUGH_A_NAME_IMPORTED_FROM_ITS_MODULE = """\
from app.services.internalization_room.canon.parse_map import load_map


def test_a_case() -> None:
    load_map.cache_clear()
"""

CLEARS_THROUGH_A_NAME_IMPORTED_UNDER_ANOTHER_NAME = """\
from app.services.internalization_room.canon.parse_map import load_map as read_the_map


def test_a_case() -> None:
    read_the_map.cache_clear()
"""

CLEARS_THROUGH_A_MODULE_UNDER_ANOTHER_NAME = """\
import app.services.internalization_room.canon.parse_map as pm


def test_a_case() -> None:
    pm.load_map.cache_clear()
"""

CLEARS_THROUGH_THE_FULL_PATH = """\
import app.services.internalization_room.canon.parse_map


def test_a_case() -> None:
    app.services.internalization_room.canon.parse_map.load_map.cache_clear()
"""

CLEARS_THROUGH_A_NAME_THAT_HOLDS_THE_MODULE = """\
from app.services.internalization_room.canon import parse_map


def test_a_case() -> None:
    held = parse_map
    held.load_map.cache_clear()
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

CLEARS_A_CACHE_THAT_SHARES_A_CANON_NAME = """\
from app.services.internalization_room import passage_lines


def test_a_case() -> None:
    passage_lines.verse_ranges.cache_clear()
"""

CLEARS_THE_FAIL_SAFE_SECTIONS_BY_THE_NAME_IT_IS_IMPORTED_AS = """\
from app.services.internalization_room.fail_safe import _sections


def test_a_case() -> None:
    _sections.cache_clear()
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
        (CLEARS_THROUGH_A_TUPLE_LOOP, 6),
        (CLEARS_THROUGH_AN_ANNOTATED_NAME, 7),
        (CLEARS_THROUGH_A_NAME_FED_BY_A_NAME, 7),
        (CLEARS_THROUGH_A_NAME_FED_AT_THE_TOP, 7),
        (CLEARS_THROUGH_A_NAME_FED_BY_THE_CASE_AROUND_IT, 8),
        (CLEARS_THROUGH_A_NAME_IMPORTED_FROM_ITS_MODULE, 5),
        (CLEARS_THROUGH_A_NAME_IMPORTED_UNDER_ANOTHER_NAME, 5),
        (CLEARS_THROUGH_A_MODULE_UNDER_ANOTHER_NAME, 5),
        (CLEARS_THROUGH_THE_FULL_PATH, 5),
        (CLEARS_THROUGH_A_NAME_THAT_HOLDS_THE_MODULE, 6),
    ],
    ids=[
        "named at the clear",
        "named by the loop that feeds it",
        "named by a tuple the loop unpacks",
        "named by an annotated assignment",
        "named by a name that another name feeds",
        "named by the module that feeds it",
        "named by the case around the function that clears it",
        "named by the name its module exports",
        "named through a name imported under another name",
        "named through a module imported under another name",
        "named by the full path of its module",
        "named through a name that holds the module",
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
        (CLEARS_THE_FAIL_SAFE_SECTIONS_BY_THE_NAME_IT_IS_IMPORTED_AS, 5),
        (CLEARS_THE_PROMPT_LOADER, 5),
    ],
    ids=[
        "the fail-safe sections",
        "the fail-safe file by an alias",
        "the fail-safe sections by the name they are imported as",
        "the prompt loader",
    ],
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
        ("services/internalization_room/canon/a_new_cache.py", A_CACHE_NOBODY_LISTED),
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


def test_a_cache_that_shares_the_name_of_a_canon_cache_is_not_the_canon_to_forget(
    tmp_path: Path,
) -> None:
    of_the_canon, of_something_else = _the_clears_in(
        _planted(tmp_path, CLEARS_A_CACHE_THAT_SHARES_A_CANON_NAME),
        _the_caches_the_harness_forgets(),
    )

    assert (of_the_canon, of_something_else) == ([], [5])


def test_no_test_clears_a_cache_the_harness_forgets_by_hand() -> None:
    owned = _the_caches_the_harness_forgets()
    by_hand: list[str] = []
    for module in sorted(TESTS.rglob("*.py")):
        if module.name == "canon_harness.py":
            continue
        of_the_harness, _ = _the_clears_in(module, owned)
        by_hand.extend(f"{module.relative_to(TESTS)}:{line}" for line in of_the_harness)
    harness = TESTS / "canon_harness.py"
    in_the_harness, _ = _the_clears_in(harness, owned)
    the_helper = next(
        node
        for node in ast.walk(ast.parse(harness.read_text(encoding="utf-8")))
        if isinstance(node, ast.FunctionDef) and node.name == "forget_the_prompts"
    )
    the_helpers_clears = {
        node.lineno
        for node in ast.walk(the_helper)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "cache_clear"
    }

    assert the_helpers_clears <= set(in_the_harness), (
        "the clears of forget_the_prompts were not read: the detector is what is broken"
    )
    assert the_helpers_clears, "forget_the_prompts clears nothing"
    assert by_hand == [], (
        "the canon is forgotten through canon_harness.forget_the_canon "
        "and the prompts through canon_harness.forget_the_prompts"
    )
