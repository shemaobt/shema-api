"""YHWH is never read letter by letter — it is voiced as the name Marcia's own prompts carry.

The bug this closes: the maps and the Guide write the tetragrammaton as the four consonants
"YHWH", and a voice engine spells letters it cannot pronounce. Nothing between a validated
line and the platform touched that shape until this module ran ahead of the TTS call.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.services.internalization_room.speakable import speakable_text

_PT_CASES = [
    pytest.param("YHWH chamou Rute.", "Senhor Jeová chamou Rute.", id="mid-sentence"),
    pytest.param("Foi YHWH.", "Foi Senhor Jeová.", id="trailing-period"),
    pytest.param("Foi YHWH, dizem.", "Foi Senhor Jeová, dizem.", id="trailing-comma"),
    pytest.param(
        "O narrador nunca diz que foi YHWH",
        "O narrador nunca diz que foi Senhor Jeová",
        id="end-of-line",
    ),
    pytest.param('Ela disse "YHWH" baixinho.', 'Ela disse "Senhor Jeová" baixinho.', id="quoted"),
    pytest.param("—YHWH— ela hesitou.", "—Senhor Jeová— ela hesitou.", id="em-dash"),
]


@pytest.mark.parametrize("text, expected", _PT_CASES)
def test_a_bare_yhwh_becomes_senhor_jeova_whatever_sits_beside_it(text: str, expected: str) -> None:
    assert speakable_text(text, "pt") == expected


def test_a_line_with_no_yhwh_reaches_speakable_text_unchanged() -> None:
    text = "O narrador nunca diz quem trouxe a fome."

    assert speakable_text(text, "pt") == text


_EN_CASES = [
    pytest.param("YHWH called Ruth.", "the LORD called Ruth.", id="mid-sentence"),
    pytest.param("It was YHWH.", "It was the LORD.", id="trailing-period"),
    pytest.param("It was YHWH, they say.", "It was the LORD, they say.", id="trailing-comma"),
    pytest.param(
        "The narrator never says it was YHWH",
        "The narrator never says it was the LORD",
        id="end-of-line",
    ),
    pytest.param('She said "YHWH" quietly.', 'She said "the LORD" quietly.', id="quoted"),
    pytest.param("—YHWH— she hesitated.", "—the LORD— she hesitated.", id="em-dash"),
]


@pytest.mark.parametrize("text, expected", _EN_CASES)
def test_the_same_escape_is_the_lord_in_an_english_line_not_senhor_jeova(
    text: str, expected: str
) -> None:
    assert speakable_text(text, "en") == expected


@pytest.mark.parametrize("language", ["es", "fr"])
def test_a_language_outside_the_table_keeps_the_bare_letters_rather_than_inventing_a_form(
    language: str,
) -> None:
    text = "YHWH chamó a Rut."

    assert speakable_text(text, language) == text


def test_a_figure_link_in_double_square_brackets_is_not_voiced() -> None:
    text = "Pensem em [[FIG_0013-Bread-house-in-Famine]] agora."

    assert speakable_text(text, "pt") == "Pensem em agora."


def test_a_link_followed_by_its_name_leaves_only_the_name() -> None:
    assert speakable_text("[[B3-Naomi]] Noemi ouve.", "pt") == "Noemi ouve."


def test_a_bare_figure_code_is_not_voiced() -> None:
    assert speakable_text("A figura FIG_0013 volta aqui.", "pt") == "A figura volta aqui."


def test_a_scene_code_typed_into_a_reply_is_not_voiced() -> None:
    assert speakable_text("Na cena S2, Rute fica.", "pt") == "Na cena, Rute fica."


def test_a_code_in_parentheses_leaves_no_empty_parentheses() -> None:
    assert speakable_text("Boaz (B13) chega.", "pt") == "Boaz chega."


def test_a_code_with_no_digit_is_not_voiced() -> None:
    assert speakable_text("Voltam para PL_LAND_OF_JUDAH.", "pt") == "Voltam para."


def test_a_bracketed_code_with_no_digit_is_not_voiced_inside_a_sentence() -> None:
    text = "Ela vive em [[PL_ISRAEL-Israel]] desde sempre."

    assert speakable_text(text, "pt") == "Ela vive em desde sempre."


def test_a_bare_code_with_its_slug_attached_goes_whole() -> None:
    assert speakable_text("Falamos de B3-Naomi hoje.", "pt") == "Falamos de hoje."


def test_two_codes_in_a_row_leave_no_orphaned_comma() -> None:
    assert speakable_text("Noemi, B3, Rute chega.", "pt") == "Noemi, Rute chega."


def test_a_code_set_off_by_dashes_leaves_no_orphaned_dash() -> None:
    assert speakable_text("Noemi — B3 — chega.", "pt") == "Noemi chega."


def test_a_code_at_the_end_of_a_clause_leaves_no_comma_before_the_full_stop() -> None:
    assert speakable_text("Rute vê Boaz, B13.", "pt") == "Rute vê Boaz."


def test_a_code_after_a_dash_at_the_end_of_a_clause_leaves_no_dash_before_the_full_stop() -> None:
    assert speakable_text("Rute vê Boaz — B13.", "pt") == "Rute vê Boaz."


def test_a_line_that_is_only_a_code_is_left_empty() -> None:
    assert speakable_text(" [[B3-Naomi]] ", "pt") == ""


_MAPS = Path(__file__).resolve().parent.parent / (
    "app/services/internalization_room/canon/vendor/meaning-map"
)
_LABELS = Path(__file__).resolve().parent.parent / (
    "app/services/internalization_room/canon/element-labels"
)


def _links_in_the_vendored_maps() -> list[str]:
    links: set[str] = set()
    for page in sorted(_MAPS.glob("*.md")):
        links.update(re.findall(r"\[\[[^\]]*\]\]", page.read_text(encoding="utf-8")))
    return sorted(links)


def test_the_vendored_maps_carry_links_for_the_sweep_to_read() -> None:
    assert len(_links_in_the_vendored_maps()) > 200


@pytest.mark.parametrize("link", _links_in_the_vendored_maps())
def test_every_link_in_the_vendored_maps_is_removed(link: str) -> None:
    assert speakable_text(f"Antes {link} depois.", "pt") == "Antes depois."


@pytest.mark.parametrize("link", _links_in_the_vendored_maps())
def test_every_code_in_the_vendored_maps_is_removed_when_bare(link: str) -> None:
    code = link[2:-2].split("-", 1)[0]

    assert speakable_text(f"Antes {code} depois.", "pt") == "Antes depois."


def _catalogue_labels() -> list[str]:
    labels: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, str):
            labels.append(node)
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for catalogue in sorted(_LABELS.glob("*.json")):
        walk(json.loads(catalogue.read_text(encoding="utf-8")))
    return sorted(set(labels))


def test_the_catalogues_carry_labels_for_the_sweep_to_read() -> None:
    assert len(_catalogue_labels()) > 500


@pytest.mark.parametrize("label", _catalogue_labels())
def test_no_catalogue_label_loses_a_word_in_portuguese(label: str) -> None:
    assert speakable_text(label, "pt") == label.replace("YHWH", "Senhor Jeová")


@pytest.mark.parametrize("label", _catalogue_labels())
def test_no_catalogue_label_loses_a_word_in_english(label: str) -> None:
    assert speakable_text(label, "en") == label.replace("YHWH", "the LORD")


@pytest.mark.parametrize("label", _catalogue_labels())
def test_no_catalogue_label_loses_a_word_in_spanish(label: str) -> None:
    assert speakable_text(label, "es") == label


def test_a_line_with_no_code_is_spoken_exactly_as_written() -> None:
    text = "Em Rute 1:6,  depois de dez anos, Noemi volta ; Senhor, LORD, 40 .  "

    assert speakable_text(text, "pt") == text


def test_the_divine_name_is_still_rewritten_beside_a_removed_code() -> None:
    assert (
        speakable_text("[[B10-YHWH]] YHWH visitou o povo.", "pt") == "Senhor Jeová visitou o povo."
    )


def test_a_bare_code_whose_slug_is_the_divine_name_is_removed_before_the_name_is_rewritten() -> (
    None
):
    assert speakable_text("B10-YHWH YHWH visitou o povo.", "pt") == "Senhor Jeová visitou o povo."


def test_a_language_outside_the_table_still_loses_its_codes() -> None:
    assert speakable_text("[[B9-Ruth]] Rut habló.", "es") == "Rut habló."
