from __future__ import annotations

from typing import Any

from app.services.internalization_room.languages import FLOOR

_OFF_BRIDGE_LANGUAGE_NOTE: dict[str, str] = {
    "pt": (
        "A resposta anterior saiu do idioma da sessão e por isso não pôde ser falada. "
        "Refaça o turno inteiro em {language}, sem nenhuma frase em outro idioma. O "
        "mapa está em inglês: carregue o sentido dele para o idioma da sessão em vez de "
        "citá-lo."
    ),
    "en": (
        "The previous response left the session's language and could not be spoken. "
        "Redo the whole turn in {language}, with no sentence in another language. The "
        "map is in English: carry its meaning into the session's language instead of "
        "quoting it."
    ),
}

_LANGUAGE_AUTONYMS: dict[str, str] = {"en": "English", "pt": "português"}

_NO_ISSUES_NOTE: dict[str, str] = {
    "pt": "A resposta anterior não passou na conferência. Refaça.",
    "en": "The previous response did not pass review. Redo it.",
}

_REDRAFT_NOTE = (
    "(internal redraft note — the previous draft carried something the map does not support: "
    "{issues}. Redraft the same answer, as fully as the team's request deserves, using only "
    "what the map contains.)"
)


def _redraft_note(issues: list[dict[str, Any]], language_code: str = FLOOR) -> str:
    """What to tell a Guide whose draft did not pass, written in the session's own language."""
    if any(issue.get("problem") == "off_bridge_language" for issue in issues):
        template = _OFF_BRIDGE_LANGUAGE_NOTE.get(language_code, _OFF_BRIDGE_LANGUAGE_NOTE[FLOOR])
        autonym = _LANGUAGE_AUTONYMS.get(language_code, _LANGUAGE_AUTONYMS[FLOOR])
        return template.format(language=autonym)
    if not issues:
        return _NO_ISSUES_NOTE.get(language_code, _NO_ISSUES_NOTE[FLOOR])
    described = "; ".join(
        f"{issue.get('problem', 'problem')}: {issue.get('claim', '')} — "
        f"{issue.get('explanation', '')}"
        for issue in issues
    )
    return _REDRAFT_NOTE.format(issues=described)
