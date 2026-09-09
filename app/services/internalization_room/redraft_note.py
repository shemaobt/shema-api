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
    "es": (
        "La respuesta anterior salió del idioma de la sesión y por eso no pudo hablarse. "
        "Rehaz el turno completo en {language}, sin ninguna frase en otro idioma. El "
        "mapa está en inglés: lleva su sentido al idioma de la sesión en lugar de "
        "citarlo."
    ),
}

_LANGUAGE_AUTONYMS: dict[str, str] = {"en": "English", "es": "español", "pt": "português"}

_NO_ISSUES_NOTE: dict[str, str] = {
    "pt": "A resposta anterior não passou na conferência. Refaça.",
    "en": "The previous response did not pass review. Redo it.",
    "es": "La respuesta anterior no pasó la revisión. Rehazla.",
}

_DESCRIBED_ISSUES_NOTE: dict[str, str] = {
    "pt": (
        "A resposta anterior foi rejeitada na conferência contra o mapa. Problemas "
        "apontados — {described}. Refaça o turno sem essas afirmações."
    ),
    "en": (
        "The previous response was rejected against the map. Issues raised — "
        "{described}. Redo the turn without those claims."
    ),
    "es": (
        "La respuesta anterior fue rechazada frente al mapa. Problemas señalados — "
        "{described}. Rehaz el turno sin esas afirmaciones."
    ),
}


def _redraft_note(issues: list[dict[str, Any]], language_code: str = FLOOR) -> str:
    """What to tell a Guide whose draft did not pass, written in the session's own language."""
    if any(issue.get("problem") == "off_bridge_language" for issue in issues):
        template = _OFF_BRIDGE_LANGUAGE_NOTE.get(language_code, _OFF_BRIDGE_LANGUAGE_NOTE[FLOOR])
        autonym = _LANGUAGE_AUTONYMS.get(language_code, _LANGUAGE_AUTONYMS[FLOOR])
        return template.format(language=autonym)
    if not issues:
        return _NO_ISSUES_NOTE.get(language_code, _NO_ISSUES_NOTE[FLOOR])
    described = "; ".join(
        f"{issue.get('problem', 'problema')}: {issue.get('claim', '')}".strip(": ")
        for issue in issues[:3]
    )
    template = _DESCRIBED_ISSUES_NOTE.get(language_code, _DESCRIBED_ISSUES_NOTE[FLOOR])
    return template.format(described=described)
