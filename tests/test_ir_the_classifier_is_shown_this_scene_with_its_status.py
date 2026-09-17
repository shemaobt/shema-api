"""What the bead classifier is handed each turn, and what it is allowed to move.

Her injection contract (`prompts/vendor/classifier_system_prompt.md`, runtime injection 1):
the elements go as structured entries carrying their **current status**, and only the ones
still at `not_encountered` or `surfaced`. Eligibility is the app's: the current scene's
beads plus the ones that belong to no scene, and an id that was not offered moves nothing.
"""

from __future__ import annotations

import json

from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.classify_coverage import (
    _parse,
    _scenes_block,
    _unresolved_block,
)
from app.services.internalization_room.coverage import (
    CoverageStatus,
    initial_state,
    merge,
    remaining_in_scene,
)

P = "P01"


def test_every_element_the_classifier_is_shown_carries_its_current_status() -> None:
    keys = element_keys(P)
    state = merge(initial_state(P), pericope_num=P, engaged=[keys[4]], surfaced=[keys[5]])

    shown = json.loads(_unresolved_block(state, P))

    by_id = {entry["id"]: entry for entry in shown}
    assert set(by_id[keys[5]]) == {"id", "kind", "label", "status"}, (
        "a lista chegava como `- [chave] rótulo`, sem status nenhum, e o prompt pedia "
        "'um avanço a partir do status atual' de um status que ele nunca via"
    )
    assert by_id[keys[5]]["status"] == CoverageStatus.SURFACED.value
    assert by_id[keys[5]]["kind"] == "being"
    assert by_id[keys[6]]["status"] == CoverageStatus.NOT_ENCOUNTERED.value
    assert keys[4] not in by_id, "uma conta já engajada não pode voltar e não precisa ser relida"
    assert {entry["status"] for entry in shown} == {"not_encountered", "surfaced"}


def test_a_bead_stored_under_the_retired_status_is_shown_as_surfaced_not_dropped() -> None:
    keys = element_keys(P)
    state = {**initial_state(P), keys[5]: CoverageStatus.PARTIALLY_ENGAGED.value}

    shown = {entry["id"]: entry["status"] for entry in json.loads(_unresolved_block(state, P))}

    assert shown[keys[5]] == CoverageStatus.SURFACED.value, (
        "o prompt dela só conhece not_encountered e surfaced; mandar a palavra aposentada "
        "nomeia um status que ele não tem, e não mandar a conta congela a conta para sempre"
    )


def test_the_scenes_are_named_by_the_bare_id_the_prompt_asks_for_and_their_title() -> None:
    block = _scenes_block(P)

    assert json.loads(block) == [
        {"id": "S1", "title": "Famine and exile to Moab"},
        {"id": "S2", "title": "Death of Elimelech"},
        {"id": "S3", "title": "Marriages and time passing"},
        {"id": "S4", "title": "Deaths of the sons"},
    ], (
        "a lista de cenas chegava como `- [scene:1] …`, a forma prefixada que o mesmo "
        "prompt manda nunca usar no escopo do reconto"
    )
    assert "scene:" not in block


def test_a_decision_buried_in_a_sentence_of_prose_still_moves_the_beads() -> None:
    wrapped = (
        "Sure — here is the classification for this exchange: "
        '{"decisions": [{"element_id": "scene:1", "new_status": "engaged", "evidence": "told it"}]}'
        " Let me know if you need anything else."
    )

    assert _parse(wrapped)["engaged"] == ["scene:1"], (
        "o leitor aceitava JSON nu ou cercado e mais nada; um objeto embrulhado numa frase "
        "era 'JSON ilegível' e a classificação do turno sumia em silêncio"
    )


THIS_SCENE_AND_THE_SCENELESS = [
    "arc",
    "context",
    "tone",
    "function",
    "scene:2",
    "being:S2:B2",
    "being:S2:B3",
    "being:S2:B4",
    "being:S2:B5",
    "place:S2:PL2",
    "absence:2",
    "preserved:R3",
    "preserved:R5",
    "preserved:R10",
]


def test_the_scene_scoped_list_holds_this_scenes_beads_and_the_ones_of_no_scene() -> None:
    left = [element.key for element in remaining_in_scene(initial_state(P), P, "S2")]

    assert left == THIS_SCENE_AND_THE_SCENELESS, (
        "a lista inteira da passagem ia ao classificador com a equipe ainda na cena 1: contas "
        "de cenas que ninguém abriu, e Noemi da cena 4 respondendo pela Noemi da cena 2"
    )
