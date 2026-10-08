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
from app.services.internalization_room.speakable import speakable_text, standalone_questions

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
    assert len(_catalogue_labels()) > 450
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
