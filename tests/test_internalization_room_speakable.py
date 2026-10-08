"""What the team hears: the voiced text, made speakable by four rewrites in a fixed order.

Formatting marks come off and every word stays; the canon codes the maps carry — `B3`,
`FIG_0013`, `[[B3-Naomi]]` — are removed and the seam they leave is mended; a question folded
after a colon, a semicolon or a dash stands alone; and "YHWH" is voiced as a name, never as
four letters. The first, third and fourth are Marcia's (her speakableTest.ts, ported case for
case, her known limits and invariants included); the second is ours and runs between her first
and second, and each of its seams has its case. The sweeps read the vendored maps and the label
catalogues from disk, so what counts as a code is the canon's own list and no expected value
comes from the module under test; each sweep is one case that names its offenders, as the
house does for a list too long to be a parametrize. A word that only looks like a code (`MP3`,
`CO2`) is spoken.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

from app.services.internalization_room import speakable
from app.services.internalization_room.speakable import (
    speakable_text,
    standalone_questions,
    strip_markdown,
)

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


_EN_DASH = "\N{EN DASH}"
_LEFT_QUOTE = "\N{LEFT DOUBLE QUOTATION MARK}"
_RIGHT_QUOTE = "\N{RIGHT DOUBLE QUOTATION MARK}"

#: Every seam a removed code leaves, in one list: the seam test reads it, and so does the
#: invariant that a line already made speakable comes back equal, so no seam is pinned without
#: its idempotence being checked.
_SEAMS = [
    pytest.param(
        "A figura FIG_0013 volta aqui.", "pt", "A figura volta aqui.", id="a-bare-figure-code"
    ),
    pytest.param(
        "Na cena S2, Rute fica.", "pt", "Na cena, Rute fica.", id="a-scene-code-in-a-reply"
    ),
    pytest.param("Cena [[S1]] aqui.", "pt", "Cena aqui.", id="a-scene-link"),
    pytest.param(
        "Effect on scene: named outright only at v.22 in S3.",
        "en",
        "Effect on scene: named outright only at v.22 in.",
        id="a-scene-code-in-map-prose",
    ),
    pytest.param("Boaz (B13) chega.", "pt", "Boaz chega.", id="a-code-alone-in-parentheses"),
    pytest.param("Voltam para PL_LAND_OF_JUDAH.", "pt", "Voltam para.", id="a-code-with-no-digit"),
    pytest.param(
        "Ela vive em [[PL_ISRAEL-Israel]] desde sempre.",
        "pt",
        "Ela vive em desde sempre.",
        id="a-bracketed-code-with-no-digit",
    ),
    pytest.param(
        "Falamos de B3-Naomi hoje.", "pt", "Falamos de hoje.", id="a-bare-code-and-its-slug"
    ),
    pytest.param("[[B3-Naomi]] Noemi ouve.", "pt", "Noemi ouve.", id="a-link-before-its-name"),
    pytest.param(
        "Pensem em [[FIG_0013-Bread-house-in-Famine]] agora.",
        "pt",
        "Pensem em Bread house in Famine agora.",
        id="seam-d-a-figure-link-speaks-its-slug",
    ),
    pytest.param(
        "Veja [[ FIG_0013-Bread-house ]] agora.",
        "pt",
        "Veja Bread house agora.",
        id="seam-d-a-spaced-figure-link-speaks-its-slug",
    ),
    pytest.param(
        "Pensem em [[FIG_0013]] agora.", "pt", "Pensem em agora.", id="a-figure-link-with-no-slug"
    ),
    pytest.param(
        "Pensem em THE_LAND_AFFLICTED_BY_FAMINE e em LAND_OF_BIRTH_UNNAMED agora.",
        "pt",
        "Pensem em e em agora.",
        id="seam-e-two-all-caps-places",
    ),
    pytest.param(
        "Vejam OBJECT_KIND e STATES_AS_TRUE.", "pt", "Vejam.", id="seam-e-two-all-caps-fields"
    ),
    pytest.param("Noemi, B3, Rute chega.", "pt", "Noemi, Rute chega.", id="two-commas"),
    pytest.param("Noemi — B3 — chega.", "pt", "Noemi chega.", id="em-dash-pair"),
    pytest.param("Noemi - B3 - chega.", "pt", "Noemi chega.", id="hyphen-pair"),
    pytest.param("Rute vê Boaz, B13.", "pt", "Rute vê Boaz.", id="comma-before-full-stop"),
    pytest.param("Rute vê Boaz — B13.", "pt", "Rute vê Boaz.", id="dash-before-full-stop"),
    pytest.param("Rute vê Boaz - B13.", "pt", "Rute vê Boaz.", id="spaced-hyphen-before-full-stop"),
    pytest.param("Ela disse: B3, e saiu.", "pt", "Ela disse, e saiu.", id="colon-then-comma"),
    pytest.param("Ela, B3!, volta.", "pt", "Ela! volta.", id="comma-bang-comma"),
    pytest.param('Ele disse "B3" ontem.', "pt", "Ele disse ontem.", id="empty-straight-quotes"),
    pytest.param(
        f"Ele disse {_LEFT_QUOTE}B3{_RIGHT_QUOTE} ontem.",
        "pt",
        "Ele disse ontem.",
        id="empty-curly-quotes",
    ),
    pytest.param(
        "Rute (ver B3) chega.", "pt", "Rute (ver) chega.", id="no-space-before-a-closing-bracket"
    ),
    pytest.param("Quem, B3?, disse.", "pt", "Quem? disse.", id="question-then-comma"),
    pytest.param(
        "Ele disse \N{LEFT-POINTING DOUBLE ANGLE QUOTATION MARK}B3"
        "\N{RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK} ontem.",
        "pt",
        "Ele disse ontem.",
        id="empty-guillemets",
    ),
    pytest.param(
        "Ele disse \N{LEFT SINGLE QUOTATION MARK}B3\N{RIGHT SINGLE QUOTATION MARK} ontem.",
        "pt",
        "Ele disse ontem.",
        id="empty-single-curly-quotes",
    ),
    pytest.param("Veja o resto, etc., B3.", "pt", "Veja o resto, etc.", id="no-double-full-stop"),
    pytest.param("Fim... B3 e mais.", "pt", "Fim... mais.", id="an-ellipsis-is-kept"),
    pytest.param(
        "Fim. B3... e mais.", "pt", "Fim. ... e mais.", id="an-ellipsis-after-a-code-is-kept"
    ),
    pytest.param("Um texto: B3. Outro.", "pt", "Um texto. Outro.", id="colon-before-full-stop"),
    pytest.param("B3/B4 e B3-B4", "pt", "", id="slash-and-hyphen-joined-codes"),
    pytest.param("Naomi, B3 ,Ruth", "pt", "Naomi, Ruth", id="space-after-the-comma-kept"),
    pytest.param(
        "Noemi\N{NO-BREAK SPACE}B3\N{NO-BREAK SPACE}chega.",
        "pt",
        "Noemi chega.",
        id="non-breaking-space",
    ),
    pytest.param(
        "Linha um B3\nLinha dois.", "pt", "Linha um Linha dois.", id="a-code-at-the-end-of-a-line"
    ),
    pytest.param(
        "B3 abre\n  recuo B4 fica.", "pt", "abre recuo fica.", id="a-code-on-each-of-two-lines"
    ),
    pytest.param(
        "Linha um.\n  Recuo.\nTem B3.",
        "pt",
        "Linha um. Recuo. Tem.",
        id="a-code-on-the-last-of-three-lines",
    ),
    pytest.param(" [[B3-Naomi]] ", "pt", "", id="only-a-code"),
    pytest.param(
        "As figuras B3, B4 e B5 choram.",
        "pt",
        "As figuras choram.",
        id="seam-a-a-list-of-codes-goes-with-its-commas-and-its-e",
    ),
    pytest.param("In B3 and B4, Naomi weeps.", "en", "In, Naomi weeps.", id="a-list-joined-by-and"),
    pytest.param("As cenas B3 a B5 choram.", "pt", "As cenas choram.", id="a-range-with-a"),
    pytest.param("The scenes B3 to B5 weep.", "en", "The scenes weep.", id="a-range-with-to"),
    pytest.param(
        f"As cenas B1{_EN_DASH}B5 choram.", "pt", "As cenas choram.", id="a-range-with-an-en-dash"
    ),
    pytest.param("As cenas B1-B5 choram.", "pt", "As cenas choram.", id="a-range-with-a-hyphen"),
    pytest.param(
        "As cenas B3 - B5 choram.", "pt", "As cenas choram.", id="a-range-with-a-spaced-hyphen"
    ),
    pytest.param(
        "As cenas B3 — B5 choram.", "pt", "As cenas choram.", id="a-range-with-an-em-dash"
    ),
    pytest.param(
        "As cenas B3 - B5 choram?", "pt", "As cenas choram?", id="a-spaced-range-cuts-no-question"
    ),
    pytest.param(
        f"Leiam Rute 1:1{_EN_DASH}5 (B1{_EN_DASH}B5).",
        "pt",
        f"Leiam Rute 1:1{_EN_DASH}5.",
        id="a-range-alone-in-parentheses",
    ),
    pytest.param(
        f"Leiam Rute 1:1{_EN_DASH}5 (cenas B1{_EN_DASH}B5).",
        "pt",
        f"Leiam Rute 1:1{_EN_DASH}5 (cenas).",
        id="a-range-beside-a-word-in-parentheses",
    ),
    pytest.param("B3, B4 e Noemi choram.", "pt", "Noemi choram.", id="a-mixed-list-that-opens"),
    pytest.param("Noemi, B3 e Rute", "pt", "Noemi e Rute", id="a-mixed-list-keeps-its-e"),
    pytest.param(
        "Rute fica (B3, B4 e Noemi).", "pt", "Rute fica (Noemi).", id="a-mixed-list-in-parentheses"
    ),
    pytest.param(
        "Vejam [[ B3 ]] agora.", "pt", "Vejam agora.", id="seam-b-a-code-spaced-in-brackets"
    ),
    pytest.param(
        "Vejam [[ B3 - Naomi ]] agora.",
        "pt",
        "Vejam agora.",
        id="seam-b-a-code-and-its-slug-spaced-in-brackets",
    ),
    pytest.param(
        "[[B3-Naomi]]: Noemi volta.",
        "pt",
        "Noemi volta.",
        id="seam-c-a-link-that-opens-the-sentence-takes-its-colon",
    ),
    pytest.param(
        "Ouçam [[B3-Naomi]]: Noemi volta.",
        "pt",
        "Ouçam: Noemi volta.",
        id="seam-c-a-colon-in-the-middle-of-a-sentence-stays",
    ),
    pytest.param(
        "Na cena [[B3-Naomi-returns]]: o que Noemi diz?",
        "pt",
        "Na cena. O que Noemi diz?",
        id="seam-c-a-colon-that-introduces-a-question-still-cuts",
    ),
    pytest.param("Naomi [[B3]]: where?", "en", "Naomi. Where?", id="seam-c-the-same-in-english"),
    pytest.param("S2: Rute fica.", "pt", "Rute fica.", id="seam-c-a-bare-code-that-opens-a-line"),
    pytest.param("- B3\n- Noemi volta.", "pt", "Noemi volta.", id="a-bullet-that-held-only-a-code"),
    pytest.param("## B3\nNoemi volta.", "pt", "Noemi volta.", id="a-heading-that-held-only-a-code"),
    pytest.param("B3 - Noemi chora?", "pt", "Noemi chora?", id="a-code-before-a-spaced-hyphen"),
    pytest.param(
        "Noemi volta. B3: Rute fica.",
        "pt",
        "Noemi volta. Rute fica.",
        id="a-code-after-a-full-stop",
    ),
    pytest.param(
        "Noemi volta. B3? Quem?", "pt", "Noemi volta. Quem?", id="a-code-before-a-question-mark"
    ),
    pytest.param(
        "- B3: Noemi volta\n- B4: Rute fica.",
        "pt",
        "Noemi volta. Rute fica.",
        id="a-list-of-scenes",
    ),
    pytest.param(
        "As cenas:\n- B3: Noemi volta\n- B4: Rute fica.",
        "pt",
        "As cenas: Noemi volta. Rute fica.",
        id="a-list-of-scenes-after-a-colon",
    ),
    pytest.param(
        "Pensem:\n- B3: o que Noemi sente?",
        "pt",
        "Pensem. O que Noemi sente?",
        id="a-question-listed-after-a-colon",
    ),
    pytest.param(
        '"[[B3-Naomi]]: Noemi volta."',
        "pt",
        '"Noemi volta."',
        id="a-link-that-opens-a-straight-quote",
    ),
    pytest.param(
        f"{_LEFT_QUOTE}B3: Noemi volta.{_RIGHT_QUOTE}",
        "pt",
        f"{_LEFT_QUOTE}Noemi volta.{_RIGHT_QUOTE}",
        id="a-code-that-opens-a-curly-quote",
    ),
    pytest.param("(B3: Noemi volta.)", "pt", "(Noemi volta.)", id="a-code-that-opens-a-bracket"),
    pytest.param(
        f"Ele disse: {_LEFT_QUOTE}B3: fique aqui.{_RIGHT_QUOTE}",
        "pt",
        f"Ele disse: {_LEFT_QUOTE}fique aqui.{_RIGHT_QUOTE}",
        id="a-code-that-opens-a-quote-after-a-colon",
    ),
    pytest.param(
        "Noemi — B3, a sogra — o que sentiu?",
        "pt",
        "Noemi — a sogra — o que sentiu?",
        id="a-code-after-the-opening-dash-of-a-pair",
    ),
    pytest.param(
        "Noemi — a sogra, B3 — o que sentiu?",
        "pt",
        "Noemi — a sogra — o que sentiu?",
        id="a-code-before-the-closing-dash-of-a-pair",
    ),
    pytest.param(
        "Noemi — a sogra — B3 - o que sentiu?",
        "pt",
        "Noemi — a sogra — o que sentiu?",
        id="a-code-and-its-hyphen-after-a-pair",
    ),
    pytest.param(
        "B3 Noemi falou. — Voltem, minhas filhas.",
        "pt",
        "Noemi falou. — Voltem, minhas filhas.",
        id="a-dialogue-dash-elsewhere-is-kept",
    ),
]


@pytest.mark.parametrize("text, language, expected", _SEAMS)
def test_the_seam_where_a_code_stood_is_mended(text: str, language: str, expected: str) -> None:
    assert speakable_text(text, language) == expected


@pytest.mark.parametrize("text, language, expected", _SEAMS)
def test_a_line_that_lost_its_codes_made_speakable_again_comes_back_equal(
    text: str, language: str, expected: str
) -> None:
    assert speakable_text(expected, language) == expected


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


def _named_by_its_slug(link: str) -> bool:
    return link.startswith(("[[FIG_", "[[CB_")) and "-" in link


def test_every_link_in_the_vendored_maps_is_removed_unless_its_slug_names_a_figure() -> None:
    links = [link for link in _links_in_the_vendored_maps() if not _named_by_its_slug(link)]

    offenders = [
        link for link in links if speakable_text(f"Antes {link} depois.", "pt") != "Antes depois."
    ]

    assert len(links) > 90
    assert offenders == []


def _the_slug_spoken(link: str) -> str:
    _, slug = link[2:-2].split("-", 1)
    return " ".join("Senhor Jeová" if word == "YHWH" else word for word in slug.split("-"))


def test_every_figure_link_in_the_vendored_maps_speaks_only_its_slug() -> None:
    links = [link for link in _links_in_the_vendored_maps() if _named_by_its_slug(link)]

    offenders = [
        link
        for link in links
        if speakable_text(f"Antes {link} depois.", "pt")
        != f"Antes {_the_slug_spoken(link)} depois."
    ]

    assert len(links) > 130
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
    assert len(_catalogue_labels()) > 450
    assert _labels_that_change("pt", "Senhor Jeová") == []


def test_no_catalogue_label_loses_a_word_in_english() -> None:
    assert _labels_that_change("en", "the LORD") == []


def test_no_catalogue_label_loses_a_word_in_spanish() -> None:
    assert _labels_that_change("es", "YHWH") == []


def test_a_line_with_no_code_is_spoken_as_written_but_for_whitespace_runs_and_edges() -> None:
    text = "Em Rute 1:6,  depois de dez anos, Noemi volta ; Senhor, LORD, 40 .  "

    assert (
        speakable_text(text, "pt")
        == "Em Rute 1:6, depois de dez anos, Noemi volta ; Senhor, LORD, 40 ."
    )


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


@pytest.mark.parametrize("heads", ["[[PL_ISRAEL]]", "[[B3-Naomi]]"])
def test_a_pin_whose_maps_carry_only_one_shape_of_code_fails_the_import(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, heads: str
) -> None:
    page = tmp_path / "map.md"
    page.write_text(f"{heads} um nome.", encoding="utf-8")
    monkeypatch.setattr(Path, "glob", lambda self, pattern: iter([page]))
    spec = importlib.util.spec_from_file_location("speakable_with_one_shape", speakable.__file__)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)

    with pytest.raises(RuntimeError):
        spec.loader.exec_module(module)


_RULED_SPLITS = [
    pytest.param(
        "Quando estiverem prontos, a pergunta segue de pé: o que vem à cabeça de vocês quando "
        'ouvem o nome "Rute"?',
        "Quando estiverem prontos, a pergunta segue de pé. O que vem à cabeça de vocês quando "
        'ouvem o nome "Rute"?',
        id="question-after-a-colon-quoted-name-inside",
    ),
    pytest.param(
        "Então, antes de tudo, eu quero que vocês conversem entre vocês: o que essa história "
        "inteira faz vocês sentirem?",
        "Então, antes de tudo, eu quero que vocês conversem entre vocês. O que essa história "
        "inteira faz vocês sentirem?",
        id="question-after-a-colon-commas-before-it-never-cut",
    ),
    pytest.param(
        "Noemi pergunta: onde você trabalhou?",
        "Noemi pergunta. Onde você trabalhou?",
        id="reported-speech-still-a-question-the-voice-must-intone",
    ),
    pytest.param(
        'Noemi pergunta: "onde você trabalhou hoje?"',
        'Noemi pergunta. "Onde você trabalhou hoje?"',
        id="reported-speech-in-quotes-capitalized-inside-the-quote",
    ),
    pytest.param(
        "Naomi asks: where did you work?", "Naomi asks. Where did you work?", id="english"
    ),
    pytest.param(
        'Naomi asks: "where did you work today?"',
        'Naomi asks. "Where did you work today?"',
        id="english-quoted",
    ),
    pytest.param(
        "Pensem nisso — o que Noemi sentiu?", "Pensem nisso. O que Noemi sentiu?", id="em-dash"
    ),
    pytest.param(
        "Pensem nisso - o que Noemi sentiu?",
        "Pensem nisso. O que Noemi sentiu?",
        id="spaced-hyphen",
    ),
    pytest.param(
        "A colheita acabou; e agora, o que Noemi faz?",
        "A colheita acabou. E agora, o que Noemi faz?",
        id="semicolon",
    ),
    pytest.param(
        "Primeira parte: a fome; segunda parte — a perda: o que vocês sentem?",
        "Primeira parte: a fome; segunda parte — a perda. O que vocês sentem?",
        id="several-separators-cut-at-the-last-one",
    ),
    pytest.param(
        'Ele disse "vá!": e agora?',
        'Ele disse "vá!" E agora?',
        id="head-that-already-ends-with-its-own-punctuation-gets-no-second-period",
    ),
    pytest.param(
        'Ele disse: "vá." — e você, o que faria?',
        'Ele disse: "vá." — e você, o que faria?',
        id="a-dash-led-question-after-a-closed-quote-is-already-its-own-sentence",
    ),
    pytest.param(
        "Rute volta para casa com muito grão. Noemi pergunta: onde você trabalhou? Rute diz o "
        "nome: Boaz.",
        "Rute volta para casa com muito grão. Noemi pergunta. Onde você trabalhou? Rute diz o "
        "nome: Boaz.",
        id="the-question-stays-a-question-in-the-middle-of-a-turn",
    ),
    pytest.param(
        "Placar 2:1 — quem ganhou?",
        "Placar 2:1. Quem ganhou?",
        id="a-colon-between-digits-is-a-time-not-a-separator-the-dash-after-it-still-cuts",
    ),
    pytest.param(
        "Noemi — a sogra — pergunta: onde você trabalhou?",
        "Noemi — a sogra — pergunta. Onde você trabalhou?",
        id="a-dash-pair-is-a-parenthetical-the-colon-after-it-still-cuts",
    ),
    pytest.param(
        "Rute 1\N{EN DASH}5 — o que acontece?",
        "Rute 1\N{EN DASH}5. O que acontece?",
        id="a-dash-range-between-digits-does-not-count-as-one-of-the-pair",
    ),
    pytest.param(
        "Vocês viram isso: ela ficou?!",
        "Vocês viram isso. Ela ficou?!",
        id="question-bang-is-still-a-question",
    ),
    pytest.param(
        "Vocês viram isso: ela ficou!?",
        "Vocês viram isso. Ela ficou!?",
        id="bang-question-is-still-a-question",
    ),
    pytest.param(
        "Naomi asks: “where\N{RIGHT SINGLE QUOTATION MARK}s Boaz: here or there?”",
        "Naomi asks. “Where\N{RIGHT SINGLE QUOTATION MARK}s Boaz: here or there?”",
        id="an-apostrophe-inside-a-curly-quote-does-not-close-it-the-colon-before-the-quote-cuts",
    ),
    pytest.param(
        "Naomi\N{RIGHT SINGLE QUOTATION MARK}s question: where did you work?",
        "Naomi\N{RIGHT SINGLE QUOTATION MARK}s question. Where did you work?",
        id="english-possessive-apostrophe-outside-any-span",
    ),
]


@pytest.mark.parametrize("text, expected", _RULED_SPLITS)
def test_a_question_folded_after_a_separator_stands_alone(text: str, expected: str) -> None:
    assert standalone_questions(text) == expected


_NOT_A_FOLDED_QUESTION = [
    pytest.param(
        'Uma coisa curiosa: o nome Belém quer dizer "casa do pão".', id="a-colon-in-a-statement"
    ),
    pytest.param(
        "Ficou claro pra vocês quem são as pessoas e o que acontece? Se tiver alguma coisa que "
        "vocês querem que eu conte de novo, me perguntem.",
        id="a-question-then-a-statement",
    ),
    pytest.param("Vocês querem que eu repita, ou está claro?", id="a-comma-never-cuts"),
    pytest.param(
        'O que vem à cabeça quando ouvem o nome "Rute"?', id="a-question-ending-in-a-quote"
    ),
    pytest.param('Ele perguntou "onde: aqui ou lá?"', id="a-colon-inside-double-quotes"),
    pytest.param("Vocês lembram (a fome: em Judá)?", id="a-colon-inside-parentheses"),
    pytest.param("Rute 1\N{EN DASH}5?", id="a-range-with-no-letter-after-it"),
    pytest.param("Vocês leram o guarda-chuva?", id="a-hyphen-inside-a-word"),
    pytest.param(
        "Essa parte ficou clara? se sim, eu continuo.", id="a-question-followed-by-lowercase"
    ),
    pytest.param("Ficou claro pra vocês?", id="a-plain-question"),
    pytest.param("", id="empty"),
    pytest.param("Vocês chegaram às 10:30 da manhã?", id="a-time"),
    pytest.param("Vocês chegaram às 10:30?", id="a-time-at-the-end"),
    pytest.param("Lembram de Rute 1:5, onde Noemi fica só?", id="a-verse-reference"),
    pytest.param("A sessão vai das 10:30 às 11:15, tudo bem?", id="two-times"),
    pytest.param("Rute 1 \N{EN DASH} 5, o que acontece?", id="a-spaced-en-dash-range"),
    pytest.param("Rute 1 - 5, o que acontece?", id="a-spaced-hyphen-range"),
    pytest.param("O que Noemi — a sogra — sentiu?", id="a-dash-pair"),
    pytest.param(
        "Como acaba exatamente — quem faz o quê, o que nasce disso — vocês conseguem imaginar?",
        id="a-dash-pair-inside-the-question",
    ),
    pytest.param(
        "A família — pai, mãe e dois filhos — o que aconteceu com ela?",
        id="a-dash-pair-before-the-question",
    ),
    pytest.param(
        "A família - pai, mãe e dois filhos - o que aconteceu com ela?",
        id="a-spaced-hyphen-pair-before-the-question",
    ),
    pytest.param("Pensem, — o que sentiram?", id="a-head-ending-with-a-comma"),
    pytest.param(
        "Ele perguntou \N{LEFT SINGLE QUOTATION MARK}onde: aqui ou "
        "lá?\N{RIGHT SINGLE QUOTATION MARK}",
        id="a-colon-inside-curly-single-quotes",
    ),
    pytest.param(
        'Ele disse: "fique no meu campo. Aqui: você está segura?"',
        id="a-quote-spanning-a-sentence-end",
    ),
    pytest.param(
        "Ele disse: “fique no meu campo. Aqui — você está segura?”",
        id="a-curly-quote-spanning-a-sentence-end",
    ),
    pytest.param("Ele perguntou (onde: aqui ou lá?)", id="a-question-inside-parentheses"),
]


@pytest.mark.parametrize("text", _NOT_A_FOLDED_QUESTION)
def test_a_line_with_no_question_folded_outside_quotes_and_parentheses_is_left_as_it_is(
    text: str,
) -> None:
    assert standalone_questions(text) == text


_KNOWN_LIMITS = [
    pytest.param(
        "Ele perguntou 'onde: aqui ou lá?'",
        "Ele perguntou 'onde. Aqui ou lá?'",
        id="a-straight-single-quote-is-not-a-span",
    ),
    pytest.param(
        "O que vocês acham: bom ou ruim?",
        "O que vocês acham. Bom ou ruim?",
        id="a-head-that-is-itself-the-question-is-closed-with-a-period",
    ),
    pytest.param(
        'Ele disse "vá. Noemi pergunta: onde você trabalhou?',
        'Ele disse "vá. Noemi pergunta: onde você trabalhou?',
        id="an-unbalanced-double-quote-suppresses-later-cuts",
    ),
]


@pytest.mark.parametrize("text, expected", _KNOWN_LIMITS)
def test_her_known_limits_of_the_question_split_stay_as_she_pinned_them(
    text: str, expected: str
) -> None:
    assert standalone_questions(text) == expected


_MARKED = [
    pytest.param(
        "Eles saem da cidade deles, **Belém de Judá**, e vão morar em *Moabe*.",
        "Eles saem da cidade deles, Belém de Judá, e vão morar em Moabe.",
        id="bold-and-italic-inside-a-sentence",
    ),
    pytest.param(
        "- o pai morre\n- os dois filhos casam",
        "O pai morre. Os dois filhos casam.",
        id="bullet-list-to-sentences",
    ),
    pytest.param(
        "- O pai morre!\n- os dois filhos casam?",
        "O pai morre! Os dois filhos casam?",
        id="bullet-list-keeps-an-items-own-punctuation",
    ),
    pytest.param(
        "* a fome\n1. a perda\n2) a volta",
        "A fome. A perda. A volta.",
        id="asterisk-and-numbered-bullets",
    ),
    pytest.param(
        '- "voltem para casa"\n- ela ficou',
        '"Voltem para casa". Ela ficou.',
        id="bullet-item-starting-with-a-quote",
    ),
    pytest.param(
        "## Segunda parte\nLá em Moabe, o pai morreu.",
        "Segunda parte. Lá em Moabe, o pai morreu.",
        id="heading-marks",
    ),
    pytest.param(
        "__Noemi__ volta para _Belém_.",
        "Noemi volta para Belém.",
        id="double-and-single-underscores",
    ),
    pytest.param(
        "o campo snake_case_name fica",
        "o campo snake_case_name fica",
        id="underscore-inside-a-word-stays",
    ),
    pytest.param(
        "a palavra `respigar` quer dizer catar",
        "a palavra respigar quer dizer catar",
        id="code-marks-keep-the-content",
    ),
    pytest.param(
        "veja [Rute 1](https://x.y/ruth#1) hoje", "veja Rute 1 hoje", id="link-to-its-text"
    ),
    pytest.param(
        "um * só e # aqui e C# fica",
        "um só e aqui e C# fica",
        id="stray-asterisks-and-hashes",
    ),
    pytest.param(
        "Primeira parte.\n\n\nSegunda   parte.",
        "Primeira parte. Segunda parte.",
        id="whitespace-runs-collapse-paragraphs-join-with-a-space",
    ),
    pytest.param(
        'Ele diz: "fique no meu campo. Aqui você está segura." — Boaz, à noite…',
        'Ele diz: "fique no meu campo. Aqui você está segura." — Boaz, à noite…',
        id="accents-quotes-and-punctuation-untouched",
    ),
    pytest.param(
        "Olá, equipe! Eu sou o Facilitador Digital.",
        "Olá, equipe! Eu sou o Facilitador Digital.",
        id="plain-text-is-the-identity",
    ),
    pytest.param(
        "Primeira parte.\n---\nSegunda parte.\n***\n___",
        "Primeira parte. Segunda parte.",
        id="horizontal-rule-dropped",
    ),
    pytest.param(
        "Olá equipe\nVamos começar",
        "Olá equipe Vamos começar",
        id="known-limit-a-plain-line-with-no-terminal-punctuation-gets-no-period",
    ),
]


@pytest.mark.parametrize("text, expected", _MARKED)
def test_formatting_marks_never_reach_the_voice_and_every_word_stays(
    text: str, expected: str
) -> None:
    assert strip_markdown(text) == expected


_THE_WHOLE_TRANSFORM = [
    pytest.param(
        "**YHWH** cuidou deles.",
        "pt",
        "Senhor Jeová cuidou deles.",
        id="bold-yhwh-is-senhor-jeova-once-the-marks-are-gone",
    ),
    pytest.param("*YHWH* saw it.", "en", "the LORD saw it.", id="italic-yhwh-is-the-lord"),
    pytest.param(
        "**Noemi pergunta:** onde você trabalhou?",
        "pt",
        "Noemi pergunta. Onde você trabalhou?",
        id="marks-off-then-the-question-split",
    ),
    pytest.param(
        "Lembram de **Rute 1:5**, às 10:30 — o que Noemi sentiu?",
        "pt",
        "Lembram de Rute 1:5, às 10:30. O que Noemi sentiu?",
        id="time-and-verse-reference-survive-the-whole-transform",
    ),
    pytest.param(
        "- Noemi pergunta: onde você trabalhou?\n- Rute responde: Boaz.",
        "pt",
        "Noemi pergunta. Onde você trabalhou? Rute responde: Boaz.",
        id="a-bullet-list-of-questions-each-its-own-sentence",
    ),
]


@pytest.mark.parametrize("text, language, expected", _THE_WHOLE_TRANSFORM)
def test_what_is_voiced_loses_its_marks_then_its_folded_questions_then_the_bare_name(
    text: str, language: str, expected: str
) -> None:
    assert speakable_text(text, language) == expected


_TURNO_2 = (
    "Sem pressa, gente. Parece que vocês ainda estão se acertando com o aparelho — tudo bem, "
    "isso é normal no começo. Só para lembrar: quem quiser falar comigo, toca no círculo, fala, "
    "e toca de novo quando terminar. Não precisa esperar nada além disso. Quando estiverem "
    "prontos, a pergunta segue de pé: o que vem à cabeça de vocês quando ouvem o nome "
    '"Rute"? Já ouviram essa história antes? Pode falar do jeito que for.'
)
_TURNO_8 = (
    "Muito bom. Quarta parte, devagar. Em Belém, Rute vai para o campo. Ela vai catar o que "
    'sobra da colheita. Isso se chama "respigar": pegar os grãos que ficam depois da '
    "colheita. Rute chega num campo. É o campo de um homem chamado Boaz. Boaz é parente da "
    "família de Noemi. Boaz vê Rute. Ele é bom com ela. Ele diz: fique no meu campo. Ele dá "
    "comida. Ele manda os trabalhadores cuidarem dela. Rute volta para casa com muito grão. "
    "Noemi pergunta: onde você trabalhou? Rute diz o nome: Boaz. E Noemi fica com esperança. "
    "Ela sabe que Boaz é parente. Um parente que pode ajudar a família. Vou parar aqui. "
    "Alguma dúvida nessa parte? Depois eu conto como a história continua."
)
_TURNO_10 = (
    "Ótimo. Agora a segunda metade. Boaz vê Rute no campo. Boaz é bom com ela. Ele diz: "
    '"fique no meu campo. Aqui você está segura." Ele dá comida para Rute. E ele manda os '
    "trabalhadores ajudarem Rute. No fim do dia, Rute volta para casa. Ela leva muito grão. "
    'Muito mais do que um dia normal. Noemi vê tudo aquilo. Ela pergunta: "onde você '
    'trabalhou hoje?" Rute responde com o nome: "Boaz." Noemi fica com esperança. Ela sabe '
    "que Boaz é parente. Um parente próximo pode ajudar a família dela. Vou parar aqui. "
    "Ficou claro? Se sim, eu conto o que vem depois."
)
_TURNO_12 = (
    "Que bom. Sexta parte, devagar. E é a última. De manhã, Boaz vai até o portão da cidade e "
    "se senta. Ali ele chama dez homens mais velhos da cidade para se sentarem com ele. Ele "
    "fala na frente de todos. Ele quer resolver o assunto da família de Noemi. E resolve. O "
    "povo abençoa Boaz e Rute. E a história termina em Belém. Lembram do começo? Noemi voltou "
    "dizendo que estava vazia. No fim, ela não está mais vazia. A casa que parecia acabada "
    "volta a ter futuro. Como acaba exatamente — quem faz o quê, o que nasce disso — o livro "
    "guarda para o final. E vamos chegar lá juntos, passagem por passagem. Agora, parece que "
    'vocês iam dizer algo: "é que como…". Podem terminar o pensamento?'
)
_TURNO_13 = (
    "Sim. Vocês já têm o mapa da viagem: a fome, a perda, o caminho de volta, o campo de Boaz, "
    "a noite, o portão, e a casa que fica cheia de novo. Agora é hora de entrar na história de "
    "verdade. O próximo passo é a primeira passagem: Rute 1, versículos 1 a 5 — a fome, a "
    "família em Moabe, e as perdas uma atrás da outra. Podem abrir a primeira passagem. Eu "
    "encontro vocês lá."
)

_REAL_GUIDE_TURNS = [
    pytest.param(
        _TURNO_2,
        _TURNO_2.replace("segue de pé: o que", "segue de pé. O que"),
        id="turno-2",
    ),
    pytest.param(
        _TURNO_8,
        _TURNO_8.replace("Noemi pergunta: onde", "Noemi pergunta. Onde"),
        id="turno-8",
    ),
    pytest.param(
        _TURNO_10,
        _TURNO_10.replace('Ela pergunta: "onde', 'Ela pergunta. "Onde'),
        id="turno-10",
    ),
    pytest.param(_TURNO_12, _TURNO_12, id="turno-12-no-folded-question"),
    pytest.param(_TURNO_13, _TURNO_13, id="turno-13"),
]


@pytest.mark.parametrize("text, expected", _REAL_GUIDE_TURNS)
def test_a_real_guide_turn_changes_only_at_the_ruled_split(text: str, expected: str) -> None:
    assert speakable_text(text, "pt") == expected


_CORPUS = [
    pytest.param(_TURNO_2, id="turno-2"),
    pytest.param(_TURNO_8, id="turno-8"),
    pytest.param(_TURNO_10, id="turno-10"),
    pytest.param(_TURNO_12, id="turno-12"),
    pytest.param(_TURNO_13, id="turno-13"),
    pytest.param(
        "Quando estiverem prontos, a pergunta segue de pé: o que vem à cabeça de vocês quando "
        'ouvem o nome "Rute"?',
        id="a-folded-question-with-a-quoted-name",
    ),
    pytest.param('Noemi pergunta: "onde você trabalhou hoje?"', id="a-folded-question-in-quotes"),
    pytest.param(
        "Eles saem da cidade deles, **Belém de Judá**, e vão morar em *Moabe*.",
        id="bold-and-italic",
    ),
    pytest.param("- o pai morre\n- os dois filhos casam", id="a-bullet-list"),
    pytest.param(
        "## Segunda parte\n* a fome\n1. a perda — o que vocês sentem?\n\n__Noemi__ volta para "
        "_Belém_ com `Rute`; e [Boaz](1) — onde está?",
        id="every-mark-at-once",
    ),
    pytest.param(
        "Primeira parte: a fome; segunda parte — a perda: o que vocês sentem?",
        id="several-separators",
    ),
    pytest.param("um * só e # aqui e C# fica snake_case_name", id="stray-marks-and-snake-case"),
    pytest.param(
        "Vocês chegaram às 10:30 da manhã? Lembram de Rute 1:5, onde Noemi fica só? Placar 2:1 — "
        "quem ganhou?",
        id="times-and-verse-references",
    ),
    pytest.param(
        "O que Noemi — a sogra — sentiu? Noemi — a sogra — pergunta: onde você trabalhou? Pensem, "
        "— o que sentiram?",
        id="dash-pairs-and-a-comma-head",
    ),
    pytest.param(
        "Naomi asks: “where\N{RIGHT SINGLE QUOTATION MARK}s Boaz: here or there?” "
        "Naomi\N{RIGHT SINGLE QUOTATION MARK}s question: where did you work? Ele "
        "perguntou \N{LEFT SINGLE QUOTATION MARK}onde: aqui ou lá?\N{RIGHT SINGLE QUOTATION MARK}",
        id="curly-quotes-and-apostrophes",
    ),
    pytest.param(
        'Ele disse: "fique no meu campo. Aqui: você está segura?" Vocês viram isso: ela ficou?!',
        id="a-quote-spanning-a-sentence-end",
    ),
    pytest.param(
        "Primeira parte.\n---\nSegunda parte: o que vocês sentem?", id="a-horizontal-rule"
    ),
]


def _words_in_order(text: str) -> list[str]:
    return re.findall(r"[^\W\d_]+", text.lower())


@pytest.mark.parametrize("text", _CORPUS)
def test_stripping_the_marks_twice_is_stripping_them_once(text: str) -> None:
    once = strip_markdown(text)

    assert strip_markdown(once) == once


@pytest.mark.parametrize("text", _CORPUS)
def test_standing_the_questions_alone_twice_is_doing_it_once(text: str) -> None:
    once = standalone_questions(strip_markdown(text))

    assert standalone_questions(once) == once


@pytest.mark.parametrize("text", _CORPUS)
def test_a_voiced_line_made_speakable_again_comes_back_equal(text: str) -> None:
    once = speakable_text(text, "pt")

    assert speakable_text(once, "pt") == once


@pytest.mark.parametrize("text", _CORPUS)
def test_stripping_the_marks_keeps_every_word(text: str) -> None:
    assert sorted(_words_in_order(strip_markdown(text))) == sorted(_words_in_order(text))


@pytest.mark.parametrize("text", _CORPUS)
def test_standing_the_questions_alone_keeps_every_word(text: str) -> None:
    unmarked = strip_markdown(text)

    assert sorted(_words_in_order(standalone_questions(unmarked))) == sorted(
        _words_in_order(unmarked)
    )


@pytest.mark.parametrize("text", _CORPUS)
def test_the_words_are_voiced_in_the_order_they_were_written(text: str) -> None:
    assert _words_in_order(speakable_text(text, "pt")) == _words_in_order(text)


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("Vejam **B3** agora.", id="inside-bold"),
        pytest.param("Vejam _B3_ agora.", id="inside-italic-the-marks-come-off-before-the-guard"),
    ],
)
def test_a_code_inside_formatting_marks_is_not_voiced(text: str) -> None:
    assert speakable_text(text, "pt") == "Vejam agora."


@pytest.mark.parametrize(
    "text, expected",
    [
        pytest.param(
            "[[B3-Naomi]]: Noemi pergunta: onde você trabalhou?",
            "Noemi pergunta. Onde você trabalhou?",
            id="the-colon-a-link-leaves-is-mended",
        ),
        pytest.param(
            "[[B3-Naomi]]: onde você trabalhou?",
            "onde você trabalhou?",
            id="the-guard-runs-before-the-question-split",
        ),
    ],
)
def test_the_seam_a_link_leaves_is_mended_before_the_question_split(
    text: str, expected: str
) -> None:
    assert speakable_text(text, "pt") == expected


def test_a_lone_all_caps_word_is_still_voiced() -> None:
    assert speakable_text("LORD, YHWH e MP3 ficam.", "pt") == "LORD, Senhor Jeová e MP3 ficam."


def test_the_divine_name_is_rewritten_after_the_question_split() -> None:
    assert (
        speakable_text("**YHWH** pergunta: onde você trabalhou?", "pt")
        == "Senhor Jeová pergunta. Onde você trabalhou?"
    )


def test_the_first_d_line_is_spoken_with_a_sentence_break_where_its_dash_was() -> None:
    assert (
        speakable_text("Desculpa, não consegui ouvir direito — podem repetir?", "pt")
        == "Desculpa, não consegui ouvir direito. Podem repetir?"
    )


_KNOWN_LIMITS_OF_THE_VOICED_TEXT = [
    pytest.param("Em 2*2 dias.", "pt", "Em 22 dias.", id="a-multiplication-asterisk-is-dropped"),
    pytest.param(
        "Noemi volta. B3: o que Rute diz?",
        "pt",
        "Noemi volta. o que Rute diz?",
        id="a-sentence-a-code-opened-starts-lowercase",
    ),
    pytest.param(
        "The YHWH-given land.",
        "en",
        "The the LORD-given land.",
        id="an-article-before-the-divine-name-is-doubled",
    ),
]


@pytest.mark.parametrize("text, language, expected", _KNOWN_LIMITS_OF_THE_VOICED_TEXT)
def test_the_known_limits_of_the_voiced_text_stay_as_pinned(
    text: str, language: str, expected: str
) -> None:
    assert speakable_text(text, language) == expected


def test_a_language_outside_the_table_loses_its_marks_and_its_folded_questions_but_not_yhwh() -> (
    None
):
    assert (
        speakable_text("**Noemí** pregunta: ¿dónde trabajaste hoy? YHWH lo sabe.", "es")
        == "Noemí pregunta. ¿dónde trabajaste hoy? YHWH lo sabe."
    )
