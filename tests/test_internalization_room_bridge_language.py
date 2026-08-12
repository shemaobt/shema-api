"""No line reaches the team in a language they did not come to work in.

The Meaning Map is written in English and the team hears every line exactly once, so a
sentence that drifts out of the bridge language is not a blemish — it is a line they
cannot use, and there is no scrollback to recover from it.
"""

import pytest

from app.services.internalization_room.bridge_language import strays_from

PT = (
    "Olá, eu sou o Facilitador Digital. Antes de entrarmos nas partes, vamos sentir "
    "o todo desta passagem juntos."
)
EN = (
    "Hello, I am the Digital Facilitator. Before we go into the parts, let us feel "
    "the whole of this passage together."
)


def test_portuguese_passes() -> None:
    assert strays_from(PT) is False


def test_english_is_refused() -> None:
    assert strays_from(EN) is True


@pytest.mark.parametrize("line", ["Vamos.", "Contem de novo.", "", "   "])
def test_a_line_too_short_to_judge_is_never_refused(line: str) -> None:
    """Silencing the facilitator costs more than one odd word."""
    assert strays_from(line) is False


def test_a_foreign_name_does_not_condemn_the_sentence() -> None:
    """The map is written in English, so a name may arrive in its English spelling.

    One foreign token inside a Portuguese sentence is not a language slip — refusing it
    would silence the facilitator over a proper noun. What the Guide must not do is
    quote the map's terms untranslated, and that is the Guide's rule, not this gate's.
    """
    mostly_pt = (
        "O mapa escreve o nome dela como Ruth, mas na fala de vocês ela é Rute, e é "
        "assim que vamos contar essa história daqui em diante."
    )
    assert strays_from(mostly_pt) is False


def test_the_map_terms_belong_in_portuguese() -> None:
    """`ausência significativa`, never `significant absence` — the team hears it once."""
    rendered = (
        "O mapa chama esse trecho de ausência significativa, e é justamente o silêncio "
        "que a gente precisa guardar quando contar de novo."
    )
    assert strays_from(rendered) is False


def test_the_room_can_be_run_in_another_bridge_language() -> None:
    assert strays_from(EN, language_code="en") is False
    assert strays_from(PT, language_code="en") is True
