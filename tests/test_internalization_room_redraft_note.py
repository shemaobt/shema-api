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
