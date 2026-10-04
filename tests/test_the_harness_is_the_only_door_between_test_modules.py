"""ENG-937 — a builder travels through a harness, and never through another test module.

A test module that imports from another test module makes the second one two things at once:
a set of cases and somebody's fixture library. Renaming a helper there breaks cases nobody
was looking at, deleting a case takes a constant with it, and pytest collects the imported
module twice over. The convention `tests/room_harness.py` writes down is the answer: a
`tests/*_harness.py` exports plain builders and constants, fixtures never travel, and each
module keeps its own three-line fixture that calls the builder.

The one sanctioned import between test modules is a package's own `conftest`, which is where
pytest itself puts what a directory of cases shares.
"""

from __future__ import annotations

import ast
from pathlib import Path

TESTS = Path(__file__).resolve().parent


def _imports_of(module: Path) -> list[str]:
    """Every module this file names in an import, including inside a function body.

    Both spellings, because the convention is about what a module reaches for and not about
    how it spells the reach: `import tests.test_x` binds the same names as
    `from tests.test_x import …` does.
    """
    tree = ast.parse(module.read_text(encoding="utf-8"))
    named: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            named.append(node.module)
        elif isinstance(node, ast.Import):
            named.extend(alias.name for alias in node.names)
    return named


def test_builders_travel_through_a_harness_and_never_through_a_test_module() -> None:
    crossings: list[str] = []
    sanctioned: list[str] = []
    for module in sorted(TESTS.rglob("*.py")):
        for imported in _imports_of(module):
            if not imported.startswith("tests.test_"):
                continue
            where = f"{module.relative_to(TESTS)} imports {imported}"
            if imported.endswith(".conftest"):
                sanctioned.append(where)
            else:
                crossings.append(where)

    assert sanctioned, (
        "nenhum import entre módulos de teste foi lido: quem está quebrado é o detector"
    )
    assert crossings == [], (
        "o que um caso empresta a outro mora num tests/*_harness.py, e fixture não viaja"
    )
