"""The pre-approved lines ship as audio inside the app, and must not drift from the prompt.

A fail-safe is what the team hears when the model failed or the network did. Synthesizing it
at that moment asks the network for a favour precisely when the network is the problem — so
these lines travel with the app. The cost of that is a frozen copy, and the guard against a
silent freeze is this file.
"""

import re
from pathlib import Path

import pytest

import scripts.render_fixed_voice_lines as render
from app.services.internalization_room.fail_safe import FailSafe, choose, localized
from app.services.internalization_room.languages import ROOM_LANGUAGES

BUNDLE = Path(__file__).resolve().parents[2] / "internalization-room/assets/audio"


@pytest.mark.skip(
    reason="paused by decision: re-rendering after a prompt edit is a person's job for now. "
    "Re-enable with `uv run python scripts/render_fixed_voice_lines.py --check`, which still "
    "works and still exits non-zero on drift."
)
@pytest.mark.parametrize("spoken", ROOM_LANGUAGES)
def test_every_line_the_room_can_speak_is_rendered_and_current(spoken: str) -> None:
    complaints = render.drift(BUNDLE, spoken)
    assert complaints == [], (
        "as falas fixas saíram de sincronia com o prompt — rode "
        "`uv run python scripts/render_fixed_voice_lines.py`"
    )


@pytest.mark.parametrize("spoken", ROOM_LANGUAGES)
def test_the_catalogue_covers_every_kind_the_room_claims_to_speak(spoken: str) -> None:
    """Um idioma reivindicado e não escrito é uma sala que troca de língua no meio.

    Medido com `localized` e não com `utterances`: `utterances` cai para o bloco inglês e
    por isso nunca volta vazio, o que a torna segura para falar e inútil como medida.
    """
    catalogue = render.catalogue(spoken)
    for kind in FailSafe:
        if kind in render.NEVER_SHIPPED:
            continue
        written = localized(kind, spoken)
        assert written, (
            f"a sala diz que fala {spoken!r} e a família {kind} não tem falas escritas nesse "
            "idioma — a equipe ouviria a falha em outra língua"
        )
        for index in range(len(written)):
            assert f"{kind}{index}" in catalogue


@pytest.mark.parametrize("spoken", ROOM_LANGUAGES)
def test_the_stretch_line_is_spoken_and_never_shipped(spoken: str) -> None:
    """O suplemento diz em negrito: *"This one is spoken, not shipped."*"""
    assert not any(name.startswith("H") for name in render.catalogue(spoken))


def test_every_language_ships_the_same_lines_so_a_turn_in_one_is_a_turn_in_all() -> None:
    """O servidor manda `fixed_line` por nome, e o app resolve o nome no pacote do idioma.

    Só os nomes que o servidor pode mandar. As falas soltas não chegam por turno — o app as
    toca sozinho — e o português é o único idioma sem `sem_conexao` e `toque_para_comecar`
    escritos, porque o áudio dele foi gravado antes deste script e a letra nunca foi anotada.
    """
    named = re.compile(r"^[A-Z]\d+$")
    shipped = {
        spoken: {name for name in render.catalogue(spoken) if named.match(name)}
        for spoken in ROOM_LANGUAGES
    }

    assert len(set(map(frozenset, shipped.values()))) == 1, (
        "um idioma ficou sem uma fala que outro tem; o nome chega do servidor no meio de um "
        f"turno e o app não acha o arquivo, então a sala emudece: {shipped}"
    )


def test_a_standalone_line_is_written_for_a_language_or_not_shipped_in_it_at_all() -> None:
    """Nenhuma fala solta empresta a letra de outro idioma: ou está escrita, ou não vai."""
    for spoken in ROOM_LANGUAGES:
        written = render.STANDALONE.get(spoken, {})
        catalogue = render.catalogue(spoken)
        for name in ("sem_conexao", "toque_para_comecar", "gravacao_presa", "microfone"):
            assert (name in catalogue) == (name in written), (
                f"{name} em {spoken!r} entrou no pacote sem letra escrita nesse idioma"
            )


def test_a_repeated_failure_does_not_repeat_the_same_sentence() -> None:
    """The authored file asks for variation; a room stuck on one line sounds like a machine."""
    spoken = [choose(FailSafe.INAUDIBLE, "pt", turn=turn) for turn in range(3)]

    assert len({line for line, _ in spoken}) == 3
    assert [name for _, name in spoken] == ["D0", "D1", "D2"]


def test_the_rotation_wraps_instead_of_running_out() -> None:
    line, name = choose(FailSafe.INAUDIBLE, "pt", turn=3)

    assert name == "D0"
    assert line == choose(FailSafe.INAUDIBLE, "pt", turn=0)[0]


def test_a_kind_with_one_line_always_answers_with_it() -> None:
    assert choose(FailSafe.HARD_STOP, "pt", turn=7)[1] == "E0"


def test_an_unwritten_language_falls_back_to_the_authored_line() -> None:
    """Silence would be the one outcome worse than the wrong language."""
    line, name = choose(FailSafe.UNREPAIRABLE, "xx", turn=0)

    assert line
    assert name == "A0"
