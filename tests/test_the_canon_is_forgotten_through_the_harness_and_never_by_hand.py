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


def _got_by_getattr(node: ast.AST) -> tuple[ast.expr, str] | None:
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
        and len(node.args) == 2
        and isinstance(node.args[1], ast.Constant)
        and isinstance(node.args[1].value, str)
    ):
        return node.args[0], node.args[1].value
    return None


def _names_in(
    expression: ast.AST,
    imports: dict[str, str],
    sources: dict[str, list[ast.AST]],
    reading: frozenset[str] = frozenset(),
) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(expression):
        if isinstance(node, ast.Name | ast.Attribute) and (chain := _chain(node)):
            root, path = chain
            names.update(base + path for base in _origins(root, imports, sources, reading))
        elif got := _got_by_getattr(node):
            owner, attribute = got
            names.update(
                f"{base}.{attribute}" for base in _names_in(owner, imports, sources, reading)
            )
    return names


def _origins(
    root: str,
    imports: dict[str, str],
    sources: dict[str, list[ast.AST]],
    reading: frozenset[str],
) -> set[str]:
    origins = {imports.get(root, root)}
    if root not in reading:
        for source in sources.get(root, []):
            origins |= _names_in(source, imports, sources, reading | {root})
    return origins


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


def _bound_by(target: ast.expr) -> list[str]:
    return [
        bound.id
        for bound in ast.walk(target)
        if isinstance(bound, ast.Name) and isinstance(bound.ctx, ast.Store)
    ]


Bindings = list[tuple[list[str], ast.AST]]


def _parametrized(decorator: ast.Call) -> tuple[list[str], ast.expr] | None:
    given = {
        **dict(zip(("argnames", "argvalues"), decorator.args, strict=False)),
        **{keyword.arg: keyword.value for keyword in decorator.keywords},
    }
    if _decorator_name(decorator) != "parametrize" or not {"argnames", "argvalues"} <= given.keys():
        return None
    names = [
        name.strip()
        for spelled in ast.walk(given["argnames"])
        if isinstance(spelled, ast.Constant)
        for name in str(spelled.value).split(",")
    ]
    return names, given["argvalues"]


def _arguments_given(tree: ast.AST) -> dict[ast.AST, Bindings]:
    defined = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    given: dict[ast.AST, Bindings] = {function: [] for function in defined.values()}
    for function in defined.values():
        for decorator in function.decorator_list:
            if isinstance(decorator, ast.Call) and (parametrized := _parametrized(decorator)):
                given[function].append(parametrized)
    for call in ast.walk(tree):
        if (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id in defined
        ):
            function = defined[call.func.id]
            parameters = [
                parameter.arg for parameter in [*function.args.posonlyargs, *function.args.args]
            ]
            given[function].extend(
                ([parameter], argument)
                for parameter, argument in zip(parameters, call.args, strict=False)
            )
            given[function].extend(
                ([keyword.arg], keyword.value) for keyword in call.keywords if keyword.arg
            )
    return given


def _bindings(
    nodes: Iterable[ast.AST], arguments: dict[ast.AST, Bindings]
) -> Iterator[tuple[list[str], ast.AST]]:
    for node in nodes:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            yield from arguments.get(node, [])
        elif isinstance(node, ast.For | ast.comprehension):
            yield _bound_by(node.target), node.iter
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                yield _bound_by(target), node.value
        elif isinstance(node, ast.AnnAssign | ast.NamedExpr) and node.value is not None:
            yield _bound_by(node.target), node.value
        elif isinstance(node, ast.withitem) and node.optional_vars is not None:
            yield _bound_by(node.optional_vars), node.context_expr


def _sourced_by(bindings: Bindings, seed: dict[str, list[ast.AST]]) -> dict[str, list[ast.AST]]:
    sources = {name: list(fed) for name, fed in seed.items()}
    for bound, source in bindings:
        for name in bound:
            sources.setdefault(name, []).append(source)
    return sources


