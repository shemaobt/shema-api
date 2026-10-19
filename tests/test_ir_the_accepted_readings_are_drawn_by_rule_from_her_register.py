from __future__ import annotations

import re
from pathlib import Path

from app.services.internalization_room.canon.accepted_readings import (
    ACCEPTED_READINGS_HEADER,
    CUTS,
    DROPS,
    SCOPES,
    accepted_ids_for,
    accepted_lines,
    accepted_readings_from,
    accepted_readings_of,
)
from app.services.internalization_room.canon.parse_map import VENDOR

GUIDE_PROMPT = (
    Path(__file__).parents[1] / "app/services/internalization_room/prompts/guide_system_prompt.md"
)

P11_LOG = VENDOR / "compilation-log" / "P11-Ruth-4-1-8-COMPILATION-LOG.md"
P11_COORDINATES = VENDOR / "meaning-coordinates" / "P11-Ruth-4-1-8-MEANING-COORDINATES.md"
RUTH = [f"P{n:02d}" for n in range(1, 15)]

P11_S4_R5 = (
    "- R5: A team telling 'and gave it to Boaz' is correct, not an addition. "
    "The voice accepts it and does not correct or remark on it."
)


def _line(pericope: str, scene: str, rid: str) -> str:
    lines = accepted_lines(accepted_readings_of(pericope).items, scene)
    return next((line for line in lines if line.startswith(f"- {rid}: ")), "")


def test_a_scenes_readings_are_its_own_and_never_another_scenes() -> None:
    assert _line("P08", "S1", "R2") and not _line("P08", "S2", "R2"), (
        "o casamento ao lado do lugar de descanso aparecia fora da cena 1"
    )
    assert _line("P11", "S4", "R5"), "o «deu pro Boaz» não chegava à cena 4"
    assert not any(_line("P11", scene, "R5") for scene in ("S1", "S2", "S3")), (
        "o «deu pro Boaz» chegava a uma cena antes da sandália"
    )
    assert _line("P13", "S3", "R8") and not (_line("P13", "S1", "R8") or _line("P13", "S2", "R8"))
    assert _line("P10", "S2", "R5") and not _line("P10", "S1", "R5")
    assert _line("P08", "S1", "R10") and not _line("P08", "S2", "R10")
    assert _line("P10", "S1", "R8") and not _line("P10", "S2", "R8")
    assert _line("P11", "S2", "R13") and not _line("P11", "S3", "R13")
    assert _line("P12", "S2", "R8") and not _line("P12", "S1", "R8"), (
        "um item cujo applies_to era mais largo que a frase vazava para a cena vizinha"
    )


def test_her_named_cases_reach_the_voice_in_her_words() -> None:
    assert _line("P11", "S4", "R5") == P11_S4_R5
    resting = _line("P08", "S1", "R2")
    assert 'keeps "a resting place" and adds marriage' in resting
    assert "is accepted without comment" in resting
    assert "offered back gently" in resting, "a devolução na mesma frase da aceitação se perdia"
    for pericope, scene, rid in (("P13", "S3", "R8"), ("P14", "S1", "R4")):
        king = _line(pericope, scene, rid)
        assert "'King David' ('o rei Davi') is a nuance" in king
        assert "without a send-back" in king
    how_did_it_go = _line("P10", "S2", "R5")
    assert "('como foi, minha filha?')" in how_did_it_go, (
        "a frase era cortada antes do parêntese e «como foi, minha filha?» se partia"
    )
    assert "a nuance, named once, not sent back" in how_did_it_go
    wing = _line("P09", "S2", "R1")
    assert "is not an addition" in wing and "offer it back as a missing detail" in wing


def test_the_ids_handed_are_the_entries_of_the_lines_in_canon_order() -> None:
    assert accepted_ids_for(accepted_readings_of("P08").items, "S1") == [
        "R1",
        "R2",
        "R4",
        "R9",
        "R10",
        "R11",
    ]
    assert accepted_ids_for(accepted_readings_of("P11").items, "S4") == ["R5"]
    assert accepted_ids_for(accepted_readings_of("P01").items, "S1") == []


def test_no_passage_before_ruth_3_and_no_scene_without_a_ruling_has_a_reading() -> None:
    assert [p for p in RUTH[:7] if accepted_readings_of(p).items] == [], (
        "uma passagem de Rute 1 e 2 recebia leituras aceitas"
    )
    for pericope, scene in (("P09", "S1"), ("P09", "S3"), ("P11", "S3")):
        assert accepted_lines(accepted_readings_of(pericope).items, scene) == [], (
            f"{pericope} {scene}, sem nenhuma regra, recebia linhas"
        )


