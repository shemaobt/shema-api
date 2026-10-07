from app.services.internalization_room.canon.elements import elements_for
from app.services.internalization_room.prompt_blocks import coverage_status_block


def _labels(pericope: str) -> dict[str, str]:
    return {element.key: element.label for element in elements_for(pericope)}


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
