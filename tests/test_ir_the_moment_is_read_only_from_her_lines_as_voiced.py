from typing import Any

import pytest

from app.services.internalization_room.moment import moment_step

FAMILIARIZATION = {"at": "familiarization"}
SCENE_TWO_OPEN = {"at": "internalization", "part": 2}
F3 = (
    "O que chamou a atenção de vocês nessa passagem? Conversem entre vocês. Se tiver alguma "
    "dúvida, me perguntem. Quando estiverem prontos, me digam e a gente vai pra Internalização "
    "da primeira cena."
)
CLOSING = (
    "O que chamou a atenção de vocês nessa cena? Conversem entre vocês. Essa cena ficou clara? "
    "Se tiver alguma dúvida, me perguntem. Se já entenderam, me digam e a gente vai pro ensaio."
)
CLOSING_OF_23_SEPTEMBER = (
    "O que chamou a atenção de vocês nessa parte? Conversem entre vocês. Essa parte ficou clara? "
    "Se tiver alguma dúvida, me perguntem. Se já entenderam, me digam e a gente vai pro ensaio."
)
FAMILIARIZATION_CLOSED = {"at": "familiarization", "closed": True}
SCENE_ONE_OPEN = {"at": "internalization", "part": 1}
SCENE_ONE = "Na primeira cena, a fome leva a família pra Moabe."
SEND_OFF = (
    "Vocês contaram a passagem inteira. "
    "Agora toquem no ponto laranja, no alto da tela, para abrir o Ensaio Final."
)
ENSAIO_FINAL = {"at": "ensaio_final"}
SCENE_TWO_PRACTISED = {"at": "articulation", "part": 2, "fenced": False}
SCENE_TWO_FENCED = {"at": "articulation", "part": 2, "fenced": True}
TOLD = "Vamos começar pela Familiarização. Primeiro eu conto a passagem inteira. Noemi voltou."


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


def test_her_familiarization_closing_as_the_last_words_closes_the_familiarization() -> None:
    assert _after(FAMILIARIZATION, f"{TOLD} {F3}") == {"at": "familiarization", "closed": True}, (
        "o fechamento da Familiarização foi dito e a sala não registrou"
    )


def test_her_familiarization_closing_with_words_after_it_is_not_the_closing() -> None:
    assert _after(FAMILIARIZATION, f"{TOLD} {F3} Mais alguma coisa?") == FAMILIARIZATION


@pytest.mark.parametrize("closing", [CLOSING, CLOSING_OF_23_SEPTEMBER])
def test_her_scene_closing_after_the_familiarization_closed_opens_the_first_scene(
    closing: str,
) -> None:
    assert _after(FAMILIARIZATION_CLOSED, f"{SCENE_ONE} {closing}") == SCENE_ONE_OPEN, (
        "o fechamento da cena terminou a abertura da cena 1 e a sala ficou na Familiarização"
    )


@pytest.mark.parametrize(
    "moment", [FAMILIARIZATION, SCENE_TWO_OPEN], ids=["not closed", "inside a scene"]
)
def test_her_scene_closing_moves_nothing_where_it_opens_no_new_scene(
    moment: dict[str, Any],
) -> None:
    assert _after(moment, f"{SCENE_ONE} {CLOSING}") == moment


def test_her_send_off_as_the_last_words_puts_the_room_in_the_ensaio_final() -> None:
    assert _after(SCENE_TWO_OPEN, SEND_OFF) == ENSAIO_FINAL, (
        "a despedida mandou a equipe pro ponto laranja e a sala continuou na cena"
    )


def test_her_send_off_with_words_after_it_is_not_the_send_off() -> None:
    assert _after(SCENE_TWO_OPEN, f"{SEND_OFF} Ou querem ouvir de novo?") == SCENE_TWO_OPEN


def test_an_opening_line_after_the_send_off_leaves_the_room_in_the_ensaio_final() -> None:
    assert _after(ENSAIO_FINAL, "Vamos pra Internalização da cena 2.") == ENSAIO_FINAL, (
        "uma linha numerada depois da despedida tirou a sala do Ensaio Final"
    )


def test_her_articulation_line_moves_the_room_to_the_scenes_articulation() -> None:
    assert _after(SCENE_TWO_OPEN, "Vamos pra Articulação da cena 2.") == SCENE_TWO_PRACTISED, (
        "a voz abriu a Articulação da cena 2 e a sala continuou na Internalização"
    )


def test_her_articulation_line_said_again_in_that_articulation_keeps_its_fenced_block() -> None:
    assert _after(SCENE_TWO_FENCED, "Vamos pra Articulação da cena 2.") == SCENE_TWO_FENCED
