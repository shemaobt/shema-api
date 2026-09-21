"""ENG-833 — B and C are reserve lines: present in the file, unreachable from code.

Marcia's ruling of 7 September: "B e C em português: podem entrar no arquivo oficial como
reserva ... B nunca responde a um pedido de entender." Reserve means the text is approved to
exist and nothing is approved to speak it — the Guide answers a request to understand from the
map itself, and a question outside the map is handled inline in its prompt, never by routing to
`FailSafe.OUTSIDE_MAP` or `FailSafe.HANDOFF`. Before this test the claim lived only as prose in
another test's docstring; nothing ran it.

A grep would do the same job less safely: the bare letters "B" and "C" turn up constantly in
unrelated code (`blocks.get("B", "")` in the map parser, for one), so this walks the syntax tree
for the one shape that actually reaches a reserve line — `FailSafe.OUTSIDE_MAP` /
`FailSafe.HANDOFF` as an attribute access — the same way
`tests/test_the_harness_is_the_only_door_between_test_modules.py` already asserts an absence
across the tree instead of across the text.

`fail_safe.py` itself is scanned too, not skipped: `OUTSIDE_MAP = "B"` and `HANDOFF = "C"` on
the enum are assignment targets, not `ast.Attribute` nodes, so the enum's own declaration was
never going to trip this — but a ladder inside the module reaching for a reserve line, the way
`validation_ladder` reaches for `FailSafe.HARD_STOP`, is exactly the attribute-access shape this
walks for, and would have gone unseen behind a module-wide skip.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"

RESERVE = {"OUTSIDE_MAP", "HANDOFF"}


def _reserve_references(module: Path) -> list[str]:
    tree = ast.parse(module.read_text(encoding="utf-8"))
    hits: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute) or node.attr not in RESERVE:
            continue
        if isinstance(node.value, ast.Name) and node.value.id == "FailSafe":
            hits.append(f"{module.relative_to(ROOT)}:{node.lineno} FailSafe.{node.attr}")
    return hits


def test_b_and_c_have_no_caller() -> None:
    hits: list[str] = []
    for module in sorted(APP.rglob("*.py")):
        hits.extend(_reserve_references(module))

    assert hits == [], (
        "B e C existem só como reserva — aprovadas para estar no arquivo, nunca para tocar — "
        f"e algo em produção agora as alcança: {hits}"
    )
