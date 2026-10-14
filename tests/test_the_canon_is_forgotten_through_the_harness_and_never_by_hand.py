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

from tests import canon_harness
from tests.canon_harness import (
    THE_CACHES_THAT_READ_NO_CANON,
    THE_CACHES_THAT_READ_THE_CANON_FROM_OUTSIDE_IT,
    the_caches_of_the_prompts,
    the_names_the_forgotten_caches_are_reached_by,
)

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent
APP = ROOT / "app"
THE_CANON_PACKAGE = "app.services.internalization_room.canon."


def _the_caches_the_harness_forgets() -> set[str]:
    return the_names_the_forgotten_caches_are_reached_by()


def _imports_of(tree: ast.AST, package: list[str]) -> dict[str, str]:
    imports: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.partition(".")[0]
                imports[alias.asname or root] = alias.name if alias.asname else root
        elif isinstance(node, ast.ImportFrom):
            held = package[: len(package) - node.level + 1] if node.level else []
            where = ".".join([*held, *([node.module] if node.module else [])])
            for alias in node.names:
                imports[alias.asname or alias.name] = f"{where}.{alias.name}"
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
            steps = path.split(".")[1:]
            for kept in range(1, len(steps) + 1):
                held = root + "".join(f".{step}" for step in steps[:kept])
                if held in sources:
                    rest = "".join(f".{step}" for step in steps[kept:])
                    names.update(base + rest for base in _origins(held, imports, sources, reading))
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
    bound: list[str] = []
    for node in ast.walk(target):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            bound.append(node.id)
        elif (
            isinstance(node, ast.Attribute)
            and isinstance(node.ctx, ast.Store)
            and (chain := _chain(node))
        ):
            bound.append(chain[0] + chain[1])
    return bound


Bindings = list[tuple[list[str], ast.AST]]


def _pairs(target: ast.expr, value: ast.AST) -> Iterator[tuple[list[str], ast.AST]]:
    if (
        isinstance(target, ast.Tuple | ast.List)
        and isinstance(value, ast.Tuple | ast.List)
        and len(target.elts) == len(value.elts)
        and not any(isinstance(element, ast.Starred) for element in value.elts)
    ):
        for element, fed in zip(target.elts, value.elts, strict=True):
            yield from _pairs(element, fed)
    else:
        yield _bound_by(target), value


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


def _parametrized_bindings(names: list[str], values: ast.AST) -> Bindings:
    rows = values.elts if isinstance(values, ast.List | ast.Tuple) else []
    if (
        len(names) > 1
        and rows
        and all(
            isinstance(row, ast.Tuple | ast.List) and len(row.elts) == len(names) for row in rows
        )
    ):
        return [([name], row.elts[at]) for row in rows for at, name in enumerate(names)]
    return [(names, values)]


Function = ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda
Functions = dict[str, Function]


def _defined_in(scope: ast.AST) -> Functions:
    defined: Functions = {}
    for child in ast.iter_child_nodes(scope):
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
            defined[child.name] = child
        elif (
            isinstance(child, ast.Assign)
            and isinstance(child.value, ast.Lambda)
            and len(child.targets) == 1
            and isinstance(child.targets[0], ast.Name)
        ):
            defined[child.targets[0].id] = child.value
        elif not isinstance(child, ast.ClassDef):
            defined |= _defined_in(child)
    return defined


def _handed_to(
    function: Function, arguments: list[ast.expr], keywords: list[ast.keyword], skipping: int = 0
) -> list[tuple[str, ast.expr]]:
    parameters = [parameter.arg for parameter in [*function.args.posonlyargs, *function.args.args]]
    return [
        *zip(parameters[skipping:], arguments, strict=False),
        *((keyword.arg, keyword.value) for keyword in keywords if keyword.arg),
    ]


Handed = list[tuple[ast.AST, Function, str, ast.expr]]


def _hand_over(
    function: Function,
    arguments: list[ast.expr],
    keywords: list[ast.keyword],
    handed: Handed,
    caller: ast.AST,
) -> None:
    handed.extend(
        (caller, function, parameter, argument)
        for parameter, argument in _handed_to(function, arguments, keywords)
    )


def _read_the_calls(scope: ast.AST, visible: Functions, handed: Handed, caller: ast.AST) -> None:
    for child in ast.iter_child_nodes(scope):
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Lambda):
                _hand_over(child.func, child.args, child.keywords, handed, caller)
            elif isinstance(child.func, ast.Name):
                function = visible.get(child.func.id)
                if function is not None:
                    _hand_over(function, child.args, child.keywords, handed, caller)
                elif (
                    child.func.id == "map" and child.args and isinstance(child.args[0], ast.Lambda)
                ):
                    _hand_over(child.args[0], child.args[1:], [], handed, caller)
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
            within = child if isinstance(caller, ast.Module) else caller
            _read_the_calls(child, visible | _defined_in(child), handed, within)
        else:
            _read_the_calls(child, visible, handed, caller)


def _arguments_given(tree: ast.Module) -> tuple[dict[ast.AST, Bindings], Handed]:
    given: dict[ast.AST, Bindings] = {
        node: [] for node in ast.walk(tree) if isinstance(node, Function)
    }
    for function in given:
        for decorator in getattr(function, "decorator_list", []):
            if isinstance(decorator, ast.Call) and (parametrized := _parametrized(decorator)):
                given[function].extend(_parametrized_bindings(*parametrized))
    handed: Handed = []
    _read_the_calls(tree, _defined_in(tree), handed, tree)
    return given, handed


def _bindings(
    nodes: Iterable[ast.AST], arguments: dict[ast.AST, Bindings]
) -> Iterator[tuple[list[str], ast.AST]]:
    for node in nodes:
        if isinstance(node, Function):
            yield from arguments.get(node, [])
        elif isinstance(node, ast.For | ast.comprehension):
            yield _bound_by(node.target), node.iter
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                yield from _pairs(target, node.value)
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


def _bound_clear_of(expression: ast.AST) -> ast.expr | None:
    if isinstance(expression, ast.Attribute) and expression.attr == "cache_clear":
        return expression.value
    got = _got_by_getattr(expression)
    return got[0] if got and got[1] == "cache_clear" else None


def _bound_clears_kept_in(
    name: str, sources: dict[str, list[ast.AST]], reading: frozenset[str] = frozenset()
) -> list[ast.expr]:
    if name in reading:
        return []
    cleared: list[ast.expr] = []
    for source in sources.get(name, []):
        if (bound := _bound_clear_of(source)) is not None:
            cleared.append(bound)
        elif isinstance(source, ast.Name):
            cleared.extend(_bound_clears_kept_in(source.id, sources, reading | {name}))
    return cleared


def _cleared_by(
    call: ast.Call, sources: dict[str, list[ast.AST]], spied_on: set[ast.AST]
) -> list[ast.expr]:
    if (direct := _bound_clear_of(call.func)) is not None:
        return [direct]
    if isinstance(call.func, ast.Name) and call not in spied_on:
        return _bound_clears_kept_in(call.func.id, sources)
    return []


def _inside_the_spies(tree: ast.AST) -> set[ast.AST]:
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    called = {call.func.id for call in calls if isinstance(call.func, ast.Name)}
    installed = {
        argument.id
        for call in calls
        if isinstance(call.func, ast.Attribute) and call.func.attr == "setattr"
        for argument in call.args
        if isinstance(argument, ast.Name)
    }
    return {
        inside
        for function in ast.walk(tree)
        if isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef)
        and function.name in installed - called
        for inside in ast.walk(function)
    }


def _values_returned_by(function: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.expr]:
    values: list[ast.expr] = []
    pending = list(ast.iter_child_nodes(function))
    while pending:
        node = pending.pop()
        if isinstance(node, Function):
            continue
        if isinstance(node, ast.Return | ast.Yield) and node.value is not None:
            values.append(node.value)
        pending.extend(ast.iter_child_nodes(node))
    return values


def _leads_to_a_cache(name: str, canon_caches: set[str]) -> bool:
    return any(cache == name or cache.startswith(f"{name}.") for cache in canon_caches)


def _fixtures_of(tree: ast.Module | ast.ClassDef) -> set[str]:
    return {
        function.name
        for function in tree.body
        if isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef)
        and "fixture" in {_decorator_name(decorator) for decorator in function.decorator_list}
    }


def _called_by_pytest(tree: ast.Module) -> set[ast.AST]:
    scopes = [tree, *(node for node in ast.walk(tree) if isinstance(node, ast.ClassDef))]
    return {
        function
        for scope in scopes
        for function in scope.body
        if isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef)
        and (
            function.name.startswith("test")
            or "fixture" in {_decorator_name(decorator) for decorator in function.decorator_list}
        )
    }


