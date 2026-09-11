"""**No router in this module touches the database** — [ADR 0009], as a property of the tree.

``docs/shema.md`` §3.3 reads the layering rule three lines long: nothing in ``app/api/shema/``
issues a query, everything in ``app/services/shema/`` does, and nothing in the service package
imports ``fastapi``. BE-05's DoD asks for the first of those and this file checks all three,
because the two it did not ask for are what stop the first from being satisfied by moving the
query one file sideways.

**Why a scan and not a review.** The rule is not *the handlers we have written are careful* —
it is that a handler cannot be written any other way and survive CI. A router that grows a
``WHERE`` for one endpoint is the sibling's own recorded defect (``docs/resource_requests.md``),
and it arrives by somebody in a hurry rather than by somebody disagreeing. This is the same
mechanism ``test_privacy_owners.py`` uses for the guarded columns and ``_scope.py`` for the
module's only ``select(ShemaProject)``: a rule applied per endpoint is a rule the next endpoint
forgets; a glob is not.

**Taking a session and passing it on is not touching the database**, and the distinction is the
whole of the rule. ``Db`` is declared in ``_deps.py`` and handed to a service, which is how
every router in this repository reaches one; what a router may not do is *use* it — execute,
scalar, commit — or build a statement of its own.

[ADR 0009]: ../../docs/adr/0009-routers-never-touch-the-database.md
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
API_PACKAGE = REPO_ROOT / "app" / "api" / "shema"
SERVICE_PACKAGE = REPO_ROOT / "app" / "services" / "shema"

#: What issuing a query looks like in the abstract syntax, rather than in prose. ``select``,
#: ``insert``, ``update`` and ``delete`` build a statement; ``execute``, ``scalar``,
#: ``scalars``, ``commit``, ``flush`` and ``refresh`` run one. A file that does none of these
#: has no way to reach the database that is not an import somebody has to explain.
QUERY_CALLS = frozenset(
    {
        "select",
        "insert",
        "update",
        "delete",
        "execute",
        "scalar",
        "scalar_one",
        "scalar_one_or_none",
        "scalars",
        "commit",
        "flush",
        "refresh",
        "add",
        "add_all",
    }
)

#: Modules a router has no business importing. ``sqlalchemy`` is the statement builder and
#: ``app.db.models`` is the table layer; a router that needs either is a router about to run a
#: query, or one constructing a table model, which ADR 0009 refuses in the same sentence.
FORBIDDEN_IN_ROUTERS = ("sqlalchemy", "app.db.models")

#: The one file exempt from the import rule, and the reason it is one file. ``_deps.py``
#: declares the annotations every router in the module reaches a session and an account
#: through — ``Db`` is an ``AsyncSession`` and ``CurrentUser`` is a ``User`` — so naming those
#: two types is the whole of what it does with them. A second name here would be somebody
#: moving a query rather than a type, which is the edit this list makes visible in a diff.
DECLARES_THE_ANNOTATIONS = frozenset({"_deps.py"})


def _called_names(tree: ast.AST) -> set[str]:
    """Every function and method name called in a module.

    Names and not resolved targets: ``db.execute(...)`` and ``session.execute(...)`` are the
    same defect, and resolving which object a name is bound to would be an import graph this
    test does not need in order to say *no*.
    """
    called: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute):
            called.add(node.func.attr)
        elif isinstance(node.func, ast.Name):
            called.add(node.func.id)
    return called


def _imported_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    return modules


def test_no_router_in_this_module_issues_a_query() -> None:
    """**The DoD's fifth line.** Query logic lives in ``app/services/``, entirely.

    ``_deps.py`` is not exempt and does not need to be: it declares the ``Db`` annotation and
    calls a service for the scope, which is exactly the shape the rule wants.
    """
    offenders = {}
    for source in sorted(API_PACKAGE.glob("*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        reached = _called_names(tree) & QUERY_CALLS
        if reached:
            offenders[str(source.relative_to(REPO_ROOT))] = sorted(reached)

    assert offenders == {}, (
        f"a router reaches the database, which is the rule the next router copies: {offenders}"
    )


def test_no_router_in_this_module_imports_the_statement_builder_or_the_table_layer() -> None:
    """The other half: a router that cannot name a table cannot grow a query later.

    Catching the import rather than only the call is what makes the check hold against the
    spelling nobody thought of — a statement assembled into a variable and handed to a service
    reads as no call at all. :data:`DECLARES_THE_ANNOTATIONS` is the one exemption and says
    why.
    """
    offenders = {}
    for source in sorted(API_PACKAGE.glob("*.py")):
        if source.name in DECLARES_THE_ANNOTATIONS:
            continue
        tree = ast.parse(source.read_text(encoding="utf-8"))
        reached = sorted(
            module for module in _imported_modules(tree) if module.startswith(FORBIDDEN_IN_ROUTERS)
        )
        if reached:
            offenders[str(source.relative_to(REPO_ROOT))] = reached

    assert offenders == {}, f"a router imports the query layer: {offenders}"


def test_no_service_in_this_module_imports_fastapi() -> None:
    """``docs/shema.md`` §3.3's third line, and the one that keeps the services reusable.

    A service that raises ``HTTPException`` is a service that only an HTTP caller can use —
    and this module already has two non-HTTP callers coming: BE-14's export and BE-16's seed.
    Business exceptions from ``app/core/exceptions.py`` are what a router maps onto a status.
    """
    offenders = {}
    for source in sorted(SERVICE_PACKAGE.glob("*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        reached = sorted(
            module for module in _imported_modules(tree) if module.startswith("fastapi")
        )
        if reached:
            offenders[str(source.relative_to(REPO_ROOT))] = reached

    assert offenders == {}, f"a service imports fastapi: {offenders}"
