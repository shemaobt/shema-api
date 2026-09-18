"""ENG-932 — asyncio_mode = "auto" already marks every coroutine test as async; a
`@pytest.mark.asyncio` on top of it asserts nothing pytest-asyncio does not already do on
its own. The marker only earns its keep back if a test needs `loop_scope` or some other
argument the auto mode does not give it — this repo has none of those today.

A new test file copied from an older one is exactly how these came back once; this guards
the mode from the other side, so a reintroduced marker fails locally instead of just sitting
there unread until the next sweep.
"""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"


def _asyncio_mode() -> str:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    return config["tool"]["pytest"]["ini_options"]["asyncio_mode"]


def _is_bare_asyncio_marker(node: ast.expr) -> bool:
    if isinstance(node, ast.Call):
        if node.args or node.keywords:
            return False
        node = node.func
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "asyncio"
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "mark"
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "pytest"
    )


def _asyncio_marker_lines(module: Path) -> list[int]:
    tree = ast.parse(module.read_text(encoding="utf-8"))
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for decorator in node.decorator_list:
            if _is_bare_asyncio_marker(decorator):
                lines.append(decorator.lineno)
    return lines


def _decorator(source: str) -> ast.expr:
    return ast.parse(source).body[0].decorator_list[0]


def test_a_bare_marker_is_flagged() -> None:
    assert _is_bare_asyncio_marker(_decorator("@pytest.mark.asyncio\nasync def f(): ...\n"))


def test_an_empty_call_marker_is_flagged() -> None:
    assert _is_bare_asyncio_marker(_decorator("@pytest.mark.asyncio()\nasync def f(): ...\n"))


def test_a_marker_carrying_loop_scope_is_not_flagged() -> None:
    marker = _decorator('@pytest.mark.asyncio(loop_scope="session")\nasync def f(): ...\n')
    assert not _is_bare_asyncio_marker(marker)


def test_asyncio_mode_is_auto() -> None:
    assert _asyncio_mode() == "auto", "o guarda abaixo só vale enquanto o modo for automático"


def test_no_test_carries_the_redundant_asyncio_marker() -> None:
    offenders = []
    for module in sorted(TESTS.rglob("*.py")):
        for lineno in _asyncio_marker_lines(module):
            offenders.append(f"{module.relative_to(ROOT)}:{lineno}")

    assert offenders == [], "@pytest.mark.asyncio é redundante sob asyncio_mode=auto: " + ", ".join(
        offenders
    )
