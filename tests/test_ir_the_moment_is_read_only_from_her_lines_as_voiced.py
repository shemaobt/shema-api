from typing import Any

import pytest

from app.services.internalization_room.moment import moment_step

FAMILIARIZATION = {"at": "familiarization"}
SCENE_TWO_OPEN = {"at": "internalization", "part": 2}


def _after(moment: dict[str, Any], voiced: str) -> dict[str, Any]:
    heard = [{"role": "guide", "text": "", "moment": {"after": moment}}]
    return moment_step(heard, voiced)["after"]


@pytest.mark.parametrize(
    "voiced",
    [
        "Vamos pra Internalização da cena 2, onde Noemi decide voltar.",
        "Vamos pra  Internalização   da cena 2.",
        "Vamos pra\nInternalização da cena 2.\n\nNoemi decide voltar.",
        "Então, vamos pra Internalização da cena 2.",
        "Agora vamos pra Internalização da cena 2.",
        "Muito bem. Agora vamos pra Internalização da cena 2.",
        "Vamos para a Internalização da parte 2.",
        "vamos pra internalização da cena dois!",
        "Agora vamos pra Internalização da cena 2 — versos 10 a 13.",
    ],
)
def test_her_opening_line_said_with_another_comma_or_space_still_opens_the_scene(
    voiced: str,
) -> None:
    assert _after(FAMILIARIZATION, voiced) == SCENE_TWO_OPEN, (
        f"a sala não reconheceu a linha dela dita assim: {voiced!r}"
    )


@pytest.mark.parametrize(
    "voiced",
    [
        "Na articulação vocês vão ensaiar essa cena, depois de entender a história.",
        "E depois vamos pra Internalização da cena 2.",
        "Vamos pra Internalização da cena 2 e depois da cena 3.",
        "Vamos pra Internalização da cena 2?",
        "Depois vamos pra Internalização da cena 2.",
        "Quando estiverem prontos, vamos pra Internalização da cena 2.",
        "Não vamos pra Internalização da cena 2 ainda.",
        "Agora vamos pra segunda parte, versos dez a treze.",
    ],
)
def test_a_moment_named_in_passing_is_not_her_line_and_moves_nothing(voiced: str) -> None:
    assert _after(FAMILIARIZATION, voiced) == FAMILIARIZATION, (
        f"a sala mudou de momento por uma menção de passagem: {voiced!r}"
    )
