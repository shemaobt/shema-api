import logging

import pytest

from app.services.internalization_room.canon import names
from app.services.internalization_room.canon.elements import (
    ElementKind,
    element_keys,
    elements_for,
    elements_of,
)
from app.services.internalization_room.canon.labels import labelled_elements
from app.services.internalization_room.canon.parse_map import (
    MAPS_DIR,
    load_book,
    load_map,
    parse_map,
)
from app.services.internalization_room.prompt_blocks import coverage_status_block

NAMES_LOGGER = "app.services.internalization_room.canon.names"
UNRESOLVED = "(unresolved — needs grounded wording)"
UNNAMED = "someone the text leaves unnamed here"


def _labels(pericope: str) -> dict[str, str]:
    return {element.key: element.label for element in elements_for(pericope)}


def _labels_of_map(pericope: str) -> dict[str, str]:
    meaning_map = load_map(pericope)
    return {element.key: element.label for element in elements_of(meaning_map)}


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

    assert _labels("P01")["being:S4:B3"] == "the woman", (
        "o nome que o texto tira em 1:5 voltava ao Guia"
    )
    assert ", the woman" in ledger
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


@pytest.mark.parametrize(
    "line",
    ["[[CB_9999-Nowhere]] — [[B3-Naomi]]", "[[CB_9999-Nowhere]] — active at Proposition 2"],
)
def test_a_bare_link_or_a_flag_note_after_the_dash_is_no_gloss(line: str) -> None:
    labels = _ruth_1_with_famine_written_as(line)

    assert labels["object:S1:CB_9999"] == UNRESOLVED, (
        "o que vinha depois do travessão ia ao Guia mesmo sendo um código cru ou uma nota"
    )


def test_a_retired_entry_of_her_names_list_is_never_a_name() -> None:
    labels = _ruth_1_with_famine_written_as("[[O17-Old-Thing]] — רָעָב / famine")

    assert labels["object:S1:O17"] == "famine", (
        "a entrada aposentada '[retired in V0.3; See O26]' ia ao Guia como se fosse um nome"
    )


@pytest.mark.parametrize(
    ("code", "english"),
    [
        ("O99", "[reserved for P08-p10 in-compilation absorptions]"),
        ("O98_RETIRED", "Old Thing"),
    ],
)
def test_a_reserved_or_retired_mark_on_the_entry_or_its_key_skips_it(
    monkeypatch: pytest.MonkeyPatch, code: str, english: str
) -> None:
    monkeypatch.setattr(names, "_names_list", lambda book: {code: {"english": english}})

    labels = _ruth_1_with_famine_written_as(f"[[{code}-Old-Thing]] — רָעָב / famine")

    assert labels[f"object:S1:{code}"] == "famine"


def test_the_cloak_of_ruth_3_15_is_the_cloak_in_that_passage_alone() -> None:
    assert _labels("P10")["object:S1:O13"] == "The Cloak", (
        "em 3:15 o texto diz mitpachat, o manto, e o Guia lia o 'Your Garments' do 3:3"
    )
    assert _labels("P08")["object:S1:O13"] == "Your Garments"


def test_the_unnamed_husband_of_ruth_2_11_is_given_no_name_and_no_description() -> None:
    labels = _labels("P06")

    assert labels["being:S2:ruth-s-deceased-husband-your-hus"] == UNNAMED, (
        "o Guia lia 'Ruth's deceased husband', uma descrição que o texto não dá"
    )
    assert "deceased husband" not in coverage_status_block({}, "P06")


def test_a_being_her_coordinates_do_not_know_reads_the_maps_own_words_for_it() -> None:
    assert _labels("P06")["being:S2:ruth-s-father-and-mother-your-fa"] == (
        '"your father and your mother"'
    ), "os pais de Rute eram 'Ruth's father and mother — אָבִיךְ וְאִמֵּךְ / …', hebraico e tudo"
    assert _labels("P07")["being:S3:the-dead-of-the-household-the-de"] == '"the dead"'
    assert _labels("P12")["being:S1:the-dead-the-dead"] == '"the dead"'


def test_an_unnamed_being_with_a_form_or_a_role_word_reads_it_and_nothing_more() -> None:
    assert _labels("P11")["being:S3:the-dead-the-dead"] == "the dead (unnamed here)", (
        "o morto de 4:5 era 'The dead — הַמֵּת / \"the dead\"', a linha do mapa inteira"
    )
    assert _labels("P13")["being:S2:the-child-a-redeemer"] == "a redeemer"
    assert _labels("P13")["being:S1:the-child-a-son"] == "a son"


def test_a_form_outside_her_table_reads_its_own_words_and_is_not_called_unnamed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinates = names._beings_by_scene("P13")
    boy = {"being_id": "B?", "role_in_scene": "SON", "referential_form": "THE_BOY"}
    monkeypatch.setattr(names, "_beings_by_scene", lambda pericope: {**coordinates, 1: [boy]})

    assert _labels_of_map("P13")["being:S1:the-child-a-son"] == "the boy"


def test_a_bead_renamed_by_her_keeps_the_key_its_coverage_is_stored_under() -> None:
    keys = element_keys("P06")

    assert "being:S2:ruth-s-deceased-husband-your-hus" in keys, (
        "a chave saía do rótulo, e a cobertura gravada sob a antiga ficava órfã"
    )
    assert "being:S2:ruth-s-father-and-mother-your-fa" in keys
    assert "being:S4:B3" in element_keys("P01")


def test_every_being_ruth_leaves_unnamed_reads_on_the_desk_what_the_voice_is_told() -> None:
    drifted = []
    for meaning_map in load_book("Ruth"):
        pericope = meaning_map.pericope_num
        desk = {element.key: element.label_en for element in labelled_elements(pericope)}
        for element in elements_for(pericope):
            if element.kind is ElementKind.BEING and element.key.split(":")[-1].islower():
                said = desk[element.key]
                if said[:1].lower() + said[1:] != element.label.strip('"'):
                    drifted.append(f"{pericope} {element.key}: {said!r} / {element.label!r}")

    assert drifted == [], "a conta dava ao ser sem nome palavras que a voz não ouvia"
