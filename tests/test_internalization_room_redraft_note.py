"""The redraft note reaches the Guide in the session's own language, not always Portuguese.

The bug (ENG-714): the note is what tells a Guide whose draft did not pass what to fix, and
every branch of it was hardcoded in Portuguese regardless of which language the session
speaks. A session in English or Spanish would receive redraft instructions in a language the
Guide never opted into.
"""

import re

import pytest

from app.services.internalization_room.languages import ROOM_LANGUAGES
from app.services.internalization_room.run_turn import (
    _DESCRIBED_ISSUES_NOTE,
    _NO_ISSUES_NOTE,
    _OFF_BRIDGE_LANGUAGE_NOTE,
    _redraft_note,
)

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
    "pt": "A resposta anterior não passou na conferência. Refaça.",
    "en": "The previous response did not pass review. Redo it.",
    "es": "La respuesta anterior no pasó la revisión. Rehazla.",
}


@pytest.mark.parametrize("language_code", ROOM_LANGUAGES)
def test_the_no_issues_note_is_written_in_the_sessions_language(language_code: str) -> None:
    note = _redraft_note([], language_code)

    assert note == _EXPECTED_NO_ISSUES[language_code]


_DESCRIBED_ISSUES = [{"problem": "imported_knowledge", "claim": "Rute era moabita"}]

_EXPECTED_DESCRIBED = {
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


@pytest.mark.parametrize("language_code", ROOM_LANGUAGES)
def test_the_described_issues_note_is_written_in_the_sessions_language(language_code: str) -> None:
    note = _redraft_note(_DESCRIBED_ISSUES, language_code)

    expected = _EXPECTED_DESCRIBED[language_code].format(
        described="imported_knowledge: Rute era moabita"
    )
    assert note == expected


_REDRAFT_NOTE_DICTS = {
    "off_bridge_language": _OFF_BRIDGE_LANGUAGE_NOTE,
    "no_issues": _NO_ISSUES_NOTE,
    "described_issues": _DESCRIBED_ISSUES_NOTE,
}


@pytest.mark.parametrize("kind", _REDRAFT_NOTE_DICTS)
@pytest.mark.parametrize("language_code", ROOM_LANGUAGES)
def test_every_redraft_note_covers_every_language_the_room_claims_to_speak(
    language_code: str, kind: str
) -> None:
    """Um idioma reivindicado e não escrito faria a sala cair pro floor sem avisar ninguém."""
    written = _REDRAFT_NOTE_DICTS[kind].get(language_code)

    assert written, (
        f"a sala diz que fala {language_code!r} e a nota de redraft {kind!r} não tem "
        "texto escrito nesse idioma"
    )


_UNNAMED_PROBLEM_ISSUE = [{"claim": "Rute era moabita"}]


@pytest.mark.parametrize(("language_code", "label"), [("en", "problem"), ("pt", "problema")])
def test_an_issue_missing_its_problem_key_falls_back_in_the_sessions_language(
    language_code: str, label: str
) -> None:
    """ENG-822, item 5: the fallback used to be the bare Portuguese word "problema" no matter
    which language's note it landed inside, so an English session's note could read
    "problema: Rute era moabita" — Portuguese inside an otherwise-English sentence.
    """
    note = _redraft_note(_UNNAMED_PROBLEM_ISSUE, language_code)

    assert f"{label}: Rute era moabita" in note


_SAY_LESS = re.compile(r"say less|saying less|dizendo menos|diga menos", re.I)


@pytest.mark.parametrize("kind", _REDRAFT_NOTE_DICTS)
@pytest.mark.parametrize("language_code", ROOM_LANGUAGES)
def test_no_redraft_note_asks_the_guide_to_say_less(language_code: str, kind: str) -> None:
    """Um pedido de entender se responde por inteiro — DOCTRINE §3, regra 4."""
    written = _REDRAFT_NOTE_DICTS[kind][language_code]

    assert not _SAY_LESS.search(written), (
        f"a nota de redraft {kind!r} em {language_code!r} manda o Guia dizer menos, e a "
        "extensão de uma resposta não é o que a conferência reprovou"
    )