def _cleared_by(call: ast.Call) -> ast.expr | None:
    if isinstance(call.func, ast.Attribute) and call.func.attr == "cache_clear":
        return call.func.value
    got = _got_by_getattr(call.func)
    return got[0] if got and got[1] == "cache_clear" else None


def _the_clears_in(module: Path, canon_caches: set[str]) -> tuple[list[int], list[int]]:
    tree = ast.parse(module.read_text(encoding="utf-8"))
    imports = _imports_of(tree)
    at_the_top = list(_outside_every_function(tree))
    arguments = _arguments_given(tree)
    at_the_top_sources = _sourced_by(_bindings(at_the_top, arguments), {})
    scopes = [(at_the_top, at_the_top_sources)]
    for function in _outermost_functions(tree):
        within = list(ast.walk(function))
        within_sources = _sourced_by(_bindings(within, arguments), at_the_top_sources)
        scopes.append((within, within_sources))
    of_the_canon: list[int] = []
    of_something_else: list[int] = []
    for nodes, sources in scopes:
        for node in nodes:
            if isinstance(node, ast.Call) and (cleared := _cleared_by(node)) is not None:
                names = _names_in(cleared, imports, sources)
                (of_the_canon if names & canon_caches else of_something_else).append(node.lineno)
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

CLEARS_THROUGH_A_TUPLE_TARGET = """\
from app.services.internalization_room.canon import book_material


def test_a_case() -> None:
    cached, other = book_material.preservation_rules, 1
    cached.cache_clear()
"""

CLEARS_THROUGH_A_WITH_TARGET = """\
from app.services.internalization_room.canon import book_material


def test_a_case() -> None:
    with book_material.preservation_rules as cached:
        cached.cache_clear()
"""

CLEARS_THROUGH_A_COMPREHENSION_TARGET = """\
from app.services.internalization_room.canon import book_material


def test_a_case() -> None:
    [cached.cache_clear() for cached in (book_material.preservation_rules,)]
"""

CLEARS_THROUGH_A_WALRUS_TARGET = """\
from app.services.internalization_room.canon import book_material


def test_a_case() -> None:
    if cached := book_material.preservation_rules:
        cached.cache_clear()
"""

CLEARS_THROUGH_A_NAME_GIVEN_TO_GETATTR = """\
from app.services.internalization_room.canon import book_material


def test_a_case() -> None:
    getattr(book_material, "preservation_rules").cache_clear()
"""

CLEARS_THROUGH_GETATTR_OF_CACHE_CLEAR = """\
from app.services.internalization_room.canon import book_material


def test_a_case() -> None:
    getattr(book_material.preservation_rules, "cache_clear")()
"""

CLEARS_THROUGH_AN_ARGUMENT_OF_A_HELPER = """\
from app.services.internalization_room.canon import book_material


def forget(cached) -> None:
    cached.cache_clear()


def test_a_case() -> None:
    forget(book_material.preservation_rules)
"""

CLEARS_THROUGH_A_PARAMETRIZED_ARGUMENT = """\
import pytest

from app.services.internalization_room.canon import book_material


@pytest.mark.parametrize("cached", [book_material.preservation_rules])
def test_a_case(cached) -> None:
    cached.cache_clear()
"""

CLEARS_THROUGH_A_KEYWORD_OF_A_HELPER = """\
from app.services.internalization_room.canon import book_material


def forget(cached) -> None:
    cached.cache_clear()


def test_a_case() -> None:
    forget(cached=book_material.preservation_rules)
"""

CLEARS_THROUGH_A_POSITIONAL_ONLY_PARAMETER = """\
from app.services.internalization_room.canon import book_material


def forget(cached, /) -> None:
    cached.cache_clear()


def test_a_case() -> None:
    forget(book_material.preservation_rules)
"""

CLEARS_THROUGH_PARAMETRIZE_WITH_TUPLE = """\
import pytest

from app.services.internalization_room.canon import book_material


@pytest.mark.parametrize(("cached", "other"), [(book_material.preservation_rules, 1)])
def test_a_case(cached) -> None:
    cached.cache_clear()
"""

