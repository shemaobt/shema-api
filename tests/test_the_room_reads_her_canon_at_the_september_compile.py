from __future__ import annotations

from collections import Counter
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import passages as route
from app.services.internalization_room.canon.book_material import (
    LOGS_DIR,
    build_book_material,
    preservation_rules,
    unwalkable,
    vendor_pin,
)
from app.services.internalization_room.canon.elements import elements_for
from app.services.internalization_room.canon.labels import labelled_elements
from app.services.internalization_room.canon.parse_map import MAPS_DIR, load_map
from app.services.internalization_room.progression import resolve

HER_COMPILE = "5b5c8d2b3ae7632279c07017224f861ae369b0d7"
RUTH = [f"P{n:02d}" for n in range(1, 15)]


def test_the_room_names_her_compile_of_29_september_and_holds_the_fourteen_passages_of_ruth() -> (
    None
):
    maps = sorted(path.name for path in MAPS_DIR.glob("*.md"))
    logs = sorted(path.name for path in LOGS_DIR.glob("*.md"))

    assert vendor_pin() == HER_COMPILE
    assert [name[:3] for name in maps] == RUTH
    assert [name[:3] for name in logs] == RUTH


def test_ruth_carries_ninety_nine_rules_of_what_not_to_decide_split_as_she_counts_them() -> None:
    rules = Counter(rule.pericope for rule in preservation_rules("Ruth"))

    assert sum(rules.values()) == 99
    assert {pericope: rules[pericope] for pericope in RUTH[7:]} == {
        "P08": 10,
        "P09": 11,
        "P10": 8,
        "P11": 10,
        "P12": 6,
        "P13": 9,
        "P14": 6,
    }


@pytest.mark.parametrize("pericope", RUTH)
def test_every_ruth_passage_opens_and_none_is_refused_as_pending(pericope: str) -> None:
    assert unwalkable(load_map(pericope)) is None


async def test_the_wheel_offers_all_fourteen_passages_of_ruth_in_order(
    monkeypatch: pytest.MonkeyPatch, db_session: AsyncSession
) -> None:
    async def voiced(text: str, **_: object) -> tuple[SimpleNamespace, bool]:
        return SimpleNamespace(key=f"tts/v/{abs(hash(text))}.mp3"), False

    monkeypatch.setattr(route.room, "synthesize_facilitator_speech", voiced)

    answer = await route.passages("Ruth", language="pt", db=db_session)

    assert [view.pericope for view in answer.passages if view.kind == "passage"] == RUTH


def test_a_team_that_finished_the_seventh_passage_is_sent_to_the_eighth() -> None:
    assert resolve(set(RUTH[:7])) == "P08"
    assert resolve(set(RUTH[:13])) == "P14"
    assert resolve(set(RUTH)) is None


def test_the_lines_that_pointed_ahead_in_the_book_are_gone_from_p05_and_p07() -> None:
    p05 = load_map("P05")
    p07 = load_map("P07")
    scene_four = next(scene for scene in p07.scenes if scene.number == 4)

    assert "the town gate in 4:1" not in p05.body
    assert "Naomi's plan at 3:1" not in p07.body
    assert "Naomi's plan at 3:1" not in (scene_four.absence or "")


def test_p09_carries_her_new_title_and_p10_and_p13_her_new_scene_headings() -> None:
    p09, p10, p13 = load_map("P09"), load_map("P10"), load_map("P13")

    assert p09.title == (
        "The threshing-floor night: the wing asked for, the word redeemer spoken, the oath"
    )
    assert [scene.title for scene in p10.scenes] == [
        "The dawn at the floor: the secrecy word and the six measures",
        'To her mother-in-law: the question, the report, and "sit still"',
    ]
    assert [scene.title for scene in p13.scenes][:2] == [
        "The marriage, the conception, the birth",
        "The women's words to Naomi",
    ]


def test_the_corrected_note_of_p01_r10_is_the_one_the_voice_reads() -> None:
    note = next(
        rule.note
        for rule in preservation_rules("Ruth")
        if (rule.pericope, rule.rule_id) == ("P01", "R10")
    )

    assert note.startswith(
        "The source text does not pair the wives with their husbands at 1:4. "
        "The Mahlon\u2013Ruth pairing is said at 4:10; the text never says whose wife Orpah was."
    )


def test_the_ruth_panorama_lists_her_ninety_nine_rules() -> None:
    material = build_book_material("Ruth")
    rule_lines = [line for line in material.splitlines() if line.startswith("- [P")]

    assert len(rule_lines) == 99
    assert Counter(line[3:6] for line in rule_lines)["P08"] == 10
    assert "14 passages, in story order)" in material


@pytest.mark.parametrize("pericope", RUTH)
def test_no_ruth_passage_loses_its_labels_after_the_move(pericope: str) -> None:
    labelled = labelled_elements(pericope)

    assert [element.key for element in labelled] == [
        element.key for element in elements_for(pericope)
    ]
    assert all(element.label_en.strip() for element in labelled)
