import logging

import pytest

from app.services.internalization_room.canon.elements import elements_for, elements_of
from app.services.internalization_room.canon.parse_map import MAPS_DIR, parse_map
from app.services.internalization_room.prompt_blocks import coverage_status_block

NAMES_LOGGER = "app.services.internalization_room.canon.names"
UNRESOLVED = "(unresolved — needs grounded wording)"


def _labels(pericope: str) -> dict[str, str]:
    return {element.key: element.label for element in elements_for(pericope)}


def _ruth_1_with_famine_written_as(line: str) -> dict[str, str]:
    text = (MAPS_DIR / "P01-Ruth-1-1-5.md").read_text(encoding="utf-8")
    edited = text.replace("[[O1-Famine]] — רָעָב / famine", line)
    meaning_map = parse_map(edited, source="P01-edited")
    return {element.key: element.label for element in elements_of(meaning_map)}


def test_a_code_in_her_names_list_is_named_by_it_not_by_the_tail_of_its_map_line() -> None:
    labels = _labels("P02")

    assert labels["being:S2:B2"] == "Elimelech", (
        "a cauda da linha do mapa levava ', [[B4-Mahlon]], [[B5-Chilion]] — collectively …' ao Guia"
    )
    assert _labels("P01")["being:S1:B3"] == "Naomi", "o Guia lia 'נָעֳמִי / Naomi', hebraico e tudo"


def test_the_woman_of_ruth_1_5_reaches_the_voice_as_the_woman_with_no_name_beside_her() -> None:
    ledger = coverage_status_block({}, "P01")

    assert "the woman @ S4" in ledger
    assert "Naomi @ S4" not in ledger, "o nome que o texto tira em 1:5 voltava ao Guia"
    assert "(Naomi)" not in ledger, (
        "o Guia lia 'הָאִשָּה (נָעֳמִי) / \"the woman\" (Naomi) @ S4', com o nome ao lado"
    )


def test_a_code_her_names_list_does_not_carry_reads_the_maps_own_gloss() -> None:
    labels = _labels("P12")

    assert labels["object:S2:CB_0010"] == '"the house of Israel"', (
        "o Guia lia 'בֵּית יִשְׂרָאֵל / \"the house of [[PL_ISRAEL-Israel]] Israel\"', link e tudo"
    )
    assert _labels("P01")["object:S1:CB_0030"] == "sojourning"


def test_a_code_found_nowhere_reads_the_placeholder_and_is_logged_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger=NAMES_LOGGER):
        labels = _ruth_1_with_famine_written_as("רָעָב / famine ([[CB_9999-Nowhere]])")

    assert labels["object:S1:CB_9999"] == UNRESOLVED, (
        "um código sem nome na lista dela nem glosa no mapa ia ao Guia com palavras nossas"
    )
    misses = [record for record in caplog.records if record.name == NAMES_LOGGER]
    assert len(misses) == 1, "a falta passava calada e ninguém a corrigia no cânon"
    assert "CB_9999" in misses[0].getMessage()
