"""YHWH is never read letter by letter — it is voiced as the name Marcia's own prompts carry.

The bug this closes: the maps and the Guide write the tetragrammaton as the four consonants
"YHWH", and a voice engine spells letters it cannot pronounce. Nothing between a validated
line and the platform touched that shape until this module ran ahead of the TTS call.
"""

from __future__ import annotations

import pytest

from app.services.internalization_room.speakable import speakable_text, strip_markdown

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


_STRIP_MARKDOWN_CASES = [
    pytest.param(
        "Eles saem da cidade deles, **Belém de Judá**, e vão morar em *Moabe*.",
        "Eles saem da cidade deles, Belém de Judá, e vão morar em Moabe.",
        id="bold-and-italic-inside-a-sentence",
    ),
    pytest.param(
        "- o pai morre\n- os dois filhos casam",
        "O pai morre. Os dois filhos casam.",
        id="bullet-list-becomes-sentences",
    ),
    pytest.param(
        "- O pai morre!\n- os dois filhos casam?",
        "O pai morre! Os dois filhos casam?",
        id="bullet-list-keeps-its-own-punctuation",
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
        id="dunder-bold-and-underscore-italic",
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
        "veja [Rute 1](https://x.y/ruth#1) hoje",
        "veja Rute 1 hoje",
        id="link-becomes-its-text",
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
]


@pytest.mark.parametrize("text, expected", _STRIP_MARKDOWN_CASES)
def test_strip_markdown_removes_formatting_marks_but_keeps_every_word(
    text: str, expected: str
) -> None:
    assert strip_markdown(text) == expected


def test_strip_markdown_known_limit_a_soft_wrapped_line_gets_no_forced_period() -> None:
    """Pinned so a change is visible, not because it is the wanted answer (Marcia, 09/09).

    A plain line with no terminal punctuation of its own is not given one: a soft-wrapped
    sentence split across two lines of the same paragraph would otherwise get a false stop.
    """
    text = "Olá equipe\nVamos começar"

    assert strip_markdown(text) == "Olá equipe Vamos começar"
