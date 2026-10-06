"""The redraft note reaches the Guide in the session's own language, not always Portuguese.

The bug (ENG-714): the note is what tells a Guide whose draft did not pass what to fix, and
every branch of it was hardcoded in Portuguese regardless of which language the session
speaks. A session in English would receive redraft instructions in a language the
Guide never opted into.
"""

import re

import pytest

from app.services.internalization_room.languages import ROOM_LANGUAGES
from app.services.internalization_room.run_turn import (
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
}

_AUTONYM = {"pt": "português", "en": "English"}


@pytest.mark.parametrize("language_code", ROOM_LANGUAGES)
def test_the_off_bridge_note_names_the_session_language_in_itself(language_code: str) -> None:
    note = _redraft_note(_OFF_BRIDGE_ISSUES, language_code)

    expected = _EXPECTED_OFF_BRIDGE[language_code].format(language=_AUTONYM[language_code])
    assert note == expected


_EXPECTED_NO_ISSUES = {
    "pt": "A resposta anterior não passou na conferência. Refaça.",
    "en": "The previous response did not pass review. Redo it.",
}


@pytest.mark.parametrize("language_code", ROOM_LANGUAGES)
def test_the_no_issues_note_is_written_in_the_sessions_language(language_code: str) -> None:
    note = _redraft_note([], language_code)

    assert note == _EXPECTED_NO_ISSUES[language_code]


_FIVE_ISSUES = [
    {
        "problem": "invented_detail",
        "claim": "Noemi chorava na estrada",
        "explanation": "The map records no tears on the road.",
    },
    {
        "problem": "imported_knowledge",
        "claim": "Moabe ficava além do Jordão",
        "explanation": "The map gives no geography beyond Moab.",
    },
    {
        "problem": "softened_absence",
        "claim": "ninguém sabe por que ela voltou",
        "explanation": "The map marks the reason as deliberately absent.",
    },
    {
        "problem": "overstated_certainty",
        "claim": "Rute decidiu na mesma hora",
        "explanation": "The map leaves the moment of decision open.",
    },
    {
        "problem": "scrambled_structure",
        "claim": "primeiro a colheita, depois a despedida",
        "explanation": "The map orders the farewell before the harvest.",
    },
]

_HER_NOTE_FOR_FIVE_ISSUES = (
    "(internal redraft note — the previous draft carried something the map does not "
    "support: invented_detail: Noemi chorava na estrada — The map records no tears on the "
    "road.; imported_knowledge: Moabe ficava além do Jordão — The map gives no geography "
    "beyond Moab.; softened_absence: ninguém sabe por que ela voltou — The map marks the "
    "reason as deliberately absent.; overstated_certainty: Rute decidiu na mesma hora — The "
    "map leaves the moment of decision open.; scrambled_structure: primeiro a colheita, "
    "depois a despedida — The map orders the farewell before the harvest.. Redraft the same "
    "answer, as fully as the team's request deserves, using only what the map contains.)"
)


def test_a_draft_sent_back_with_five_issues_lists_all_five_with_their_reasons() -> None:
    assert _redraft_note(_FIVE_ISSUES) == _HER_NOTE_FOR_FIVE_ISSUES


_REDRAFT_NOTE_DICTS = {
    "off_bridge_language": _OFF_BRIDGE_LANGUAGE_NOTE,
    "no_issues": _NO_ISSUES_NOTE,
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


@pytest.mark.parametrize(
    ("issues", "expected"),
    [
        (
            _OFF_BRIDGE_ISSUES,
            _EXPECTED_OFF_BRIDGE["en"].format(language="English"),
        ),
        ([], _EXPECTED_NO_ISSUES["en"]),
    ],
)
def test_a_session_still_stored_in_spanish_is_told_in_the_floors_language(
    issues: list[dict[str, str]], expected: str
) -> None:
    assert _redraft_note(issues, "es") == expected


_UNNAMED_PROBLEM_ISSUE = [{"claim": "Rute era moabita"}]


def test_an_issue_missing_its_problem_key_falls_back_to_the_english_word() -> None:
    note = _redraft_note(_UNNAMED_PROBLEM_ISSUE)

    assert "problem: Rute era moabita" in note


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