def _fixtures_in_reach(tree: ast.Module) -> dict[ast.AST, dict[str, ast.AST]]:
    classes = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}

    def lineage(scope: ast.ClassDef) -> list[ast.ClassDef]:
        return [
            scope,
            *(
                each
                for base in scope.bases
                if isinstance(base, ast.Name) and base.id in classes
                for each in lineage(classes[base.id])
            ),
        ]

    around = {
        inner: outer
        for outer in classes.values()
        for inner in outer.body
        if isinstance(inner, ast.ClassDef)
    }

    def visible(scope: ast.ClassDef) -> list[ast.ClassDef]:
        return [*lineage(scope), *(visible(around[scope]) if scope in around else [])]

    reach: dict[ast.AST, dict[str, ast.AST]] = {}
    for scope in ast.walk(tree):
        if isinstance(scope, ast.ClassDef):
            fixtures = {
                function.name: function
                for each in reversed(visible(scope))
                for function in each.body
                if isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef)
                and function.name in _fixtures_of(each)
            }
            for function in scope.body:
                if isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef):
                    reach[function] = fixtures
    return reach


def _as_resolved(names: set[str]) -> list[ast.expr]:
    return [ast.Name(id=name) for name in sorted(names)]


def _names_returned_by(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    imports: dict[str, str],
    fed: dict[ast.AST, Bindings],
    at_the_top_sources: dict[str, list[ast.AST]],
    canon_caches: set[str],
) -> set[str]:
    sources = _sourced_by(_bindings(list(ast.walk(function)), fed), at_the_top_sources)
    return {
        name
        for value in _values_returned_by(function)
        for name in _names_in(value, imports, sources)
        if _leads_to_a_cache(name, canon_caches)
    }


