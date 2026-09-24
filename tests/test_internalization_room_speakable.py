"""YHWH is never read letter by letter — it is voiced as the name Marcia's own prompts carry.

The bug this closes: the maps and the Guide write the tetragrammaton as the four consonants
"YHWH", and a voice engine spells letters it cannot pronounce. Nothing between a validated
line and the platform touched that shape until this module ran ahead of the TTS call.
"""

from __future__ import annotations

import pytest

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


_STANDALONE_QUESTIONS_RULED_SPLITS = [
    pytest.param(
        'Quando estiverem prontos, a pergunta segue de pé: o que vem à cabeça de vocês quando ouvem o nome "Rute"?',
        'Quando estiverem prontos, a pergunta segue de pé. O que vem à cabeça de vocês quando ouvem o nome "Rute"?',
        id="question-after-a-colon-quoted-name-inside",
    ),
    pytest.param(
        "Então, antes de tudo, eu quero que vocês conversem entre vocês: o que essa história inteira faz vocês sentirem?",
        "Então, antes de tudo, eu quero que vocês conversem entre vocês. O que essa história inteira faz vocês sentirem?",
        id="commas-before-it-never-cut",
    ),
    pytest.param(
        "Noemi pergunta: onde você trabalhou?",
        "Noemi pergunta. Onde você trabalhou?",
        id="reported-speech",
    ),
    pytest.param(
        'Noemi pergunta: "onde você trabalhou hoje?"',
        'Noemi pergunta. "Onde você trabalhou hoje?"',
        id="reported-speech-in-quotes",
    ),
    pytest.param(
        "Naomi asks: where did you work?",
        "Naomi asks. Where did you work?",
        id="english",
    ),
    pytest.param(
        'Naomi asks: "where did you work today?"',
        'Naomi asks. "Where did you work today?"',
        id="english-quoted",
    ),
    pytest.param(
        "Pensem nisso — o que Noemi sentiu?",
        "Pensem nisso. O que Noemi sentiu?",
        id="em-dash",
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
        "Rute volta para casa com muito grão. Noemi pergunta: onde você trabalhou? Rute diz o nome: Boaz.",
        "Rute volta para casa com muito grão. Noemi pergunta. Onde você trabalhou? Rute diz o nome: Boaz.",
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
        "Rute 1–5 — o que acontece?",
        "Rute 1–5. O que acontece?",
        id="a-dash-range-between-digits-does-not-count-as-one-of-the-pair",
    ),
    pytest.param(
        "Vocês viram isso: ela ficou?!",
        "Vocês viram isso. Ela ficou?!",
        id="question-mark-exclamation-is-still-a-question",
    ),
    pytest.param(
        "Vocês viram isso: ela ficou!?",
        "Vocês viram isso. Ela ficou!?",
        id="exclamation-question-mark-is-still-a-question",
    ),
    pytest.param(
        "Naomi asks: “where’s Boaz: here or there?”",
        "Naomi asks. “Where’s Boaz: here or there?”",
        id="an-apostrophe-inside-a-curly-quote-does-not-close-it-the-colon-before-the-quote-cuts",
    ),
    pytest.param(
        "Naomi’s question: where did you work?",
        "Naomi’s question. Where did you work?",
        id="english-possessive-apostrophe-outside-any-span",
    ),
]


@pytest.mark.parametrize("text, expected", _STANDALONE_QUESTIONS_RULED_SPLITS)
def test_standalone_questions_splits_the_ruled_cases(text: str, expected: str) -> None:
    assert standalone_questions(text) == expected


_STANDALONE_QUESTIONS_UNTOUCHED = [
    'Uma coisa curiosa: o nome Belém quer dizer "casa do pão".',
    "Ficou claro pra vocês quem são as pessoas e o que acontece? "
    "Se tiver alguma coisa que vocês querem que eu conte de novo, me perguntem.",
    "Vocês querem que eu repita, ou está claro?",
    'O que vem à cabeça quando ouvem o nome "Rute"?',
    'Ele perguntou "onde: aqui ou lá?"',
    "Vocês lembram (a fome: em Judá)?",
    "Rute 1–5?",
    "Vocês leram o guarda-chuva?",
    "Essa parte ficou clara? se sim, eu continuo.",
    "Ficou claro pra vocês?",
    "",
    # review 2026-09-09: a separator between digits is a time / verse reference / range
    "Vocês chegaram às 10:30 da manhã?",
    "Vocês chegaram às 10:30?",
    "Lembram de Rute 1:5, onde Noemi fica só?",
    "A sessão vai das 10:30 às 11:15, tudo bem?",
    "Rute 1 – 5, o que acontece?",
    "Rute 1 - 5, o que acontece?",
    # review 2026-09-09: a dash pair is a parenthetical, never a cut
    "O que Noemi — a sogra — sentiu?",
    "Como acaba exatamente — quem faz o quê, o que nasce disso — vocês conseguem imaginar?",
    "A família — pai, mãe e dois filhos — o que aconteceu com ela?",
    "A família - pai, mãe e dois filhos - o que aconteceu com ela?",
    # review 2026-09-09: a head that ends with a comma would give ",." — left alone
    "Pensem, — o que sentiram?",
    # review 2026-09-09: never inside a quoted span — curly single quotes, and a span crossing a sentence end
    "Ele perguntou ‘onde: aqui ou lá?’",
    'Ele disse: "fique no meu campo. Aqui: você está segura?"',
    "Ele disse: “fique no meu campo. Aqui — você está segura?”",
    "Ele perguntou (onde: aqui ou lá?)",
]


@pytest.mark.parametrize(
    "text",
    _STANDALONE_QUESTIONS_UNTOUCHED,
    ids=[f"unchanged-{i}" for i in range(len(_STANDALONE_QUESTIONS_UNTOUCHED))],
)
def test_standalone_questions_leaves_the_rest_untouched(text: str) -> None:
    assert standalone_questions(text) == text


_STANDALONE_QUESTIONS_KNOWN_LIMITS = [
    pytest.param(
        "Ele perguntou 'onde: aqui ou lá?'",
        "Ele perguntou 'onde. Aqui ou lá?'",
        id="a-straight-single-quote-is-not-a-span-it-is-also-the-apostrophe",
    ),
    pytest.param(
        "O que vocês acham: bom ou ruim?",
        "O que vocês acham. Bom ou ruim?",
        id="a-head-that-is-itself-the-question-is-closed-with-a-period",
    ),
    pytest.param(
        'Ele disse "vá. Noemi pergunta: onde você trabalhou?',
        'Ele disse "vá. Noemi pergunta: onde você trabalhou?',
        id="an-unbalanced-double-quote-suppresses-later-cuts-the-safe-direction",
    ),
]


@pytest.mark.parametrize("text, expected", _STANDALONE_QUESTIONS_KNOWN_LIMITS)
def test_standalone_questions_known_limits_stay_pinned(text: str, expected: str) -> None:
    """Pinned so a change is visible, not because it is the wanted answer (Marcia, 09/09).

    Changing any of these is her call, not this port's — see the docstring above
    ``standalone_questions`` for what each one means and why it is left as it is.
    """
    assert standalone_questions(text) == expected
