"""YHWH is never read letter by letter — it is voiced as the name Marcia's own prompts carry.

The bug this closes: the maps and the Guide write the tetragrammaton as the four consonants
"YHWH", and a voice engine spells letters it cannot pronounce. Nothing between a validated
line and the platform touched that shape until this module ran ahead of the TTS call.
"""

from __future__ import annotations

import pytest
import regex

import scripts.render_fixed_voice_lines as render
from app.services.internalization_room.canon.parse_map import load_book
from app.services.internalization_room.languages import ROOM_LANGUAGES
from app.services.internalization_room.passage_lines import line_for, panorama_line_for
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
        "Quando estiverem prontos, a pergunta segue de pé: o que vem à cabeça de vocês "
        'quando ouvem o nome "Rute"?',
        "Quando estiverem prontos, a pergunta segue de pé. O que vem à cabeça de vocês "
        'quando ouvem o nome "Rute"?',
        id="question-after-a-colon-quoted-name-inside",
    ),
    pytest.param(
        "Então, antes de tudo, eu quero que vocês conversem entre vocês: o que essa "
        "história inteira faz vocês sentirem?",
        "Então, antes de tudo, eu quero que vocês conversem entre vocês. O que essa "
        "história inteira faz vocês sentirem?",
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
        "Rute volta para casa com muito grão. Noemi pergunta: onde você trabalhou? "
        "Rute diz o nome: Boaz.",
        "Rute volta para casa com muito grão. Noemi pergunta. Onde você trabalhou? "
        "Rute diz o nome: Boaz.",
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
    # review 2026-09-09: never inside a span — curly single quotes, a span crossing a sentence end
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


_SPEAKABLE_TEXT_COMPOSITION = [
    pytest.param(
        "**YHWH** cuidou deles.",
        "pt",
        "Senhor Jeová cuidou deles.",
        id="yhwh-becomes-senhor-jeova-pt-the-divine-name-step-runs-after-the-marks-are-gone",
    ),
    pytest.param(
        "*YHWH* saw it.",
        "en",
        "the LORD saw it.",
        id="yhwh-becomes-the-lord-en",
    ),
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


@pytest.mark.parametrize("text, language, expected", _SPEAKABLE_TEXT_COMPOSITION)
def test_speakable_text_composes_marks_off_then_the_question_split_then_yhwh(
    text: str, language: str, expected: str
) -> None:
    assert speakable_text(text, language) == expected


_TURNO_2 = (
    "Sem pressa, gente. Parece que vocês ainda estão se acertando com o aparelho — tudo bem, "
    "isso é normal no começo. Só para lembrar: quem quiser falar comigo, toca no círculo, "
    "fala, e toca de novo quando terminar. Não precisa esperar nada além disso. Quando "
    "estiverem prontos, a pergunta segue de pé: o que vem à cabeça de vocês quando ouvem o "
    'nome "Rute"? Já ouviram essa história antes? Pode falar do jeito que for.'
)
_TURNO_8 = (
    "Muito bom. Quarta parte, devagar. Em Belém, Rute vai para o campo. Ela vai catar o que "
    'sobra da colheita. Isso se chama "respigar": pegar os grãos que ficam depois da colheita. '
    "Rute chega num campo. É o campo de um homem chamado Boaz. Boaz é parente da família de "
    "Noemi. Boaz vê Rute. Ele é bom com ela. Ele diz: fique no meu campo. Ele dá comida. Ele "
    "manda os trabalhadores cuidarem dela. Rute volta para casa com muito grão. Noemi "
    "pergunta: onde você trabalhou? Rute diz o nome: Boaz. E Noemi fica com esperança. Ela "
    "sabe que Boaz é parente. Um parente que pode ajudar a família. Vou parar aqui. Alguma "
    "dúvida nessa parte? Depois eu conto como a história continua."
)
_TURNO_10 = (
    "Ótimo. Agora a segunda metade. Boaz vê Rute no campo. Boaz é bom com ela. Ele diz: "
    '"fique no meu campo. Aqui você está segura." Ele dá comida para Rute. E ele manda os '
    "trabalhadores ajudarem Rute. No fim do dia, Rute volta para casa. Ela leva muito grão. "
    'Muito mais do que um dia normal. Noemi vê tudo aquilo. Ela pergunta: "onde você '
    'trabalhou hoje?" Rute responde com o nome: "Boaz." Noemi fica com esperança. Ela sabe '
    "que Boaz é parente. Um parente próximo pode ajudar a família dela. Vou parar aqui. Ficou "
    "claro? Se sim, eu conto o que vem depois."
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
    "Sim. Vocês já têm o mapa da viagem: a fome, a perda, o caminho de volta, o campo de "
    "Boaz, a noite, o portão, e a casa que fica cheia de novo. Agora é hora de entrar na "
    "história de verdade. O próximo passo é a primeira passagem: Rute 1, versículos 1 a 5 — "
    "a fome, a família em Moabe, e as perdas uma atrás da outra. Podem abrir a primeira "
    "passagem. Eu encontro vocês lá."
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
    pytest.param(_TURNO_12, _TURNO_12, id="turno-12-unchanged-no-folded-question"),
    pytest.param(_TURNO_13, _TURNO_13, id="turno-13-unchanged"),
]


@pytest.mark.parametrize("text, expected", _REAL_GUIDE_TURNS)
def test_speakable_text_on_real_guide_turns_from_the_2026_09_09_dossier(
    text: str, expected: str
) -> None:
    """Real Guide turns from the OV-Ruth dossier, session ffa462f2, 2026-09-09.

    Each must come out unchanged except for the ruled splits — the same bar her own test
    suite holds these turns to.
    """
    assert speakable_text(text, "pt") == expected


_SPEAKABLE_TEXT_SPANISH = [
    pytest.param(
        "- Rut preguntó: dónde trabajaste?",
        "Rut preguntó. Dónde trabajaste?",
        id="marks-and-the-question-split-apply-to-a-language-outside-the-yhwh-table",
    ),
    pytest.param(
        "**YHWH** llamó a Rut: trabajaste hoy?",
        "YHWH llamó a Rut. Trabajaste hoy?",
        id="yhwh-stays-literal-in-spanish-while-marks-and-the-question-split-still-run",
    ),
]


@pytest.mark.parametrize("text, expected", _SPEAKABLE_TEXT_SPANISH)
def test_speakable_text_marks_and_questions_run_in_spanish_even_though_yhwh_does_not(
    text: str, expected: str
) -> None:
    assert speakable_text(text, "es") == expected


def _words(text: str) -> str:
    return " ".join(sorted(match.group(0).lower() for match in regex.finditer(r"\p{L}+", text)))


def _word_order(text: str) -> str:
    return " ".join(match.group(0).lower() for match in regex.finditer(r"\p{L}+", text))


_INVARIANTS_CORPUS = [
    pytest.param(_TURNO_2, id="turno-2"),
    pytest.param(_TURNO_8, id="turno-8"),
    pytest.param(_TURNO_10, id="turno-10"),
    pytest.param(_TURNO_12, id="turno-12"),
    pytest.param(_TURNO_13, id="turno-13"),
    pytest.param(
        "Quando estiverem prontos, a pergunta segue de pé: o que vem à cabeça de vocês "
        'quando ouvem o nome "Rute"?',
        id="folded-question-with-a-quoted-name",
    ),
    pytest.param(
        'Noemi pergunta: "onde você trabalhou hoje?"',
        id="reported-speech-in-quotes",
    ),
    pytest.param(
        "Eles saem da cidade deles, **Belém de Judá**, e vão morar em *Moabe*.",
        id="bold-and-italic",
    ),
    pytest.param("- o pai morre\n- os dois filhos casam", id="bullet-list"),
    pytest.param(
        "## Segunda parte\n* a fome\n1. a perda — o que vocês sentem?\n\n"
        "__Noemi__ volta para _Belém_ com `Rute`; e [Boaz](1) — onde está?",
        id="heading-bullet-code-link-and-a-folded-question-together",
    ),
    pytest.param(
        "Primeira parte: a fome; segunda parte — a perda: o que vocês sentem?",
        id="several-separators",
    ),
    pytest.param("um * só e # aqui e C# fica snake_case_name", id="stray-marks-and-c-sharp"),
    pytest.param(
        "Vocês chegaram às 10:30 da manhã? Lembram de Rute 1:5, onde Noemi fica só? "
        "Placar 2:1 — quem ganhou?",
        id="times-and-verse-references",
    ),
    pytest.param(
        "O que Noemi — a sogra — sentiu? Noemi — a sogra — pergunta: onde você trabalhou? "
        "Pensem, — o que sentiram?",
        id="dash-pairs-and-a-comma-headed-dash",
    ),
    pytest.param(
        "Naomi asks: “where’s Boaz: here or there?” Naomi’s question: where did you work? "
        "Ele perguntou ‘onde: aqui ou lá?’",
        id="curly-quotes-apostrophes-and-a-straight-single-quote",
    ),
    pytest.param(
        'Ele disse: "fique no meu campo. Aqui: você está segura?" Vocês viram isso: ela ficou?!',
        id="a-span-crossing-a-sentence-end-and-a-question-mark-exclamation",
    ),
    pytest.param(
        "Primeira parte.\n---\nSegunda parte: o que vocês sentem?",
        id="horizontal-rule-and-a-folded-question",
    ),
]


@pytest.mark.parametrize("text", _INVARIANTS_CORPUS)
def test_the_transform_is_idempotent_and_never_drops_gains_or_reorders_a_word(
    text: str,
) -> None:
    """Over every case above: applying a step twice is applying it once, and a word survives.

    Neither step ever drops, reorders or invents a word — only formatting marks go and a
    sentence boundary can move. speakable_text runs "pt" throughout because idempotence and
    word-preservation are properties of the transform, not of the divine-name table.
    """
    marks_off = strip_markdown(text)
    questions_split = standalone_questions(marks_off)
    voiced = speakable_text(text, "pt")

    assert strip_markdown(marks_off) == marks_off, "strip_markdown is not idempotent"
    assert standalone_questions(questions_split) == questions_split, (
        "standalone_questions is not idempotent"
    )
    assert speakable_text(voiced, "pt") == voiced, "speakable_text is not idempotent"
    assert _words(marks_off) == _words(text), "strip_markdown dropped or invented a word"
    assert _words(questions_split) == _words(marks_off), (
        "standalone_questions dropped or invented a word"
    )
    assert _word_order(voiced) == _word_order(text), "word order was not preserved end to end"


# The D family (couldn't hear / transcription failed) folds a real question after an em
# dash, in both languages — the one place a fixed line is not a no-op under the new steps.
# Its shipped clip was recorded reading the flat statement; ENG-1091 tracks the re-render
# and teaching scripts/render_fixed_voice_lines.py's fingerprint to hash the spoken form
# instead of the raw one, so `--check` can see this drift on its own next time.
_FIXED_LINE_QUESTION_SPLITS = {
    (
        "en",
        "Sorry, I didn't quite catch that — could you say it again?",
    ): "Sorry, I didn't quite catch that. Could you say it again?",
    (
        "en",
        "The sound didn't come through — would you say that again?",
    ): "The sound didn't come through. Would you say that again?",
    (
        "pt",
        "Desculpa, não consegui ouvir direito — podem repetir?",
    ): "Desculpa, não consegui ouvir direito. Podem repetir?",
    (
        "pt",
        "O som não chegou bem — podem falar mais uma vez?",
    ): "O som não chegou bem. Podem falar mais uma vez?",
}


def _fixed_voice_line_cases() -> list[object]:
    """Every pre-approved fixed line the app can ship, by the name it plays it under.

    ``scripts/render_fixed_voice_lines.py`` fingerprints this text before
    ``render_facilitator_speech`` ever calls ``speakable_text`` on it (fingerprint at
    ``:172``, taken from the raw ``catalogue()`` text at ``:210``), so a voicing-only change
    to one of these lines would never show up as manifest drift. Almost every line here is a
    no-op under the new steps apart from YHWH, which is what keeps that blind spot safe — the
    D family (``_FIXED_LINE_QUESTION_SPLITS`` above) is the real exception, not a fixture bug.
    """
    cases: list[object] = []
    for language in ROOM_LANGUAGES:
        for name, text in render.catalogue(language).items():
            expected = _FIXED_LINE_QUESTION_SPLITS.get((language, text), text)
            cases.append(pytest.param(text, language, expected, id=f"catalogue-{language}-{name}"))
        for name, text in render.STANDALONE.get(language, {}).items():
            cases.append(pytest.param(text, language, text, id=f"standalone-{language}-{name}"))
        for meaning_map in load_book("Ruth"):
            text = line_for(meaning_map.pericope_num, language)
            if text:
                cases.append(
                    pytest.param(
                        text,
                        language,
                        text,
                        id=f"passage-line-{language}-{meaning_map.pericope_num}",
                    )
                )
        panorama = panorama_line_for(language)
        if panorama:
            cases.append(pytest.param(panorama, language, panorama, id=f"panorama-{language}"))
    return cases


@pytest.mark.parametrize("text, language, expected", _fixed_voice_line_cases())
def test_fixed_voice_lines_pass_through_speakable_text_unchanged_apart_from_yhwh(
    text: str, language: str, expected: str
) -> None:
    assert "YHWH" not in text, "a fixed line naming YHWH would need its own case, not this one"
    assert speakable_text(text, language) == expected
