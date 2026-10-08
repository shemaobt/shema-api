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


def test_a_figure_link_speaks_the_words_of_its_slug_and_never_its_code() -> None:
    text = "Pensem em [[FIG_0013-Bread-house-in-Famine]] agora."

    assert speakable_text(text, "pt") == "Pensem em Bread house in Famine agora."


def test_a_figure_link_with_no_slug_is_not_voiced() -> None:
    assert speakable_text("Pensem em [[FIG_0013]] agora.", "pt") == "Pensem em agora."


def test_a_link_followed_by_its_name_leaves_only_the_name() -> None:
    assert speakable_text("[[B3-Naomi]] Noemi ouve.", "pt") == "Noemi ouve."


def test_a_bare_figure_code_is_not_voiced() -> None:
    assert speakable_text("A figura FIG_0013 volta aqui.", "pt") == "A figura volta aqui."


def test_a_scene_code_typed_into_a_reply_is_not_voiced() -> None:
    assert speakable_text("Na cena S2, Rute fica.", "pt") == "Na cena, Rute fica."


def test_a_scene_link_is_not_voiced() -> None:
    assert speakable_text("Cena [[S1]] aqui.", "pt") == "Cena aqui."


def test_a_scene_code_in_map_prose_is_not_voiced() -> None:
    assert (
        speakable_text("Effect on scene: named outright only at v.22 in S3.", "en")
        == "Effect on scene: named outright only at v.22 in."
    )


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
    pytest.param(
        "Ele disse \N{LEFT-POINTING DOUBLE ANGLE QUOTATION MARK}B3"
        "\N{RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK} ontem.",
        "Ele disse ontem.",
        id="empty-guillemets",
    ),
    pytest.param(
        "Ele disse \N{LEFT SINGLE QUOTATION MARK}B3\N{RIGHT SINGLE QUOTATION MARK} ontem.",
        "Ele disse ontem.",
        id="empty-single-curly-quotes",
    ),
    pytest.param("Veja o resto, etc., B3.", "Veja o resto, etc.", id="no-double-full-stop"),
    pytest.param("Fim... B3 e mais.", "Fim... e mais.", id="an-ellipsis-is-kept"),
    pytest.param("Um texto: B3. Outro.", "Um texto. Outro.", id="colon-before-full-stop"),
    pytest.param("B3/B4 e B3-B4", "", id="slash-and-hyphen-joined-codes"),
    pytest.param("Naomi, B3 ,Ruth", "Naomi, Ruth", id="space-after-the-comma-kept"),
    pytest.param("Noemi\u00a0B3\u00a0chega.", "Noemi chega.", id="non-breaking-space"),
    pytest.param(
        "Linha um B3\nLinha dois.", "Linha um Linha dois.", id="a-code-at-the-end-of-a-line"
    ),
    pytest.param("B3 abre\n  recuo B4 fica.", "abre recuo fica.", id="a-code-on-each-of-two-lines"),
    pytest.param(
        "Linha um.\n  Recuo.\nTem B3.",
        "Linha um. Recuo. Tem.",
        id="a-code-on-the-last-of-three-lines",
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


def _named_by_its_slug(link: str) -> bool:
    return link.startswith(("[[FIG_", "[[CB_")) and "-" in link


def test_every_link_in_the_vendored_maps_is_removed_unless_its_slug_names_a_figure() -> None:
    links = [link for link in _links_in_the_vendored_maps() if not _named_by_its_slug(link)]

    offenders = [
        link for link in links if speakable_text(f"Antes {link} depois.", "pt") != "Antes depois."
    ]

    assert len(links) > 50
    assert offenders == []


def test_every_figure_link_in_the_vendored_maps_speaks_only_its_slug() -> None:
    links = [link for link in _links_in_the_vendored_maps() if _named_by_its_slug(link)]

    offenders = [
        link
        for link in links
        if speakable_text(f"Antes {link} depois.", "pt")
        != f"Antes {link[2:-2].split('-', 1)[1].replace('-', ' ')} depois.".replace(
            "YHWH", "Senhor Jeová"
        )
    ]

    assert len(links) > 50
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
    'Uma coisa curiosa: o nome Belém quer dizer "casa do pão".',
    "Ficou claro pra vocês quem são as pessoas e o que acontece? Se tiver alguma coisa que "
    "vocês querem que eu conte de novo, me perguntem.",
    "Vocês querem que eu repita, ou está claro?",
    'O que vem à cabeça quando ouvem o nome "Rute"?',
    'Ele perguntou "onde: aqui ou lá?"',
    "Vocês lembram (a fome: em Judá)?",
    "Rute 1\N{EN DASH}5?",
    "Vocês leram o guarda-chuva?",
    "Essa parte ficou clara? se sim, eu continuo.",
    "Ficou claro pra vocês?",
    "",
    "Vocês chegaram às 10:30 da manhã?",
    "Vocês chegaram às 10:30?",
    "Lembram de Rute 1:5, onde Noemi fica só?",
    "A sessão vai das 10:30 às 11:15, tudo bem?",
    "Rute 1 \N{EN DASH} 5, o que acontece?",
    "Rute 1 - 5, o que acontece?",
    "O que Noemi — a sogra — sentiu?",
    "Como acaba exatamente — quem faz o quê, o que nasce disso — vocês conseguem imaginar?",
    "A família — pai, mãe e dois filhos — o que aconteceu com ela?",
    "A família - pai, mãe e dois filhos - o que aconteceu com ela?",
    "Pensem, — o que sentiram?",
    "Ele perguntou \N{LEFT SINGLE QUOTATION MARK}onde: aqui ou lá?\N{RIGHT SINGLE QUOTATION MARK}",
    'Ele disse: "fique no meu campo. Aqui: você está segura?"',
    "Ele disse: “fique no meu campo. Aqui — você está segura?”",
    "Ele perguntou (onde: aqui ou lá?)",
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
    _TURNO_2,
    _TURNO_8,
    _TURNO_10,
    _TURNO_12,
    _TURNO_13,
    "Quando estiverem prontos, a pergunta segue de pé: o que vem à cabeça de vocês quando ouvem "
    'o nome "Rute"?',
    'Noemi pergunta: "onde você trabalhou hoje?"',
    "Eles saem da cidade deles, **Belém de Judá**, e vão morar em *Moabe*.",
    "- o pai morre\n- os dois filhos casam",
    "## Segunda parte\n* a fome\n1. a perda — o que vocês sentem?\n\n__Noemi__ volta para "
    "_Belém_ com `Rute`; e [Boaz](1) — onde está?",
    "Primeira parte: a fome; segunda parte — a perda: o que vocês sentem?",
    "um * só e # aqui e C# fica snake_case_name",
    "Vocês chegaram às 10:30 da manhã? Lembram de Rute 1:5, onde Noemi fica só? Placar 2:1 — "
    "quem ganhou?",
    "O que Noemi — a sogra — sentiu? Noemi — a sogra — pergunta: onde você trabalhou? Pensem, "
    "— o que sentiram?",
    "Naomi asks: “where\N{RIGHT SINGLE QUOTATION MARK}s Boaz: here or there?” "
    "Naomi\N{RIGHT SINGLE QUOTATION MARK}s question: where did you work? Ele "
    "perguntou \N{LEFT SINGLE QUOTATION MARK}onde: aqui ou lá?\N{RIGHT SINGLE QUOTATION MARK}",
    'Ele disse: "fique no meu campo. Aqui: você está segura?" Vocês viram isso: ela ficou?!',
    "Primeira parte.\n---\nSegunda parte: o que vocês sentem?",
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


def test_a_list_of_codes_goes_with_its_commas_and_its_e() -> None:
    assert speakable_text("As figuras B3, B4 e B5 choram.", "pt") == "As figuras choram."


def test_a_code_with_spaces_inside_its_brackets_leaves_nothing() -> None:
    assert speakable_text("Vejam [[ B3 ]] agora.", "pt") == "Vejam agora."


@pytest.mark.parametrize(
    "text, expected",
    [
        pytest.param("[[B3-Naomi]]: Noemi volta.", "Noemi volta.", id="at-the-start"),
        pytest.param("Ouçam [[B3-Naomi]]: Noemi volta.", "Ouçam Noemi volta.", id="in-the-middle"),
    ],
)
def test_a_link_followed_by_a_colon_and_its_name_leaves_only_the_name(
    text: str, expected: str
) -> None:
    assert speakable_text(text, "pt") == expected


def test_a_bare_code_that_opens_a_line_leaves_no_colon() -> None:
    assert speakable_text("S2: Rute fica.", "pt") == "Rute fica."


@pytest.mark.parametrize(
    "text, names",
    [
        pytest.param(
            "Pensem em THE_LAND_AFFLICTED_BY_FAMINE e em LAND_OF_BIRTH_UNNAMED agora.",
            ["THE_LAND_AFFLICTED_BY_FAMINE", "LAND_OF_BIRTH_UNNAMED"],
            id="two-places",
        ),
        pytest.param(
            "Vejam OBJECT_KIND e STATES_AS_TRUE.",
            ["OBJECT_KIND", "STATES_AS_TRUE"],
            id="two-fields",
        ),
    ],
)
def test_an_all_caps_name_joined_by_underscores_is_never_voiced(
    text: str, names: list[str]
) -> None:
    spoken = speakable_text(text, "pt")

    assert [name for name in names if name in spoken] == []
    assert "  " not in spoken


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
