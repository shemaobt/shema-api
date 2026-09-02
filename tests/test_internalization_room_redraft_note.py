"""The redraft note reaches the Guide in the session's own language, not always Portuguese.

The bug (ENG-714): the note is what tells a Guide whose draft did not pass what to fix, and
every branch of it was hardcoded in Portuguese regardless of which language the session
speaks. A session in English or Spanish would receive redraft instructions in a language the
Guide never opted into.
"""

import pytest

from app.services.internalization_room.languages import ROOM_LANGUAGES
from app.services.internalization_room.run_turn import TURN_BUDGET, _redraft_note

_OVER_BUDGET_ISSUES = [{"problem": "over_speech_budget"}]

_EXPECTED_OVER_BUDGET = {
    "pt": (
        "A resposta anterior era longa demais para uma sala oral. Refaça com no máximo "
        "{sentences} frases curtas e {words} palavras."
    ),
    "en": (
        "The previous response was too long for an oral room. Redo it with at most "
        "{sentences} short sentences and {words} words."
    ),
    "es": (
        "La respuesta anterior era demasiado larga para una sala oral. Rehazla con un "
        "máximo de {sentences} frases cortas y {words} palabras."
    ),
}


@pytest.mark.parametrize("language_code", ROOM_LANGUAGES)
def test_the_over_budget_note_is_written_in_the_sessions_language(language_code: str) -> None:
    note = _redraft_note(_OVER_BUDGET_ISSUES, language_code, ceiling=TURN_BUDGET)

    expected = _EXPECTED_OVER_BUDGET[language_code].format(
        sentences=TURN_BUDGET.sentences, words=TURN_BUDGET.words
    )
    assert note == expected


_OFF_BRIDGE_ISSUES = [{"problem": "off_bridge_language"}]

_EXPECTED_OFF_BRIDGE = {
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

_AUTONYM = {"pt": "português", "en": "English", "es": "español"}


@pytest.mark.parametrize("language_code", ROOM_LANGUAGES)
def test_the_off_bridge_note_names_the_session_language_in_itself(language_code: str) -> None:
    note = _redraft_note(_OFF_BRIDGE_ISSUES, language_code)

    expected = _EXPECTED_OFF_BRIDGE[language_code].format(language=_AUTONYM[language_code])
    assert note == expected


_EXPECTED_NO_ISSUES = {
    "pt": "A resposta anterior não passou na conferência. Refaça, dizendo menos.",
    "en": "The previous response did not pass review. Redo it, saying less.",
    "es": "La respuesta anterior no pasó la revisión. Rehazla, diciendo menos.",
}


@pytest.mark.parametrize("language_code", ROOM_LANGUAGES)
def test_the_no_issues_note_is_written_in_the_sessions_language(language_code: str) -> None:
    note = _redraft_note([], language_code)

    assert note == _EXPECTED_NO_ISSUES[language_code]
