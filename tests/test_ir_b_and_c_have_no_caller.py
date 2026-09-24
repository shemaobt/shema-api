"""ENG-833/ENG-917 — B, C and E are reserve lines: present in the file, unreachable from code.

Marcia's ruling of 7 September: "B e C em português: podem entrar no arquivo oficial como
reserva ... B nunca responde a um pedido de entender." Her ruling of 21 September adds E to the
same word: "B, C and E remain reserve lines." Reserve means the text is approved to exist and
nothing is approved to speak it — the Guide answers a request to understand from the map itself,
a question outside the map is handled inline in its prompt, and a run of failures ends in the
fourth A line, never in the pause — so nothing may route to `FailSafe.OUTSIDE_MAP`,
`FailSafe.HANDOFF`, or `FailSafe.HARD_STOP`. Before this test the claim lived only as prose in
another test's docstring; nothing ran it.

A grep would do the same job less safely: the bare letters "B" and "C" turn up constantly in
unrelated code (`blocks.get("B", "")` in the map parser, for one), so this walks the syntax tree
for the one shape that actually reaches a reserve line — `FailSafe.OUTSIDE_MAP` /
`FailSafe.HANDOFF` / `FailSafe.HARD_STOP` as an attribute access — the same way
`tests/test_the_harness_is_the_only_door_between_test_modules.py` already asserts an absence
across the tree instead of across the text.

`fail_safe.py` itself is scanned too, not skipped: `OUTSIDE_MAP = "B"`, `HANDOFF = "C"` and
`HARD_STOP = "E"` on the enum are assignment targets, not `ast.Attribute` nodes, so the enum's
own declaration was never going to trip this — but a module-internal reach for a reserve line
would be exactly the attribute-access shape this walks for, and would have gone unseen behind a
module-wide skip. `validation_ladder` reached for `FailSafe.HARD_STOP` this way until ENG-917
deleted it with its one caller; this guard is what now keeps that door shut.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"

RESERVE = {"OUTSIDE_MAP", "HANDOFF", "HARD_STOP"}


def _reserve_references(module: Path) -> list[str]:
    tree = ast.parse(module.read_text(encoding="utf-8"))
    hits: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute) or node.attr not in RESERVE:
            continue
        if isinstance(node.value, ast.Name) and node.value.id == "FailSafe":
            hits.append(f"{module.relative_to(ROOT)}:{node.lineno} FailSafe.{node.attr}")
    return hits


def test_the_reserve_lines_have_no_caller() -> None:
    hits: list[str] = []
    for module in sorted(APP.rglob("*.py")):
        hits.extend(_reserve_references(module))

    assert hits == [], (
        "B, C e E existem só como reserva — aprovadas para estar no arquivo, nunca para "
        f"tocar — e algo em produção agora as alcança: {hits}"
    )