CLEARS_THROUGH_PARAMETRIZE_WITH_LIST = """\
import pytest

from app.services.internalization_room.canon import book_material


@pytest.mark.parametrize(["cached"], [book_material.preservation_rules])
def test_a_case(cached) -> None:
    cached.cache_clear()
"""

CLEARS_THROUGH_PARAMETRIZE_WITH_KEYWORD = """\
import pytest

from app.services.internalization_room.canon import book_material


@pytest.mark.parametrize("cached", argvalues=[book_material.preservation_rules])
def test_a_case(cached) -> None:
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

A_SPY_ON_A_CANON_CACHE_THE_HARNESS_CALLS = """\
from app.services.internalization_room.canon import book_material


def test_a_case(monkeypatch) -> None:
    cache = book_material.preservation_rules
    empty_it = cache.cache_clear

    def empty_and_note() -> None:
        empty_it()

    monkeypatch.setattr(cache, "cache_clear", empty_and_note)
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


CACHES = {"lru_cache", "cache"}


def _built_by_a_call(value: ast.expr | None) -> bool:
    if not isinstance(value, ast.Call):
        return False
    if isinstance(value.func, ast.Call):
        return _decorator_name(value.func) in CACHES
    return (
        _decorator_name(value) in CACHES
        and bool(value.args)
        and not isinstance(value.args[0], ast.Constant)
    )


def _cache_declared_by(node: ast.AST) -> str | None:
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        kinds = {_decorator_name(decorator) for decorator in node.decorator_list}
        return node.name if kinds & CACHES else None
    if isinstance(node, ast.Assign | ast.AnnAssign) and _built_by_a_call(node.value):
        target = node.targets[0] if isinstance(node, ast.Assign) else node.target
        return ast.unparse(target)
    return None