def _fed_by_what_functions_return(
    tree: ast.Module,
    imports: dict[str, str],
    arguments: dict[ast.AST, Bindings],
    at_the_top: list[ast.AST],
    canon_caches: set[str],
    names_a_cache: bool,
    outside: dict[str, set[str]],
) -> tuple[dict[ast.AST, Bindings], dict[str, list[ast.AST]], dict[str, set[str]]]:
    functions = {
        function.name: function
        for function in tree.body
        if names_a_cache and isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    overridden = _fixtures_of(tree) & outside.keys()
    fixtures = _fixtures_of(tree) - overridden
    called_by_pytest = _called_by_pytest(tree) if outside else set()
    reach = _fixtures_in_reach(tree) if names_a_cache else {}
    of_the_classes = {fixture for each in reach.values() for fixture in each.values()}
    carried: dict[str, set[str]] = {}
    carried_by_the_classes: dict[ast.AST, set[str]] = {}
    for _ in range(len(functions) + len(of_the_classes) + 1):
        fed = {
            node: [
                *bindings,
                *(
                    ([parameter.arg], value)
                    for parameter in _parameters_of(node)
                    for value in _as_resolved(
                        carried_by_the_classes.get(reach[node][parameter.arg], set())
                        if parameter.arg in reach.get(node, {})
                        else (
                            carried
                            if parameter.arg in fixtures
                            else outside
                            if node in called_by_pytest
                            else {}
                        ).get(parameter.arg, set())
                    )
                ),
            ]
            for node, bindings in arguments.items()
        }
        at_the_top_sources = _sourced_by(
            [
                *_bindings(at_the_top, fed),
                *(
                    ([name], value)
                    for name, names in carried.items()
                    if name not in overridden
                    for value in _as_resolved(names)
                ),
            ],
            {},
        )
        now = {
            name: names
            for name, function in functions.items()
            if (
                names := _names_returned_by(
                    function, imports, fed, at_the_top_sources, canon_caches
                )
            )
        }
        now_by_the_classes = {
            fixture: names
            for fixture in of_the_classes
            if (
                names := _names_returned_by(fixture, imports, fed, at_the_top_sources, canon_caches)
            )
        }
        if now == carried and now_by_the_classes == carried_by_the_classes:
            break
        carried = now
        carried_by_the_classes = now_by_the_classes
    return fed, at_the_top_sources, carried


def _parameters_of(function: Function) -> list[ast.arg]:
    return [*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs]


def _module_file(dotted: str, root: Path) -> Path | None:
    base = root.joinpath(*dotted.split("."))
    return next(
        (found for found in (base.with_suffix(".py"), base / "__init__.py") if found.is_file()),
        None,
    )


def _package_of(module: Path, root: Path) -> list[str]:
    return list(module.relative_to(root).parent.parts) if module.is_relative_to(root) else []


Callee = tuple[Path, ast.Module, ast.FunctionDef | ast.AsyncFunctionDef, int]


def _is_static(method: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return "staticmethod" in {_decorator_name(decorator) for decorator in method.decorator_list}


def _defined_at(
    tree: ast.Module, path: list[str]
) -> tuple[ast.FunctionDef | ast.AsyncFunctionDef, int] | None:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and path == [node.name]:
            return node, 0
        if isinstance(node, ast.ClassDef) and path[:1] == [node.name]:
            for method in node.body:
                if isinstance(method, ast.FunctionDef | ast.AsyncFunctionDef) and path[1:] == [
                    method.name
                ]:
                    return method, 0 if _is_static(method) else 1
    return None


def _callee_named(dotted: str, module: Path, tree: ast.Module, root: Path) -> Callee | None:
    parts = dotted.split(".")
    if len(parts) == 2 and (here := _defined_at(tree, parts)):
        return module, tree, here[0], here[1]
    for taken in range(len(parts) - 1, 0, -1):
        if (file := _module_file(".".join(parts[:taken]), root)) is None:
            continue
        callee_tree = ast.parse(file.read_text(encoding="utf-8"))
        if found := _defined_at(callee_tree, parts[taken:]):
            return file, callee_tree, found[0], found[1]
        return None
    return None


def _clears_its_parameter(callee: Callee, parameter: str, root: Path) -> bool:
    file, tree, function, _ = callee
    if "cache_clear" not in file.read_text(encoding="utf-8"):
        return False
    marker = f"<marker>.{parameter}"
    of_the_marker, _ = _clears_in_tree(
        file,
        tree,
        {marker},
        root,
        {function: [([parameter], ast.Name(id=marker))]},
        follow=False,
    )
    return bool(of_the_marker)


def _leftmost_name(node: ast.expr) -> str | None:
    while isinstance(node, ast.Attribute | ast.Call):
        node = node.value if isinstance(node, ast.Attribute) else node.func
    return node.id if isinstance(node, ast.Name) else None


def _hands_the_canon_to_a_clear(
    call: ast.Call,
    module: Path,
    tree: ast.Module,
    imports: dict[str, str],
    sources: dict[str, list[ast.AST]],
    canon_caches: set[str],
    root: Path,
) -> bool:
    classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    leftmost = _leftmost_name(call.func)
    if leftmost not in imports and leftmost not in sources and leftmost not in classes:
        return False
    handed = [
        argument
        for argument in [*call.args, *(keyword.value for keyword in call.keywords)]
        if _names_in(argument, imports, sources) & canon_caches
    ]
    if not handed:
        return False
    callees = (
        {f"{owner}.{call.func.attr}" for owner in _names_in(call.func.value, imports, sources)}
        if isinstance(call.func, ast.Attribute)
        else _names_in(call.func, imports, sources)
    )
    for dotted in callees:
        if (callee := _callee_named(dotted, module, tree, root)) is None:
            continue
        for parameter, argument in _handed_to(callee[2], call.args, call.keywords, callee[3]):
            if argument in handed and _clears_its_parameter(callee, parameter, root):
                return True
    return False


def _scopes(
    tree: ast.Module,
    arguments: dict[ast.AST, Bindings],
    at_the_top: list[ast.AST],
    at_the_top_sources: dict[str, list[ast.AST]],
) -> list[tuple[ast.AST, list[ast.AST], dict[str, list[ast.AST]]]]:
    scopes = [(tree, at_the_top, at_the_top_sources)]
    for function in _outermost_functions(tree):
        within = list(ast.walk(function))
        scopes.append(
            (function, within, _sourced_by(_bindings(within, arguments), at_the_top_sources))
        )
    return scopes


def _handed_down(
    handed: Handed,
    imports: dict[str, str],
    scopes: list[tuple[ast.AST, list[ast.AST], dict[str, list[ast.AST]]]],
    canon_caches: set[str],
) -> set[tuple[ast.AST, str, str]]:
    sources = {caller: caller_sources for caller, _, caller_sources in scopes}
    return {
        (function, parameter, name)
        for caller, function, parameter, argument in handed
        for name in _names_in(argument, imports, sources[caller])
        if "." in name and _leads_to_a_cache(name, canon_caches)
    }


def _conftests_above(module: Path, root: Path) -> list[Path]:
    directory = module.parent
    found = [directory / "conftest.py"]
    while directory != root and directory.is_relative_to(root):
        directory = directory.parent
        found.append(directory / "conftest.py")
    return found[::-1]


def _fixtures_of_the_conftest(
    module: Path, tree: ast.Module, canon_caches: set[str], root: Path
) -> dict[str, set[str]]:
    conftests = [conftest for conftest in _conftests_above(module, root) if conftest.is_file()]
    texts = {conftest: conftest.read_text(encoding="utf-8") for conftest in conftests}
    if module not in conftests:
        texts[module] = module.read_text(encoding="utf-8")

    def names_a_cache(file: Path) -> bool:
        return any(cache.rpartition(".")[2] in texts[file] for cache in canon_caches)

    def requests_a_fixture_of_the_case() -> bool:
        requested = {
            parameter.arg
            for conftest in conftests
            for node in ast.walk(ast.parse(texts[conftest]))
            if isinstance(node, Function)
            for parameter in _parameters_of(node)
        }
        return bool(_fixtures_of(tree) & requested)

    if not (
        any(names_a_cache(conftest) for conftest in conftests)
        or (
            module not in conftests
            and _fixtures_of(tree)
            and names_a_cache(module)
            and requests_a_fixture_of_the_case()
        )
    ):
        return {}
    trees = {file: tree if file == module else ast.parse(text) for file, text in texts.items()}
    defined_by = {name: file for file, parsed in trees.items() for name in _fixtures_of(parsed)}
    carried_by_name: dict[str, set[str]] = {}
    while True:
        now: dict[str, set[str]] = {}
        for file, parsed in trees.items():
            given, _ = _arguments_given(parsed)
            *_, carried = _fed_by_what_functions_return(
                parsed,
                _imports_of(parsed, _package_of(file, root)),
                given,
                list(_outside_every_function(parsed)),
                canon_caches,
                True,
                carried_by_name,
            )
            now |= {
                name: carried.get(name, set())
                for name in _fixtures_of(parsed)
                if defined_by[name] == file
            }
        if now == carried_by_name:
            return {name: names for name, names in now.items() if names}
        carried_by_name = now


def _clears_in_tree(
    module: Path,
    tree: ast.Module,
    canon_caches: set[str],
    root: Path,
    seeded: dict[ast.AST, Bindings],
    *,
    follow: bool,
) -> tuple[list[int], list[int]]:
    text = module.read_text(encoding="utf-8")
    outside = _fixtures_of_the_conftest(module, tree, canon_caches, root)
    names_a_cache = bool(outside) or any(cache.rpartition(".")[2] in text for cache in canon_caches)
    imports = _imports_of(tree, _package_of(module, root))
    spied_on = _inside_the_spies(tree)
    at_the_top = list(_outside_every_function(tree))
    given, handed = _arguments_given(tree)
    for function, bindings in seeded.items():
        given[function].extend(bindings)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for method in node.body:
                if isinstance(method, ast.FunctionDef | ast.AsyncFunctionDef) and method.args.args:
                    given[method].append(([method.args.args[0].arg], ast.Name(id=node.name)))
    arguments, at_the_top_sources, _ = _fed_by_what_functions_return(
        tree,
        imports,
        given,
        at_the_top,
        canon_caches,
        names_a_cache,
        outside,
    )
    scopes = _scopes(tree, arguments, at_the_top, at_the_top_sources)
    passed: set[tuple[ast.AST, str, str]] = set()
    while names_a_cache and (new := _handed_down(handed, imports, scopes, canon_caches) - passed):
        passed |= new
        for function, parameter, name in new:
            arguments[function].append(([parameter], ast.Name(id=name)))
            if function in at_the_top:
                at_the_top_sources.setdefault(parameter, []).append(ast.Name(id=name))
        scopes = _scopes(tree, arguments, at_the_top, at_the_top_sources)
    of_the_canon: list[int] = []
    of_something_else: list[int] = []
    for _, nodes, sources in scopes:
        for node in nodes:
            if not isinstance(node, ast.Call):
                continue
            if cleared := _cleared_by(node, sources, spied_on):
                names = set().union(*(_names_in(each, imports, sources) for each in cleared))
                (of_the_canon if names & canon_caches else of_something_else).append(node.lineno)
            elif (
                follow
                and names_a_cache
                and _hands_the_canon_to_a_clear(
                    node, module, tree, imports, sources, canon_caches, root
                )
            ):
                of_the_canon.append(node.lineno)
    return sorted(of_the_canon), sorted(of_something_else)


def _the_clears_in(
    module: Path, canon_caches: set[str], root: Path = ROOT
) -> tuple[list[int], list[int]]:
    tree = ast.parse(module.read_text(encoding="utf-8"))
    return _clears_in_tree(module, tree, canon_caches, root, {}, follow=True)


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

CLEARS_THROUGH_A_BOUND_CLEAR_KEPT_IN_A_NAME = """\
from app.services.internalization_room.canon import book_material


def test_a_case() -> None:
    cache = book_material.preservation_rules
    empty_it = cache.cache_clear
    empty_it()
"""

CLEARS_THROUGH_A_BOUND_CLEAR_GOT_BY_GETATTR = """\
from app.services.internalization_room.canon import book_material


def test_a_case() -> None:
    empty_it = getattr(book_material.preservation_rules, "cache_clear")
    empty_it()
"""

CLEARS_THROUGH_AN_ATTRIBUTE_TARGET = """\
from types import SimpleNamespace

from app.services.internalization_room.canon import book_material


def test_a_case() -> None:
    holder = SimpleNamespace()
    holder.cached = book_material.preservation_rules
    holder.cached.cache_clear()
"""

CLEARS_THE_SIBLING_OF_AN_ATTRIBUTE_TARGET = """\
from types import SimpleNamespace

from app.services.internalization_room.canon import book_material


def test_a_case() -> None:
    holder = SimpleNamespace()
    holder.cached = book_material.preservation_rules
    holder.other = 1
    holder.other.cache_clear()
"""

CLEARS_THROUGH_A_LAMBDA_CALLED_AT_THE_TOP_OF_THE_MODULE = """\
from app.services.internalization_room.canon import book_material

(lambda cached: cached.cache_clear())(book_material.preservation_rules)
"""

CLEARS_THROUGH_A_LAMBDA_CALLED_IN_PLACE = """\
from app.services.internalization_room.canon import book_material


def test_a_case() -> None:
    (lambda cached: cached.cache_clear())(book_material.preservation_rules)
"""

CLEARS_THROUGH_A_LAMBDA_KEPT_IN_A_NAME = """\
from app.services.internalization_room.canon import book_material


def test_a_case() -> None:
    forget = lambda cached: cached.cache_clear()
    forget(book_material.preservation_rules)
"""

CLEARS_THROUGH_A_LAMBDA_GIVEN_TO_MAP = """\
from app.services.internalization_room.canon import book_material


def test_a_case() -> None:
    list(map(lambda cached: cached.cache_clear(), (book_material.preservation_rules,)))
"""

CLEARS_ANOTHER_CACHE_THROUGH_A_LAMBDA = """\
from app.core.config import get_settings


def test_a_case() -> None:
    (lambda cached: cached.cache_clear())(get_settings)
"""

CLEARS_THROUGH_A_FIXTURE_THAT_RETURNS_THE_CACHE = """\
import pytest

from app.services.internalization_room.canon import book_material


@pytest.fixture
def cached():
    return book_material.preservation_rules


def test_a_case(cached) -> None:
    cached.cache_clear()
"""

CLEARS_THROUGH_A_FIXTURE_THAT_YIELDS_A_LOCAL_HOLDING_THE_CACHE = """\
import pytest

from app.services.internalization_room.canon import book_material


@pytest.fixture
def cached():
    held = book_material.preservation_rules
    yield held


def test_a_case(cached) -> None:
    cached.cache_clear()
"""

CLEARS_THROUGH_A_FIXTURE_FED_BY_ANOTHER_FIXTURE = """\
import pytest

from app.services.internalization_room.canon import book_material


@pytest.fixture
def first():
    return book_material.preservation_rules


@pytest.fixture
def second(first):
    return first


def test_a_case(second) -> None:
    second.cache_clear()
"""

CLEARS_THE_FIXTURE_OF_ANOTHER_CACHE = """\
import pytest

from app.core.config import get_settings
from app.services.internalization_room.canon import book_material


@pytest.fixture
def cached():
    return book_material.preservation_rules


@pytest.fixture
def settings():
    return get_settings


def test_a_case(settings) -> None:
    settings.cache_clear()
"""

CLEARS_THROUGH_THE_VALUE_A_FUNCTION_RETURNS = """\
from app.services.internalization_room.canon import book_material


def the_cache():
    return book_material.preservation_rules


def test_a_case() -> None:
    the_cache().cache_clear()
"""

CLEARS_THROUGH_A_NAME_FED_BY_A_FUNCTIONS_VALUE = """\
from app.services.internalization_room.canon import book_material


def the_cache():
    held = book_material.preservation_rules
    return held


def test_a_case() -> None:
    cached = the_cache()
    cached.cache_clear()
"""

CLEARS_THROUGH_A_FUNCTION_THAT_RETURNS_ANOTHERS_VALUE = """\
from app.services.internalization_room.canon import book_material


def the_cache():
    return book_material.preservation_rules


def the_same_cache():
    return the_cache()


def test_a_case() -> None:
    the_same_cache().cache_clear()
"""

CLEARS_THE_VALUE_OF_A_FUNCTION_THAT_RETURNS_ANOTHER_CACHE = """\
from app.core.config import get_settings
from app.services.internalization_room.canon import book_material


def the_cache():
    return book_material.preservation_rules


def the_settings():
    return get_settings


def test_a_case() -> None:
    the_settings().cache_clear()
"""

CLEARS_THROUGH_A_LOCAL_OF_THE_CALLER_HANDED_TO_A_HELPER = """\
from app.services.internalization_room.canon import book_material


def forget(cached) -> None:
    cached.cache_clear()


def test_a_case() -> None:
    cached_local = book_material.preservation_rules
    forget(cached_local)
"""

CLEARS_THROUGH_A_HELPER_CALLED_FROM_A_FUNCTION_INSIDE_THE_CASE = """\
from app.services.internalization_room.canon import book_material


def forget(cached) -> None:
    cached.cache_clear()


def test_a_case() -> None:
    def run() -> None:
        forget(book_material.preservation_rules)

    run()
"""

CLEARS_THROUGH_A_CHAIN_OF_HELPERS_THAT_NAME_THEIR_PARAMETER_ALIKE = """\
from app.services.internalization_room.canon import book_material


def _empty(cached) -> None:
    cached.cache_clear()


def forget(cached) -> None:
    _empty(cached)


def test_a_case() -> None:
    forget(book_material.preservation_rules)
"""

CLEARS_THROUGH_A_CHAIN_OF_HELPERS_HANDED_A_LOCAL_OF_THE_CALLER = """\
from app.services.internalization_room.canon import book_material


def _empty(cached) -> None:
    cached.cache_clear()


def forget(cached) -> None:
    _empty(cached)


def test_a_case() -> None:
    cached = book_material.preservation_rules
    forget(cached)
"""

A_SIBLING_MODULE_IMPORTED_BY_A_DOT = """\
from . import book_material


def test_a_case() -> None:
    book_material.preservation_rules.cache_clear()
"""

A_SUBPACKAGE_IMPORTED_BY_A_DOT = """\
from .canon import book_material


def test_a_case() -> None:
    book_material.preservation_rules.cache_clear()
"""

A_MODULE_IMPORTED_THROUGH_THE_PARENT = """\
from ..canon import book_material


def test_a_case() -> None:
    book_material.preservation_rules.cache_clear()
"""

A_CACHE_IMPORTED_BY_A_DOT_FROM_ITS_MODULE = """\
from .book_material import preservation_rules as the_rules


def test_a_case() -> None:
    the_rules.cache_clear()
"""

# The same source on purpose: the contrast is the package the file sits in, not the text.
A_MODULE_OUTSIDE_THE_ROOM_IMPORTED_BY_A_DOT = A_SIBLING_MODULE_IMPORTED_BY_A_DOT

THE_HELPER_MODULE_THAT_CLEARS_ITS_PARAMETER = """\
def forget(cached) -> None:
    cached.cache_clear()
"""

THE_HELPER_MODULE_THAT_CLEARS_ITS_PARAMETER_IN_A_NESTED_FUNCTION = """\
def forget(cached) -> None:
    def _empty(held) -> None:
        held.cache_clear()

    _empty(cached)
"""

THE_HELPER_MODULE_THAT_CLEARS_ITS_FIRST_PARAMETER_ONLY = """\
def forget(first, second) -> None:
    first.cache_clear()
"""

THE_HELPER_MODULE_THAT_CLEARS_SOMETHING_ELSE = """\
def forget(cached):
    unrelated = 1
    unrelated.cache_clear()
    return cached
"""

THE_CASE_THAT_IMPORTS_THE_HELPER_BY_NAME = """\
from a_helper import forget

from app.services.internalization_room.canon import book_material


def test_a_case() -> None:
    forget(book_material.preservation_rules)
"""

THE_CASE_THAT_IMPORTS_THE_HELPER_MODULE_UNDER_ANOTHER_NAME = """\
import a_helper as helper

from app.services.internalization_room.canon import book_material


def test_a_case() -> None:
    helper.forget(book_material.preservation_rules)
"""

THE_CASE_THAT_IMPORTS_THE_HELPER_UNDER_ANOTHER_NAME = """\
from a_helper import forget as drop

from app.services.internalization_room.canon import book_material


def test_a_case() -> None:
    drop(cached=book_material.preservation_rules)
"""

THE_CASE_THAT_HANDS_THE_CACHE_SECOND = """\
from a_helper import forget

from app.services.internalization_room.canon import book_material


def test_a_case() -> None:
    forget(1, book_material.preservation_rules)
"""

THE_CASE_THAT_HANDS_ANOTHER_CACHE = """\
from a_helper import forget

from app.core.config import get_settings
from app.services.internalization_room.canon import book_material


def test_a_case() -> None:
    assert book_material.preservation_rules
    forget(get_settings)
"""

THE_CLASS_WHOSE_METHOD_CLEARS_ITS_PARAMETER = """\
class Holder:
    def forget(self, cached) -> None:
        cached.cache_clear()
"""

THE_CASE_THAT_CALLS_A_METHOD_ON_AN_INSTANCE = """\
from a_helper import Holder

from app.services.internalization_room.canon import book_material


def test_a_case() -> None:
    holder = Holder()
    holder.forget(book_material.preservation_rules)
"""

THE_CASE_THAT_CALLS_A_METHOD_ON_A_FRESH_INSTANCE = """\
from a_helper import Holder

from app.services.internalization_room.canon import book_material


def test_a_case() -> None:
    Holder().forget(book_material.preservation_rules)
"""

A_CLASS_OF_THE_CASE_WHOSE_METHOD_CLEARS_ITS_PARAMETER = """\
from app.services.internalization_room.canon import book_material


class Holder:
    def forget(self, cached) -> None:
        cached.cache_clear()

    def test_a_case(self) -> None:
        self.forget(book_material.preservation_rules)


def test_another_case() -> None:
    Holder().forget(book_material.preservation_rules)
"""

TWO_CLASSES_WHOSE_METHODS_ARE_CALLED_FORGET = """\
from app.services.internalization_room.canon import book_material


class Quiet:
    def forget(self, cached) -> None:
        return None


class Holder:
    def forget(self, cached) -> None:
        cached.cache_clear()


def test_a_case() -> None:
    Quiet().forget(book_material.preservation_rules)
"""

THE_CLASS_WHOSE_STATIC_METHOD_CLEARS_ITS_PARAMETER = """\
class Holder:
    @staticmethod
    def forget(cached) -> None:
        cached.cache_clear()
"""

THE_CASE_THAT_CALLS_A_STATIC_METHOD_ON_THE_CLASS = """\
from a_helper import Holder

from app.services.internalization_room.canon import book_material


def test_a_case() -> None:
    Holder.forget(book_material.preservation_rules)
"""

THE_CLASS_WHOSE_CLASS_METHOD_CLEARS_ITS_PARAMETER = """\
class Holder:
    @classmethod
    def forget(cls, cached) -> None:
        cached.cache_clear()
"""

THE_CONFTEST_WHOSE_FIXTURE_RETURNS_THE_CACHE = """\
import pytest

from app.services.internalization_room.canon import book_material


@pytest.fixture
def cached():
    return book_material.preservation_rules
"""

THE_CONFTEST_WHOSE_FIXTURE_YIELDS_A_LOCAL_HOLDING_THE_CACHE = """\
import pytest

from app.services.internalization_room.canon import book_material


@pytest.fixture
def cached():
    held = book_material.preservation_rules
    yield held
"""

THE_CONFTEST_WHOSE_FIXTURE_RETURNS_ANOTHER_CACHE = """\
import pytest

from app.core.config import get_settings


@pytest.fixture
def cached():
    return get_settings
"""

THE_CONFTEST_WHOSE_FIXTURE_REQUESTS_A_FIXTURE_IT_DOES_NOT_DEFINE = """\
import pytest


@pytest.fixture
def derived(cached):
    return cached
"""

THE_CASE_THAT_ASKS_FOR_THE_FIXTURE_THAT_REQUESTS_ANOTHER = """\
def test_a_case(derived) -> None:
    derived.cache_clear()
"""

THE_CASE_WHOSE_FIXTURE_REQUESTS_THE_CONFTESTS = """\
import pytest


@pytest.fixture
def second(cached):
    return cached


def test_a_case(second) -> None:
    second.cache_clear()
"""

THE_CONFTEST_WHOSE_FIXTURES_ARE_THE_CACHE_AND_WHAT_REQUESTS_IT = """\
import pytest

from app.services.internalization_room.canon import book_material


@pytest.fixture
def cached():
    return book_material.preservation_rules


@pytest.fixture
def derived(cached):
    return cached
"""

THE_CASE_THAT_ASKS_FOR_THE_FIXTURE = """\
def test_a_case(cached) -> None:
    cached.cache_clear()
"""

THE_CASE_WHOSE_HELPER_IS_HANDED_ANOTHER_CACHE_UNDER_THE_FIXTURES_NAME = """\
from app.core.config import get_settings


def forget(cached) -> None:
    cached.cache_clear()


def test_a_case() -> None:
    forget(get_settings)
"""

THE_CASE_THAT_HANDS_THE_FIXTURE_TO_A_HELPER = """\
def forget(cached) -> None:
    cached.cache_clear()


def test_a_case(cached) -> None:
    forget(cached)
"""

THE_CASE_THAT_DEFINES_THE_FIXTURE_A_CONFTEST_FIXTURE_REQUESTS = """\
import pytest

from app.services.internalization_room.canon import book_material


@pytest.fixture
def cached():
    return book_material.preservation_rules


def test_a_case(derived) -> None:
    derived.cache_clear()
"""

THE_CASE_THAT_ASKS_FOR_THE_FIXTURE_IN_A_CLASS = """\
class TestACase:
    def test_a_case(self, cached) -> None:
        cached.cache_clear()
"""

THE_CASE_WHOSE_NESTED_HELPER_IS_HANDED_ANOTHER_CACHE_UNDER_THE_FIXTURES_NAME = """\
from app.core.config import get_settings


def test_a_case() -> None:
    def forget(cached) -> None:
        cached.cache_clear()

    forget(get_settings)
"""

THE_CASE_WHOSE_LAMBDA_IS_HANDED_ANOTHER_CACHE_UNDER_THE_FIXTURES_NAME = """\
from app.core.config import get_settings


def test_a_case() -> None:
    (lambda cached: cached.cache_clear())(get_settings)
"""

THE_CASE_THAT_ASKS_FOR_THE_FIXTURE_IN_A_NESTED_CLASS = """\
class TestOuter:
    class TestInner:
        def test_a_case(self, cached) -> None:
            cached.cache_clear()
"""

THE_CASE_THAT_ASKS_FOR_ANOTHER_NAME = """\
def test_a_case(other) -> None:
    other.cache_clear()
"""

THE_CASE_THAT_DEFINES_THE_FIXTURE_ITSELF = """\
import pytest

from app.core.config import get_settings


@pytest.fixture
def cached():
    return get_settings


def test_a_case(cached) -> None:
    cached.cache_clear()
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

A_SPY_THE_CASE_CALLS_BY_NAME = """\
from app.services.internalization_room.canon import book_material


def test_a_case(monkeypatch) -> None:
    cache = book_material.preservation_rules
    empty_it = cache.cache_clear

    def empty_and_note() -> None:
        empty_it()

    monkeypatch.setattr(cache, "cache_clear", empty_and_note)
    empty_and_note()
"""

A_WRAPPER_NO_ONE_INSTALLED = """\
from app.services.internalization_room.canon import book_material


def test_a_case() -> None:
    cache = book_material.preservation_rules
    empty_it = cache.cache_clear

    def empty_and_note() -> None:
        empty_it()
"""

CLEARS_THE_SIBLING_OF_A_TUPLE_TARGET = """\
from app.services.internalization_room.canon import book_material


def test_a_case() -> None:
    cached, other = book_material.preservation_rules, 1
    other.cache_clear()
"""

CLEARS_THE_SIBLING_OF_A_PARAMETRIZED_ARGUMENT = """\
import pytest

from app.services.internalization_room.canon import book_material


@pytest.mark.parametrize(("cached", "other"), [(book_material.preservation_rules, 1)])
def test_a_case(cached, other) -> None:
    other.cache_clear()
"""

CLEARS_A_NAME_UNPACKED_FROM_A_CACHE = """\
from app.services.internalization_room.canon import book_material


def test_a_case() -> None:
    first, second = book_material.preservation_rules
    second.cache_clear()
"""

CLEARS_A_NAME_UNPACKED_FROM_A_LONGER_TUPLE = """\
from app.services.internalization_room.canon import book_material


def test_a_case() -> None:
    first, second = book_material.preservation_rules, 1, 2
    second.cache_clear()
"""

CLEARS_A_NAME_UNPACKED_FROM_A_TUPLE_WITH_A_STAR = """\
from app.services.internalization_room.canon import book_material


def test_a_case() -> None:
    first, second = *book_material.preservation_rules, 1
    second.cache_clear()
"""

CLEARS_A_PARAMETRIZED_ARGUMENT_OF_VALUES_NOT_SEEN_ROW_BY_ROW = """\
import pytest

from app.services.internalization_room.canon import book_material


@pytest.mark.parametrize(("cached", "other"), book_material.preservation_rules)
def test_a_case(cached, other) -> None:
    other.cache_clear()
"""

TWO_CASES_EACH_DEFINE_A_HELPER_OF_ONE_NAME = """\
from app.core.config import get_settings
from app.services.internalization_room.canon import book_material


def test_a_case() -> None:
    def forget(cached) -> None:
        cached.cache_clear()

    forget(book_material.preservation_rules)


def test_another_case() -> None:
    def forget(cached) -> None:
        cached.cache_clear()

    forget(get_settings)
"""

A_METHOD_AND_A_HELPER_OF_ONE_NAME = """\
from app.services.internalization_room.canon import book_material


def forget(cached) -> None:
    cached.cache_clear()


class Holder:
    def forget(self, cached) -> None:
        cached.cache_clear()


def test_a_case() -> None:
    forget(book_material.preservation_rules)
"""

CLEARS_WHAT_A_HELPER_IS_HANDED_UNDER_THE_NAME_OF_ONE_OF_ITS_OWN_LOCALS = """\
from app.core.config import get_settings
from app.services.internalization_room.canon import book_material


def forget(cached) -> None:
    held = book_material.preservation_rules
    cached.cache_clear()


def test_a_case() -> None:
    held = get_settings
    forget(held)
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


THE_CASE_WHOSE_CLASS_DEFINES_THE_FIXTURE_ITS_METHOD_ASKS_FOR = """\
import pytest

from app.services.internalization_room.canon import book_material


class TestACase:
    @pytest.fixture
    def cached(self):
        return book_material.preservation_rules

    def test_a_case(self, cached) -> None:
        cached.cache_clear()
"""

THE_CASE_WHOSE_CLASS_FIXTURE_IS_ASKED_FOR_BY_A_TEST_OF_THE_MODULE_TOO = """\
import pytest

from app.services.internalization_room.canon import book_material


class TestACase:
    @pytest.fixture
    def cached(self):
        return book_material.preservation_rules

    def test_a_case(self, cached) -> None:
        cached.cache_clear()


def test_another_case(cached) -> None:
    cached.cache_clear()
"""

THE_CASE_WHOSE_CLASS_FIXTURE_IS_ASKED_FOR_BY_A_METHOD_OF_ANOTHER_CLASS_TOO = """\
import pytest

from app.services.internalization_room.canon import book_material


class TestACase:
    @pytest.fixture
    def cached(self):
        return book_material.preservation_rules

    def test_a_case(self, cached) -> None:
        cached.cache_clear()


class TestAnotherCase:
    def test_another_case(self, cached) -> None:
        cached.cache_clear()
"""

THE_CASE_WHOSE_METHOD_ASKS_FOR_THE_FIXTURE_OF_ITS_BASE_CLASS = """\
import pytest

from app.services.internalization_room.canon import book_material


class Base:
    @pytest.fixture
    def cached(self):
        return book_material.preservation_rules


class TestACase(Base):
    def test_a_case(self, cached) -> None:
        cached.cache_clear()
"""

THE_CASE_WHOSE_NESTED_CLASS_ASKS_FOR_THE_FIXTURE_OF_THE_CLASS_AROUND_IT = """\
import pytest

from app.services.internalization_room.canon import book_material


class TestOuter:
    @pytest.fixture
    def cached(self):
        return book_material.preservation_rules

    class TestInner:
        def test_a_case(self, cached) -> None:
            cached.cache_clear()
"""


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


def _cache_declared_by(node: ast.AST, named: set[ast.AST]) -> str | None:
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        kinds = {_decorator_name(decorator) for decorator in node.decorator_list}
        return node.name if kinds & CACHES else None
    if isinstance(node, ast.Assign | ast.AnnAssign) and _built_by_a_call(node.value):
        target = node.targets[0] if isinstance(node, ast.Assign) else node.target
        return ast.unparse(target)
    if isinstance(node, ast.Call) and node not in named and _built_by_a_call(node):
        return ast.unparse(node)
    return None


def _named_or_decorating(tree: ast.AST) -> set[ast.AST]:
    named: set[ast.AST] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign | ast.AnnAssign) and node.value is not None:
            named.add(node.value)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            named.update(node.decorator_list)
    return named


def _unlisted_caches(root: Path, listed: set[str]) -> list[str]:
    unlisted: list[str] = []
    for module in sorted(root.rglob("*.py")):
        relative = module.relative_to(root.parent)
        dotted = ".".join(relative.with_suffix("").parts)
        tree = ast.parse(module.read_text(encoding="utf-8"))
        named = _named_or_decorating(tree)
        for node in ast.walk(tree):
            name = _cache_declared_by(node, named)
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

A_CACHE_BUILT_BY_A_CALL_AND_RETURNED = """\
from functools import lru_cache


def _read() -> str:
    return "the map"


def keep_it():
    return lru_cache(maxsize=1)(_read)
"""

A_CACHE_BUILT_BY_A_CALL_AND_HANDED_ON = """\
import functools


def _read() -> str:
    return "the map"


register(functools.cache(_read))
"""

A_CACHE_BUILT_BY_A_CALL_AND_LEFT_ALONE = """\
from functools import lru_cache


def _read() -> str:
    return "the map"


lru_cache(maxsize=1)(_read)
"""

A_DECORATOR_BUILT_BY_A_CALL_ON_A_FUNCTION = """\
from functools import lru_cache

SIZE = 1


@lru_cache(SIZE)
def read_the_map_again() -> str:
    return "the map"
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
        (CLEARS_THROUGH_A_BOUND_CLEAR_KEPT_IN_A_NAME, 7),
        (CLEARS_THROUGH_A_BOUND_CLEAR_GOT_BY_GETATTR, 6),
        (CLEARS_THROUGH_AN_ATTRIBUTE_TARGET, 9),
        (CLEARS_THROUGH_A_LAMBDA_CALLED_AT_THE_TOP_OF_THE_MODULE, 3),
        (CLEARS_THROUGH_A_LAMBDA_CALLED_IN_PLACE, 5),
        (CLEARS_THROUGH_A_LAMBDA_KEPT_IN_A_NAME, 5),
        (CLEARS_THROUGH_A_LAMBDA_GIVEN_TO_MAP, 5),
        (CLEARS_THROUGH_A_FIXTURE_THAT_RETURNS_THE_CACHE, 12),
        (CLEARS_THROUGH_A_FIXTURE_THAT_YIELDS_A_LOCAL_HOLDING_THE_CACHE, 13),
        (CLEARS_THROUGH_A_FIXTURE_FED_BY_ANOTHER_FIXTURE, 17),
        (CLEARS_THROUGH_THE_VALUE_A_FUNCTION_RETURNS, 9),
        (CLEARS_THROUGH_A_NAME_FED_BY_A_FUNCTIONS_VALUE, 11),
        (CLEARS_THROUGH_A_FUNCTION_THAT_RETURNS_ANOTHERS_VALUE, 13),
        (CLEARS_THROUGH_A_LOCAL_OF_THE_CALLER_HANDED_TO_A_HELPER, 5),
        (CLEARS_THROUGH_A_HELPER_CALLED_FROM_A_FUNCTION_INSIDE_THE_CASE, 5),
        (CLEARS_THROUGH_A_CHAIN_OF_HELPERS_THAT_NAME_THEIR_PARAMETER_ALIKE, 5),
        (CLEARS_THROUGH_A_CHAIN_OF_HELPERS_HANDED_A_LOCAL_OF_THE_CALLER, 5),
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
        "cleared by a bound cache_clear kept in a name",
        "cleared by a bound cache_clear got by getattr",
        "named by an attribute target",
        "named by the parameter of a lambda called at the top of the module",
        "named by the parameter of a lambda called in place",
        "named by the parameter of a lambda kept in a name",
        "named by the parameter of a lambda given to map",
        "named by a fixture that returns it",
        "named by a fixture that yields a local holding it",
        "named by a fixture that another fixture feeds",
        "named by the value a function returns",
        "named by a name a function's value feeds",
        "named by a function that returns another's value",
        "named by a local of the caller handed to a helper",
        "named by a helper called from a function inside the case",
        "named by a chain of helpers that name their parameter alike",
        "named by a chain of helpers handed a local of the caller",
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


@pytest.mark.parametrize(
    ("source", "line", "name"),
    [
        (A_CACHE_BUILT_BY_A_CALL_AND_RETURNED, 9, "lru_cache(maxsize=1)(_read)"),
        (A_CACHE_BUILT_BY_A_CALL_AND_HANDED_ON, 8, "functools.cache(_read)"),
        (A_CACHE_BUILT_BY_A_CALL_AND_LEFT_ALONE, 8, "lru_cache(maxsize=1)(_read)"),
    ],
    ids=["returned", "handed to a call", "left alone"],
)
def test_a_cache_built_by_a_call_and_kept_under_no_name_is_reported_where_it_is(
    tmp_path: Path, source: str, line: int, name: str
) -> None:
    app = _an_app_holding(tmp_path, "services/a_new_cache.py", source)

    (reported,) = _unlisted_caches(app, set())

    assert reported.startswith(
        f"app/services/a_new_cache.py:{line} `{name}` is a cache the harness does not know. "
    )


def test_a_decorator_built_by_a_call_is_one_cache_and_not_two(tmp_path: Path) -> None:
    app = _an_app_holding(
        tmp_path, "services/a_new_cache.py", A_DECORATOR_BUILT_BY_A_CALL_ON_A_FUNCTION
    )

    (reported,) = _unlisted_caches(app, set())

    assert reported.startswith("app/services/a_new_cache.py:7 `read_the_map_again` is a cache ")


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


@pytest.mark.parametrize(
    ("source", "line"),
    [(A_SPY_THE_CASE_CALLS_BY_NAME, 9), (A_WRAPPER_NO_ONE_INSTALLED, 9)],
    ids=["a spy the case calls by name", "a wrapper no one installed"],
)
def test_a_wrapper_that_is_called_or_never_installed_is_a_clear_by_hand(
    tmp_path: Path, source: str, line: int
) -> None:
    of_the_canon, of_something_else = _the_clears_in(
        _planted(tmp_path, source), _the_caches_the_harness_forgets()
    )

    assert (of_the_canon, of_something_else) == ([line], [])


@pytest.mark.parametrize(
    ("at", "source", "of_the_canon", "of_something_else"),
    [
        (
            "services/internalization_room/canon/a_case.py",
            A_SIBLING_MODULE_IMPORTED_BY_A_DOT,
            [5],
            [],
        ),
        ("services/internalization_room/a_case.py", A_SUBPACKAGE_IMPORTED_BY_A_DOT, [5], []),
        (
            "services/internalization_room/other/a_case.py",
            A_MODULE_IMPORTED_THROUGH_THE_PARENT,
            [5],
            [],
        ),
        (
            "services/internalization_room/canon/a_case.py",
            A_CACHE_IMPORTED_BY_A_DOT_FROM_ITS_MODULE,
            [5],
            [],
        ),
        ("services/a_case.py", A_MODULE_OUTSIDE_THE_ROOM_IMPORTED_BY_A_DOT, [], [5]),
    ],
    ids=[
        "a sibling module imported by a dot",
        "a subpackage imported by a dot",
        "a module imported through the parent",
        "a cache imported by a dot from its module",
        "a module outside the room imported by a dot",
    ],
)
def test_a_relative_import_is_read_as_the_module_it_names_from_where_the_file_is(
    tmp_path: Path, at: str, source: str, of_the_canon: list[int], of_something_else: list[int]
) -> None:
    app = _an_app_holding(tmp_path, at, source)

    clears = _the_clears_in(app / at, _the_caches_the_harness_forgets(), tmp_path)

    assert clears == (of_the_canon, of_something_else)


def _a_case_beside_its_helper(tmp_path: Path, helper: str, source: str) -> Path:
    (tmp_path / "a_helper.py").write_text(helper, encoding="utf-8")
    return _planted(tmp_path, source)


@pytest.mark.parametrize(
    ("helper", "source", "of_the_canon"),
    [
        (
            THE_HELPER_MODULE_THAT_CLEARS_ITS_PARAMETER,
            THE_CASE_THAT_IMPORTS_THE_HELPER_BY_NAME,
            [7],
        ),
        (
            THE_HELPER_MODULE_THAT_CLEARS_ITS_PARAMETER,
            THE_CASE_THAT_IMPORTS_THE_HELPER_MODULE_UNDER_ANOTHER_NAME,
            [7],
        ),
        (
            THE_HELPER_MODULE_THAT_CLEARS_ITS_PARAMETER,
            THE_CASE_THAT_IMPORTS_THE_HELPER_UNDER_ANOTHER_NAME,
            [7],
        ),
        (
            THE_HELPER_MODULE_THAT_CLEARS_ITS_PARAMETER_IN_A_NESTED_FUNCTION,
            THE_CASE_THAT_IMPORTS_THE_HELPER_BY_NAME,
            [7],
        ),
        (
            THE_HELPER_MODULE_THAT_CLEARS_ITS_FIRST_PARAMETER_ONLY,
            THE_CASE_THAT_HANDS_THE_CACHE_SECOND,
            [],
        ),
        (
            THE_HELPER_MODULE_THAT_CLEARS_SOMETHING_ELSE,
            THE_CASE_THAT_IMPORTS_THE_HELPER_BY_NAME,
            [],
        ),
        (
            THE_HELPER_MODULE_THAT_CLEARS_ITS_PARAMETER,
            THE_CASE_THAT_HANDS_ANOTHER_CACHE,
            [],
        ),
    ],
    ids=[
        "a helper imported by name",
        "a helper reached through its module under another name",
        "a helper imported under another name, the cache given by keyword",
        "a helper that hands its parameter to a nested function that clears it",
        "a cache handed to the parameter the helper leaves alone",
        "a helper that clears something else",
        "a helper handed another cache",
    ],
)
def test_a_helper_of_another_module_that_clears_its_parameter_is_a_clear_at_the_call(
    tmp_path: Path, helper: str, source: str, of_the_canon: list[int]
) -> None:
    module = _a_case_beside_its_helper(tmp_path, helper, source)

    clears = _the_clears_in(module, _the_caches_the_harness_forgets(), tmp_path)

    assert clears == (of_the_canon, [])


@pytest.mark.parametrize(
    ("helper", "source", "of_the_canon", "of_something_else"),
    [
        (
            THE_CLASS_WHOSE_METHOD_CLEARS_ITS_PARAMETER,
            THE_CASE_THAT_CALLS_A_METHOD_ON_AN_INSTANCE,
            [8],
            [],
        ),
        (
            THE_CLASS_WHOSE_METHOD_CLEARS_ITS_PARAMETER,
            THE_CASE_THAT_CALLS_A_METHOD_ON_A_FRESH_INSTANCE,
            [7],
            [],
        ),
        (
            THE_CLASS_WHOSE_STATIC_METHOD_CLEARS_ITS_PARAMETER,
            THE_CASE_THAT_CALLS_A_STATIC_METHOD_ON_THE_CLASS,
            [7],
            [],
        ),
        (
            THE_CLASS_WHOSE_CLASS_METHOD_CLEARS_ITS_PARAMETER,
            THE_CASE_THAT_CALLS_A_STATIC_METHOD_ON_THE_CLASS,
            [7],
            [],
        ),
        ("", A_CLASS_OF_THE_CASE_WHOSE_METHOD_CLEARS_ITS_PARAMETER, [9, 13], [6]),
        ("", TWO_CLASSES_WHOSE_METHODS_ARE_CALLED_FORGET, [], [11]),
    ],
    ids=[
        "a method called on an instance of an imported class",
        "a method called on a fresh instance of an imported class",
        "a static method called on the class, which has no receiver",
        "a class method called on the class, whose receiver is the class",
        "a method of a class of the case, through self and through an instance",
        "two classes whose methods share a name",
    ],
)
def test_a_method_that_clears_its_parameter_is_a_clear_at_the_call(
    tmp_path: Path, helper: str, source: str, of_the_canon: list[int], of_something_else: list[int]
) -> None:
    module = _a_case_beside_its_helper(tmp_path, helper, source)

    clears = _the_clears_in(module, _the_caches_the_harness_forgets(), tmp_path)

    assert clears == (of_the_canon, of_something_else)


@pytest.mark.parametrize(
    ("source", "of_the_canon", "of_something_else"),
    [
        (CLEARS_THE_SIBLING_OF_A_TUPLE_TARGET, [], [6]),
        (CLEARS_THE_SIBLING_OF_A_PARAMETRIZED_ARGUMENT, [], [8]),
        (CLEARS_THE_SIBLING_OF_AN_ATTRIBUTE_TARGET, [], [10]),
        (CLEARS_ANOTHER_CACHE_THROUGH_A_LAMBDA, [], [5]),
        (CLEARS_THE_FIXTURE_OF_ANOTHER_CACHE, [], [18]),
        (CLEARS_THE_VALUE_OF_A_FUNCTION_THAT_RETURNS_ANOTHER_CACHE, [], [14]),
        (CLEARS_A_NAME_UNPACKED_FROM_A_CACHE, [6], []),
        (CLEARS_A_NAME_UNPACKED_FROM_A_LONGER_TUPLE, [6], []),
        (CLEARS_A_NAME_UNPACKED_FROM_A_TUPLE_WITH_A_STAR, [6], []),
        (CLEARS_A_PARAMETRIZED_ARGUMENT_OF_VALUES_NOT_SEEN_ROW_BY_ROW, [8], []),
        (TWO_CASES_EACH_DEFINE_A_HELPER_OF_ONE_NAME, [7], [14]),
        (A_METHOD_AND_A_HELPER_OF_ONE_NAME, [5], [10]),
        (CLEARS_WHAT_A_HELPER_IS_HANDED_UNDER_THE_NAME_OF_ONE_OF_ITS_OWN_LOCALS, [], [7]),
    ],
    ids=[
        "the sibling of a tuple target",
        "the sibling of a parametrized argument",
        "the sibling of an attribute target",
        "another cache through a lambda",
        "the fixture of another cache",
        "the value of a function that returns another cache",
        "a name unpacked from a cache, shapes not paired",
        "a name unpacked from a longer tuple",
        "a name unpacked from a tuple with a star",
        "parametrized values not seen row by row",
        "two cases each define a helper of one name",
        "a method and a helper of one name",
        "what a helper is handed under the name of one of its own locals",
    ],
)
def test_a_name_is_fed_by_its_own_element_where_the_shapes_pair_and_by_the_whole_where_they_do_not(
    tmp_path: Path, source: str, of_the_canon: list[int], of_something_else: list[int]
) -> None:
    clears = _the_clears_in(_planted(tmp_path, source), _the_caches_the_harness_forgets())

    assert clears == (of_the_canon, of_something_else)


@pytest.mark.parametrize(
    ("conftest", "source", "of_the_canon", "of_something_else"),
    [
        (THE_CONFTEST_WHOSE_FIXTURE_RETURNS_THE_CACHE, THE_CASE_THAT_ASKS_FOR_THE_FIXTURE, [2], []),
        (
            THE_CONFTEST_WHOSE_FIXTURE_YIELDS_A_LOCAL_HOLDING_THE_CACHE,
            THE_CASE_THAT_ASKS_FOR_THE_FIXTURE,
            [2],
            [],
        ),
        (
            THE_CONFTEST_WHOSE_FIXTURE_RETURNS_THE_CACHE,
            THE_CASE_THAT_ASKS_FOR_ANOTHER_NAME,
            [],
            [2],
        ),
        (
            THE_CONFTEST_WHOSE_FIXTURE_RETURNS_THE_CACHE,
            THE_CASE_THAT_DEFINES_THE_FIXTURE_ITSELF,
            [],
            [12],
        ),
        (
            THE_CONFTEST_WHOSE_FIXTURE_RETURNS_THE_CACHE,
            THE_CASE_WHOSE_FIXTURE_REQUESTS_THE_CONFTESTS,
            [10],
            [],
        ),
        (
            THE_CONFTEST_WHOSE_FIXTURE_RETURNS_THE_CACHE,
            THE_CASE_WHOSE_HELPER_IS_HANDED_ANOTHER_CACHE_UNDER_THE_FIXTURES_NAME,
            [],
            [5],
        ),
        (
            THE_CONFTEST_WHOSE_FIXTURE_RETURNS_THE_CACHE,
            THE_CASE_THAT_HANDS_THE_FIXTURE_TO_A_HELPER,
            [2],
            [],
        ),
        (
            THE_CONFTEST_WHOSE_FIXTURE_RETURNS_THE_CACHE,
            THE_CASE_THAT_ASKS_FOR_THE_FIXTURE_IN_A_CLASS,
            [3],
            [],
        ),
        (
            THE_CONFTEST_WHOSE_FIXTURE_RETURNS_THE_CACHE,
            THE_CASE_THAT_ASKS_FOR_THE_FIXTURE_IN_A_NESTED_CLASS,
            [4],
            [],
        ),
        (
            THE_CONFTEST_WHOSE_FIXTURE_REQUESTS_A_FIXTURE_IT_DOES_NOT_DEFINE,
            THE_CASE_THAT_DEFINES_THE_FIXTURE_A_CONFTEST_FIXTURE_REQUESTS,
            [12],
            [],
        ),
        (
            THE_CONFTEST_WHOSE_FIXTURE_RETURNS_THE_CACHE,
            THE_CASE_WHOSE_NESTED_HELPER_IS_HANDED_ANOTHER_CACHE_UNDER_THE_FIXTURES_NAME,
            [],
            [6],
        ),
        (
            THE_CONFTEST_WHOSE_FIXTURE_RETURNS_THE_CACHE,
            THE_CASE_WHOSE_LAMBDA_IS_HANDED_ANOTHER_CACHE_UNDER_THE_FIXTURES_NAME,
            [],
            [5],
        ),
    ],
    ids=[
        "a fixture that returns the cache",
        "a fixture that yields a local holding the cache",
        "a case that asks for another name",
        "a case that defines the fixture itself",
        "a fixture of the case that requests the conftest's",
        "a helper that is handed another cache under the fixture's name",
        "a case that hands the fixture to a helper",
        "a test method of a class that asks for the fixture",
        "a test method of a class nested in a class that asks for the fixture",
        "a conftest fixture that requests a fixture the case defines",
        "a nested helper that is handed another cache under the fixture's name",
        "a lambda that is handed another cache under the fixture's name",
    ],
)
def test_a_fixture_of_the_conftest_beside_the_case_feeds_the_parameter_of_its_name(
    tmp_path: Path,
    conftest: str,
    source: str,
    of_the_canon: list[int],
    of_something_else: list[int],
) -> None:
    (tmp_path / "conftest.py").write_text(conftest, encoding="utf-8")
    module = _planted(tmp_path, source)

    clears = _the_clears_in(module, _the_caches_the_harness_forgets(), tmp_path)

    assert clears == (of_the_canon, of_something_else)


def test_a_fixture_of_a_conftest_above_the_case_feeds_the_parameter_of_its_name(
    tmp_path: Path,
) -> None:
    (tmp_path / "conftest.py").write_text(
        THE_CONFTEST_WHOSE_FIXTURE_RETURNS_THE_CACHE, encoding="utf-8"
    )
    subdirectory = tmp_path / "test_a_subdirectory"
    subdirectory.mkdir()
    module = _planted(subdirectory, THE_CASE_THAT_ASKS_FOR_THE_FIXTURE)

    clears = _the_clears_in(module, _the_caches_the_harness_forgets(), tmp_path)

    assert clears == ([2], [])


def test_a_conftest_fixture_that_requests_one_of_a_conftest_above_is_followed_to_the_clear(
    tmp_path: Path,
) -> None:
    (tmp_path / "conftest.py").write_text(
        THE_CONFTEST_WHOSE_FIXTURE_RETURNS_THE_CACHE, encoding="utf-8"
    )
    subdirectory = tmp_path / "test_a_subdirectory"
    subdirectory.mkdir()
    (subdirectory / "conftest.py").write_text(
        THE_CONFTEST_WHOSE_FIXTURE_REQUESTS_A_FIXTURE_IT_DOES_NOT_DEFINE, encoding="utf-8"
    )
    module = _planted(subdirectory, THE_CASE_THAT_ASKS_FOR_THE_FIXTURE_THAT_REQUESTS_ANOTHER)

    clears = _the_clears_in(module, _the_caches_the_harness_forgets(), tmp_path)

    assert clears == ([2], [])


def test_a_conftest_fixture_takes_what_it_requests_from_a_conftest_nearer_than_its_own(
    tmp_path: Path,
) -> None:
    (tmp_path / "conftest.py").write_text(
        THE_CONFTEST_WHOSE_FIXTURE_REQUESTS_A_FIXTURE_IT_DOES_NOT_DEFINE, encoding="utf-8"
    )
    subdirectory = tmp_path / "test_a_subdirectory"
    subdirectory.mkdir()
    (subdirectory / "conftest.py").write_text(
        THE_CONFTEST_WHOSE_FIXTURE_RETURNS_THE_CACHE, encoding="utf-8"
    )
    module = _planted(subdirectory, THE_CASE_THAT_ASKS_FOR_THE_FIXTURE_THAT_REQUESTS_ANOTHER)

    clears = _the_clears_in(module, _the_caches_the_harness_forgets(), tmp_path)

    assert clears == ([2], [])


def test_a_conftest_fixture_takes_what_it_requests_from_the_nearest_definition_of_the_name(
    tmp_path: Path,
) -> None:
    (tmp_path / "conftest.py").write_text(
        THE_CONFTEST_WHOSE_FIXTURES_ARE_THE_CACHE_AND_WHAT_REQUESTS_IT, encoding="utf-8"
    )
    subdirectory = tmp_path / "test_a_subdirectory"
    subdirectory.mkdir()
    (subdirectory / "conftest.py").write_text(
        THE_CONFTEST_WHOSE_FIXTURE_RETURNS_ANOTHER_CACHE, encoding="utf-8"
    )
    module = _planted(subdirectory, THE_CASE_THAT_ASKS_FOR_THE_FIXTURE_THAT_REQUESTS_ANOTHER)

    clears = _the_clears_in(module, _the_caches_the_harness_forgets(), tmp_path)

    assert clears == ([], [2])


def test_a_nearer_conftest_fixture_of_the_same_name_shadows_the_one_above(
    tmp_path: Path,
) -> None:
    (tmp_path / "conftest.py").write_text(
        THE_CONFTEST_WHOSE_FIXTURE_RETURNS_THE_CACHE, encoding="utf-8"
    )
    subdirectory = tmp_path / "test_a_subdirectory"
    subdirectory.mkdir()
    (subdirectory / "conftest.py").write_text(
        THE_CONFTEST_WHOSE_FIXTURE_RETURNS_ANOTHER_CACHE, encoding="utf-8"
    )
    module = _planted(subdirectory, THE_CASE_THAT_ASKS_FOR_THE_FIXTURE)

    clears = _the_clears_in(module, _the_caches_the_harness_forgets(), tmp_path)

    assert clears == ([], [2])


def test_a_conftest_above_the_root_is_not_read(tmp_path: Path) -> None:
    (tmp_path / "conftest.py").write_text(
        THE_CONFTEST_WHOSE_FIXTURE_RETURNS_THE_CACHE, encoding="utf-8"
    )
    subdirectory = tmp_path / "tests" / "test_a_subdirectory"
    subdirectory.mkdir(parents=True)
    module = _planted(subdirectory, THE_CASE_THAT_ASKS_FOR_THE_FIXTURE)

    clears = _the_clears_in(module, _the_caches_the_harness_forgets(), tmp_path / "tests")

    assert clears == ([], [2])


@pytest.mark.parametrize(
    ("source", "of_the_canon", "of_something_else"),
    [
        (THE_CASE_WHOSE_CLASS_DEFINES_THE_FIXTURE_ITS_METHOD_ASKS_FOR, [12], []),
        (THE_CASE_WHOSE_CLASS_FIXTURE_IS_ASKED_FOR_BY_A_TEST_OF_THE_MODULE_TOO, [12], [16]),
        (THE_CASE_WHOSE_CLASS_FIXTURE_IS_ASKED_FOR_BY_A_METHOD_OF_ANOTHER_CLASS_TOO, [12], [17]),
        (THE_CASE_WHOSE_METHOD_ASKS_FOR_THE_FIXTURE_OF_ITS_BASE_CLASS, [14], []),
        (THE_CASE_WHOSE_NESTED_CLASS_ASKS_FOR_THE_FIXTURE_OF_THE_CLASS_AROUND_IT, [13], []),
    ],
    ids=[
        "a method of the class that asks for the class's fixture",
        "a test of the module that asks for the name of the class's fixture",
        "a method of another class that asks for the name of the class's fixture",
        "a method of a subclass that asks for the fixture of its base class",
        "a method of a nested class that asks for the fixture of the class around it",
    ],
)
def test_a_fixture_defined_in_a_class_feeds_the_methods_that_can_reach_it(
    tmp_path: Path, source: str, of_the_canon: list[int], of_something_else: list[int]
) -> None:
    clears = _the_clears_in(_planted(tmp_path, source), _the_caches_the_harness_forgets())

    assert clears == (of_the_canon, of_something_else)


def test_a_cache_listed_from_outside_the_room_is_one_the_harness_forgets_by_its_own_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        canon_harness,
        "THE_CACHES_THAT_READ_THE_CANON_FROM_OUTSIDE_IT",
        ("app.core.config.get_settings",),
    )

    assert "app.core.config.get_settings" in _the_caches_the_harness_forgets()


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