def test_a_never_list_a_silence_and_a_never_sentence_planted_in_her_register_never_reach_the_voice() -> (  # noqa: E501
    None
):
    anchor = "The voice accepts it and does not correct or remark on it. Voice and team"
    planted = (
        "For the voice only, never to be said: do not say the sandal was a shame; a team telling "
        "'he threw the sandal down' is accepted without comment. The text does not say who kept "
        "the sandal; a team telling 'Boaz kept it' is correct. Never say that Ruth was at the gate."
    )
    log = P11_LOG.read_text(encoding="utf-8")
    assert log.count(anchor) == 1
    sabotaged = log.replace(anchor, anchor.replace(" Voice and team", f" {planted} Voice and team"))

    readings = accepted_readings_from("P11", sabotaged, P11_COORDINATES.read_text(encoding="utf-8"))

    assert accepted_lines(readings.items, "S4") == [
        f"{P11_S4_R5} A team telling 'he threw the sandal down' is accepted without comment."
    ], "a cláusula limpa de aceitação não sobrevivia ao lado da lista do que não dizer"
    every_line = "\n".join(
        line for scene in ("S1", "S2", "S3", "S4") for line in accepted_lines(readings.items, scene)
    )
    assert not re.search(
        r"shame|Never|does not say|Ruth was at the gate|Boaz kept it", every_line
    ), "o que o mapa retém chegava à voz"
    assert [(x.why, x.text[:40]) for x in readings.excluded] == [
        ("silence", "The text does not say who kept the sanda")
    ], "o silêncio não era barrado pelo guarda"
    pinned = accepted_readings_of("P11").items
    for scene in ("S1", "S2", "S3"):
        assert accepted_lines(readings.items, scene) == accepted_lines(pinned, scene)


def test_every_cut_drop_and_scope_still_bites_on_the_pinned_canon() -> None:
    readings = {pericope: accepted_readings_of(pericope) for pericope in RUTH}
    by_key = {item.key: item for r in readings.values() for item in r.items}
    for key, cuts in CUTS.items():
        assert key in by_key, f"o corte {key} já não encontrava o seu item"
        assert not any(cut in by_key[key].text for cut in cuts), f"o corte {key} não cortou"
    for key in DROPS:
        assert key in readings[key[:3]].candidates, f"o descarte {key} já não descartava nada"
        assert key not in by_key, f"o descarte {key} chegava à voz"
    for key, scenes in SCOPES.items():
        assert by_key[key].scenes == tuple(scenes), f"o escopo {key} não prendia a cena"


def test_the_guard_holds_nothing_back_on_the_pinned_canon() -> None:
    held = [x.key for pericope in RUTH for x in accepted_readings_of(pericope).excluded]

    assert held == [], "o cânone fixado tinha itens barrados pelo guarda"


def test_a_text_fact_a_code_and_a_cut_that_no_longer_fits_are_held_back_naming_why() -> None:
    anchor = "The voice accepts it and does not correct or remark on it. Voice and team"
    planted = (
        "A team telling 'he took off his shoe' is accepted without comment, as the Hebrew "
        "word allows. A team telling 'his shoe' is correct (FIG_0168)."
    )
    log = P11_LOG.read_text(encoding="utf-8")
    assert log.count(anchor) == 1 and log.count("OPTIONAL (FIG_0167): ") == 1
    sabotaged = log.replace(
        anchor, anchor.replace(" Voice and team", f" {planted} Voice and team")
    ).replace("OPTIONAL (FIG_0167): ", "OPTIONAL (FIG_0167) — ")

    readings = accepted_readings_from("P11", sabotaged, P11_COORDINATES.read_text(encoding="utf-8"))

    held = {(x.why[:26], x.text[:40]) for x in readings.excluded}
    assert held == {
        ("fact", "A team telling 'he took off his shoe' is"),
        ("code", "A team telling 'his shoe' is correct (FI"),
        ("cut not found exactly once", "OPTIONAL (FIG_0167) — 'I will uncover yo"),
    }, "um fato do texto, um código ou um corte que já não cabia chegava à voz"
    every_line = "\n".join(
        line for scene in ("S1", "S2", "S3", "S4") for line in accepted_lines(readings.items, scene)
    )
    assert "shoe" not in every_line and "FIG_" not in every_line and "OPTIONAL" not in every_line


def test_the_header_handed_to_the_guide_is_the_one_her_prompt_quotes_byte_for_byte() -> None:
    quoted = re.findall(
        r'"(ACCEPTED READINGS FOR THE SCENE THIS TELLING CHECKS \(.*?)"',
        GUIDE_PROMPT.read_text(encoding="utf-8"),
    )

    assert quoted == [ACCEPTED_READINGS_HEADER], (
        "o cabeçalho que o Guia recebia já não era o que o prompt dela cita"
    )
