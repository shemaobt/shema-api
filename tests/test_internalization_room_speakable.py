"""What the team hears: YHWH is voiced as a name, and no canon code is voiced at all.

The first bug: the maps and the Guide write the tetragrammaton as the four consonants "YHWH",
and a voice engine spells letters it cannot pronounce. Nothing between a validated line and
the platform touched that shape until this module ran ahead of the TTS call.

The second (ENG-1337): the same maps carry codes — `B3`, `FIG_0013`, `[[B3-Naomi]]` — and the
Guide quotes them, so the voice read letters and numbers aloud. A code is removed, never
replaced by its label. The sweeps read the vendored maps and the label catalogues from disk, so
what counts as a code is the canon's own list and no expected value comes from the module under
test; each sweep is one case that names its offenders, as the house does for a list too long to
be a parametrize. A word that only looks like a code (`MP3`, `CO2`) is spoken.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

from app.services.internalization_room import speakable
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
    assert speakable_text("Na cena T2, Rute fica.", "pt") == "Na cena, Rute fica."


def test_a_code_in_parentheses_leaves_no_empty_parentheses() -> None:
    assert speakable_text("Boaz (B13) chega.", "pt") == "Boaz chega."


def test_a_code_with_no_digit_is_not_voiced() -> None:
    assert speakable_text("Voltam para PL_LAND_OF_JUDAH.", "pt") == "Voltam para."


def test_a_bracketed_code_with_no_digit_is_not_voiced_inside_a_sentence() -> None:
    text = "Ela vive em [[PL_ISRAEL-Israel]] desde sempre."

    assert speakable_text(text, "pt") == "Ela vive em desde sempre."


def test_a_bare_code_with_its_slug_attached_goes_whole() -> None:
    assert speakable_text("Falamos de B3-Naomi hoje.", "pt") == "Falamos de hoje."


@pytest.mark.parametrize(
    "word",
    ["MP3", "A1", "CO2", "F1", "Ctrl+F1", "AT1 e NT2"],
)
def test_a_word_that_only_looks_like_a_code_is_spoken(word: str) -> None:
    text = f"Ouçam o {word} agora."

    assert speakable_text(text, "pt") == text


def test_a_link_that_does_not_begin_with_a_code_is_spoken() -> None:
    text = "Veja [[Gênesis]] agora."

    assert speakable_text(text, "pt") == text


_MENDED = [
    pytest.param("Noemi, B3, Rute chega.", "Noemi, Rute chega.", id="two-commas"),
    pytest.param("Noemi — B3 — chega.", "Noemi chega.", id="em-dash-pair"),
    pytest.param("Noemi - B3 - chega.", "Noemi chega.", id="hyphen-pair"),
    pytest.param("Rute vê Boaz, B13.", "Rute vê Boaz.", id="comma-before-full-stop"),
    pytest.param("Rute vê Boaz — B13.", "Rute vê Boaz.", id="dash-before-full-stop"),
    pytest.param("Ela disse: B3, e saiu.", "Ela disse, e saiu.", id="colon-then-comma"),
    pytest.param("Ela, B3!, volta.", "Ela! volta.", id="comma-bang-comma"),
    pytest.param('Ele disse "B3" ontem.', "Ele disse ontem.", id="empty-straight-quotes"),
    pytest.param(
        "Ele disse \N{LEFT DOUBLE QUOTATION MARK}B3\N{RIGHT DOUBLE QUOTATION MARK} ontem.",
        "Ele disse ontem.",
        id="empty-curly-quotes",
    ),
    pytest.param(
        "Rute (ver B3) chega.", "Rute (ver) chega.", id="no-space-before-a-closing-bracket"
    ),
    pytest.param("Quem, B3?, disse.", "Quem? disse.", id="question-then-comma"),
    pytest.param("Um texto: B3. Outro.", "Um texto. Outro.", id="colon-before-full-stop"),
    pytest.param("B3/B4 e B3-B4", "e", id="slash-and-hyphen-joined-codes"),
    pytest.param("Naomi, B3 ,Ruth", "Naomi, Ruth", id="space-after-the-comma-kept"),
    pytest.param("Noemi\u00a0B3\u00a0chega.", "Noemi chega.", id="non-breaking-space"),
    pytest.param("Linha um B3\nLinha dois.", "Linha um\nLinha dois.", id="trim-per-line"),
    pytest.param(
        "B3 abre\n  recuo B4 fica.", "abre\nrecuo fica.", id="indent-of-a-line-with-a-code"
    ),
    pytest.param(
        "Linha um.\n  Recuo.\nTem B3.", "Linha um.\n  Recuo.\nTem.", id="other-lines-untouched"
    ),
    pytest.param(" [[B3-Naomi]] ", "", id="only-a-code"),
]


@pytest.mark.parametrize("text, expected", _MENDED)
def test_the_seam_where_a_code_stood_is_mended(text: str, expected: str) -> None:
    assert speakable_text(text, "pt") == expected


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


def test_every_link_in_the_vendored_maps_is_removed() -> None:
    links = _links_in_the_vendored_maps()

    offenders = [
        link for link in links if speakable_text(f"Antes {link} depois.", "pt") != "Antes depois."
    ]

    assert len(links) > 200
    assert offenders == []


def test_every_code_in_the_vendored_maps_is_removed_when_bare() -> None:
    codes = sorted({link[2:-2].split("-", 1)[0] for link in _links_in_the_vendored_maps()})

    offenders = [
        code for code in codes if speakable_text(f"Antes {code} depois.", "pt") != "Antes depois."
    ]

    assert len(codes) > 200
    assert offenders == []


def _catalogue_labels() -> list[str]:
    labels: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, str):
            labels.add(node)
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for catalogue in sorted(_LABELS.glob("*.json")):
        walk(json.loads(catalogue.read_text(encoding="utf-8")))
    return sorted(labels)


def _labels_that_change(language: str, divine_name: str) -> list[str]:
    return [
        label
        for label in _catalogue_labels()
        if speakable_text(label, language) != label.replace("YHWH", divine_name)
    ]


def test_no_catalogue_label_loses_a_word_in_portuguese() -> None:
    assert len(_catalogue_labels()) > 500
    assert _labels_that_change("pt", "Senhor Jeová") == []


def test_no_catalogue_label_loses_a_word_in_english() -> None:
    assert _labels_that_change("en", "the LORD") == []


def test_no_catalogue_label_loses_a_word_in_spanish() -> None:
    assert _labels_that_change("es", "YHWH") == []


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


def test_a_pin_with_no_vendored_map_fails_the_import_instead_of_deleting_every_number(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Path, "glob", lambda self, pattern: iter(()))
    spec = importlib.util.spec_from_file_location("speakable_without_maps", speakable.__file__)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)

    with pytest.raises(RuntimeError):
        spec.loader.exec_module(module)