def _unlisted_caches(root: Path, listed: set[str]) -> list[str]:
    unlisted: list[str] = []
    for module in sorted(root.rglob("*.py")):
        relative = module.relative_to(root.parent)
        dotted = ".".join(relative.with_suffix("").parts)
        for node in ast.walk(ast.parse(module.read_text(encoding="utf-8"))):
            name = _cache_declared_by(node)
            qualified = f"{dotted}.{name}"
            if name is None or dotted.startswith(THE_CANON_PACKAGE) or qualified in listed:
                continue
            unlisted.append(
                f"{relative.as_posix()}:{node.lineno} `{name}` is a cache the harness "
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


A_CACHE_BUILT_BY_A_CALL_NOBODY_LISTED = """\
from functools import lru_cache


def _read() -> str:
    return "the map"


read_the_map_again = lru_cache(maxsize=1)(_read)
"""

A_CACHE_BUILT_BY_A_BARE_FUNCTOOLS_CALL = """\
import functools


def _read() -> str:
    return "the map"


read_the_map_again = functools.cache(_read)
"""

A_CACHE_BUILT_BY_LRU_CACHE_ON_A_FUNCTION = """\
from functools import lru_cache


def _read() -> str:
    return "the map"


read_the_map_again = lru_cache(_read)
"""

A_DECORATOR_KEPT_IN_A_NAME = """\
from functools import lru_cache

keep_one = lru_cache(maxsize=1)
keep_many = lru_cache(128)
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
        (CLEARS_THROUGH_A_TUPLE_TARGET, 6),
        (CLEARS_THROUGH_A_WITH_TARGET, 6),
        (CLEARS_THROUGH_A_COMPREHENSION_TARGET, 5),
        (CLEARS_THROUGH_A_WALRUS_TARGET, 6),
        (CLEARS_THROUGH_A_NAME_GIVEN_TO_GETATTR, 5),
        (CLEARS_THROUGH_GETATTR_OF_CACHE_CLEAR, 5),
        (CLEARS_THROUGH_AN_ARGUMENT_OF_A_HELPER, 5),
        (CLEARS_THROUGH_A_PARAMETRIZED_ARGUMENT, 8),
        (CLEARS_THROUGH_A_KEYWORD_OF_A_HELPER, 5),
        (CLEARS_THROUGH_A_POSITIONAL_ONLY_PARAMETER, 5),
        (CLEARS_THROUGH_PARAMETRIZE_WITH_TUPLE, 8),
        (CLEARS_THROUGH_PARAMETRIZE_WITH_LIST, 8),
        (CLEARS_THROUGH_PARAMETRIZE_WITH_KEYWORD, 8),
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
        "named by a tuple target",
        "named by a with target",
        "named by a comprehension target",
        "named by a walrus target",
        "named by a string given to getattr",
        "cleared by getattr of cache_clear",
        "named by the argument of a helper",
        "named by a parametrized argument",
        "named by the keyword of a helper",
        "named by a positional-only parameter",
        "named by a parametrize with a tuple of names",
        "named by a parametrize with a list of names",
        "named by a parametrize with an argvalues keyword",
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


def test_a_cache_built_by_a_call_is_reported_like_one_built_by_a_decorator(
    tmp_path: Path,
) -> None:
    app = _an_app_holding(
        tmp_path, "services/a_new_cache.py", A_CACHE_BUILT_BY_A_CALL_NOBODY_LISTED
    )

    (reported,) = _unlisted_caches(app, set())

    assert reported.startswith(
        "app/services/a_new_cache.py:8 `read_the_map_again` is a cache the harness does not know. "
    )
    assert 'list "app.services.a_new_cache.read_the_map_again" in ' in reported


@pytest.mark.parametrize(
    "source",
    [A_CACHE_BUILT_BY_A_BARE_FUNCTOOLS_CALL, A_CACHE_BUILT_BY_LRU_CACHE_ON_A_FUNCTION],
    ids=["functools.cache on a function", "lru_cache on a function"],
)
def test_a_cache_built_by_handing_the_function_to_the_decorator_is_reported(
    tmp_path: Path, source: str
) -> None:
    app = _an_app_holding(tmp_path, "services/a_new_cache.py", source)

    assert len(_unlisted_caches(app, set())) == 1


def test_a_decorator_kept_in_a_name_is_not_a_cache(tmp_path: Path) -> None:
    app = _an_app_holding(tmp_path, "services/a_new_cache.py", A_DECORATOR_KEPT_IN_A_NAME)

    assert _unlisted_caches(app, set()) == []


def test_a_bare_functools_cache_is_a_cache_too(tmp_path: Path) -> None:
    app = _an_app_holding(tmp_path, "services/a_new_cache.py", A_BARE_CACHE_NOBODY_LISTED)

    assert len(_unlisted_caches(app, set())) == 1


def test_a_cache_that_is_listed_by_name_is_not_reported(tmp_path: Path) -> None:
    app = _an_app_holding(tmp_path, "services/a_new_cache.py", A_CACHE_NOBODY_LISTED)

    assert _unlisted_caches(app, {"app.services.a_new_cache.read_the_map_again"}) == []


def test_a_cache_listed_under_the_same_name_in_another_module_does_not_hide_this_one(
    tmp_path: Path,
) -> None:
    app = _an_app_holding(tmp_path, "services/a_new_cache.py", A_CACHE_NOBODY_LISTED)

    reported = _unlisted_caches(app, {"app.services.another_cache.read_the_map_again"})

    assert len(reported) == 1


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


def test_a_spy_the_harness_calls_through_a_bound_cache_clear_is_not_a_clear_by_hand(
    tmp_path: Path,
) -> None:
    of_the_canon, of_something_else = _the_clears_in(
        _planted(tmp_path, A_SPY_ON_A_CANON_CACHE_THE_HARNESS_CALLS),
        _the_caches_the_harness_forgets(),
    )

    assert (of_the_canon, of_something_else) == ([], [])


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
