import json
from typing import Any

import pytest

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.canon.elements import (
    ElementKind,
    element_keys,
    elements_for,
    scene_of,
)
from app.services.internalization_room.classify_coverage import classify_coverage
from app.services.internalization_room.coverage import CoverageStatus, initial_state
from tests.turn_harness import the_room_agent_is

P01 = "P01"


def test_scene_four_of_ruth_1_has_the_woman_in_it() -> None:
    beings = {
        element.key: element for element in elements_for(P01) if element.kind is ElementKind.BEING
    }

    assert "being:B3" not in beings, (
        "Naomi dita na cena 1 satisfazia a conta dela pelo resto da passagem, e a cena 4 — "
        "onde o mapa a chama de 'a mulher' — não tinha ninguém no colar"
    )
    assert beings["being:S4:B3"].scene == 4
    assert beings["being:S4:B3"].label == "the woman"
    assert beings["being:S1:B3"].label == "Naomi"


def test_scene_four_of_ruth_1_holds_everyone_her_coordinates_list_not_only_the_prose() -> None:
    scene_four = [
        (element.key, element.label)
        for element in elements_for(P01)
        if element.kind is ElementKind.BEING and element.scene == 4
    ]

    assert scene_four == [
        ("being:S4:B4", "Mahlon"),
        ("being:S4:B5", "Chilion"),
        ("being:S4:B3", "the woman"),
        ("being:S4:B2", "Elimelech"),
        ("being:S4:B8", "Orpah"),
        ("being:S4:B9", "Ruth"),
    ], (
        "as contas vinham da prosa do mapa, e a cena 4 ficava sem Elimeleque, Orfa e Rute, "
        "que as coordenadas dela listam ali"
    )


def test_ruth_1_strings_thirty_two_entity_beads_across_its_four_scenes() -> None:
    entity_kinds = {ElementKind.BEING, ElementKind.PLACE, ElementKind.OBJECT, ElementKind.TIME}
    per_scene: dict[int, list[str]] = {}
    for element in elements_for(P01):
        if element.kind in entity_kinds and element.scene is not None:
            per_scene.setdefault(element.scene, []).append(element.key)

    assert {scene: len(keys) for scene, keys in per_scene.items()} == {1: 12, 2: 5, 3: 8, 4: 7}
    assert per_scene[4] == [
        "being:S4:B4",
        "being:S4:B5",
        "being:S4:B3",
        "being:S4:B2",
        "being:S4:B8",
        "being:S4:B9",
        "place:S4:PL2",
    ]
    assert len(set(element_keys(P01))) == len(element_keys(P01))


def test_every_bead_that_sits_in_a_scene_can_say_which() -> None:
    answers = scene_of(P01)

    assert answers["being:S4:B3"] == 4, (
        "Naomi atravessava as quatro cenas numa conta só, e a conta não podia dizer onde a "
        "equipe estava — cinco das contas de P01 ficavam sem resposta"
    )
    assert answers["place:S2:PL2"] == 2
    assert answers["scene:S3"] == 3
    assert "preserved:R10" not in answers
    assert "L1:tone" not in answers
    assert set(answers) == {e.key for e in elements_for(P01) if e.scene is not None}


async def test_naomi_named_in_scene_one_does_not_answer_for_the_woman_in_scene_four(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    naomi_in_scene_one = json.dumps(
        {
            "decisions": [
                {
                    "element_id": "being:S1:B3",
                    "new_status": "engaged",
                    "evidence": "contaram que Noemi saiu de Belém com o marido",
                }
            ]
        }
    )

    async def agent(*, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        return naomi_in_scene_one

    the_room_agent_is(monkeypatch, classifier=agent)

    settled = await classify_coverage(
        coverage_state=initial_state(P01),
        team_utterance="Noemi saiu de Belém com o marido e os dois filhos",
        guide_response="isso mesmo",
        classifier_prompt=default_prompt(IRPromptKey.COVERAGE_CLASSIFIER)["prompt"],
        pericope_num=P01,
        settings=Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake"),
    )

    assert settled["being:S1:B3"] == CoverageStatus.ENGAGED.value
    assert settled["being:S4:B3"] == CoverageStatus.NOT_ENCOUNTERED.value, (
        "'Noemi' dita na cena 1 satisfazia 'a mulher' da cena 4 — a de-nomeação em que a "
        "passagem vira não podia ser perguntada"
    )


def test_the_room_asks_once_about_the_missing_act_of_god_not_twice() -> None:
    by_key = {element.key: element for element in elements_for(P01)}
    rules = {key for key in by_key if key.startswith("preserved:")}

    assert rules == {"preserved:R3", "preserved:R5", "preserved:R10"}, (
        "'nenhum ato de Deus' era a conta absence:1 e de novo a conta preserved:R6, e a sala "
        "levantava o mesmo silêncio duas vezes"
    )
    assert by_key["absence:S1"].label.startswith("The narrator never says YHWH sent the famine")
    assert (
        "STRUCTURAL_ABSENCE_OF_DIVINE_AGENCY: YHWH is not named as agent"
        in by_key["absence:S1"].label
    )
    assert "STRUCTURAL_ABSENCE_OF_GRIEF" not in by_key["absence:S1"].label
    assert "STRUCTURAL_ABSENCE_OF_DIVINE_AGENCY" in by_key["absence:S4"].label
    assert (
        "STRUCTURAL_ABSENCE_OF_GRIEF: The narrator reports each death" in by_key["absence:S4"].label
    )
    assert by_key["absence:S3"].label == (
        "No children are born to either marriage in the ten years they live there. "
        "The narrator tells us how long it was, but says nothing of any child."
    )
    assert by_key["preserved:R10"].label.startswith("WITHHELD_PAIRING_PER_SOURCE_DISCIPLINE")


def test_ruth_1_strings_forty_seven_beads_axes_first() -> None:
    spine = elements_for(P01)
    by_kind: dict[str, int] = {}
    for element in spine:
        by_kind[element.kind.value] = by_kind.get(element.kind.value, 0) + 1

    assert len(spine) == 47
    assert by_kind == {
        "arc": 1,
        "context": 1,
        "tone": 1,
        "function": 1,
        "scene": 4,
        "being": 22,
        "place": 6,
        "object": 3,
        "time": 1,
        "absence": 4,
        "preserved": 3,
    }
    assert [element.key for element in spine[:5]] == [
        "L1:arc",
        "L1:context",
        "L1:tone",
        "L1:function",
        "scene:S1",
    ]
    assert spine[-1].key == "preserved:R10"
