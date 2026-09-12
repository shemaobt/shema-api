"""Every literal the room writes about the telling back says traduzir / tradução (ENG-881).

Marcia's ruling (ENG-878): "Na retroverificação a palavra é traduzir/tradução"; *contar*
belongs to the Conversation with the Guide alone, and *recontar* to the External Check
(`CONTEXT.md`, **Telling back**). Read with `ast`, following the pattern of
`tests/test_internalization_room_session_progression.py:_string_literals`: every string
literal of a module except its docstrings, so this sweep is honest about what the server
itself writes rather than about prose describing it.
"""

import ast
from pathlib import Path

_MODULES = [
    "app/services/internalization_room/back_translation.py",
    "app/api/internalization_room/back_translation.py",
    "app/services/internalization_room/verdict_round.py",
    "app/services/internalization_room/turn_instructions.py",
]

_CARRIES_A_DOCSTRING = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def _string_literals(source: Path) -> list[str]:
    """Every string literal in a module except its docstrings."""
    tree = ast.parse(source.read_text(encoding="utf-8"))
    prose = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, _CARRIES_A_DOCSTRING)
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    }
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in prose
    ]


def _literals_of(modules: list[str]) -> list[str]:
    root = Path(__file__).resolve().parents[1]
    literals: list[str] = []
    for module in modules:
        literals.extend(_string_literals(root / module))
    return literals


def _all_app_literals() -> list[str]:
    app_dir = Path(__file__).resolve().parents[1] / "app"
    literals: list[str] = []
    for source in app_dir.rglob("*.py"):
        literals.extend(_string_literals(source))
    return literals


_FORBIDDEN = (
    r"contad[oa]s? de volta|contou de volta|contar de volta|conta de volta"
    r"|contaron de vuelta|contado nada de vuelta|contou nada de volta|told (anything )?back"
)

#: Ten sentences: the six new renderings, where two (1 and 6) are three-language dicts
#: (pt/en/es) and the other four are single Portuguese strings — 3 + 1 + 1 + 1 + 1 + 3.
_EXPECTED_TRADUZIR_WORDS = {
    "(a equipe ainda não traduziu nada)",
    "(the team has not translated anything yet)",
    "(el equipo aún no ha traducido nada)",
    "Compare a tradução com o mapa.",
    "a análise da tradução não pôde ser feita agora",
    "(nenhum achado — a tradução está completa)",
    "a leitura final da tradução não pôde ser feita agora",
    "(a equipe não falou nesta conversa; o que ela traduziu está no bloco abaixo)",
    "(the team has not spoken in this conversation; what they translated is in the block below)",
    "(el equipo no ha hablado en esta conversación; lo que tradujeron está en el bloque de abajo)",
}


def test_no_literal_the_room_writes_says_contar_de_volta() -> None:
    """Every string literal under `app/`, not just the three named modules.

    The business rule is that *no* server literal says it, so a sixth or seventh place the
    ticket never named — anywhere in the app, not only in the three modules this slice
    touches — must be caught too.
    """
    import re

    pattern = re.compile(_FORBIDDEN)
    offenders = sorted({literal for literal in _all_app_literals() if pattern.search(literal)})

    assert offenders == [], f"literais ainda dizem contar de volta: {offenders}"


def test_the_rooms_words_for_the_telling_back_are_exactly_these() -> None:
    """Scoped to the three modules this slice governs.

    Other app modules (`app/services/internalization_room/_default_prompts.py`, the i18n
    strings) carry their own unrelated *tradu* literals — Marcia's prompts and app-facing
    text out of this ticket's scope (ENG-880) — so the exact-set assertion stays narrow to
    what this slice actually changed.
    """
    found = {
        literal
        for literal in _literals_of(_MODULES)
        if "tradu" in literal.lower() or "translated" in literal.lower()
    }

    assert found == _EXPECTED_TRADUZIR_WORDS
