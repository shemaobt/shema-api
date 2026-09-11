"""The Speaker addresses a team, and calls what they did traduzir (ENG-873).

Marcia's merged verdict prompt rules who the Speaker is talking to and in whose words: a
team and never one person, and *traduzir / tradução* for what they did — *contar* belongs to
the Conversation with the Guide alone (`CONTEXT.md`, **Telling back**). Her `check-doctrine`
header rules that the guard scans code and never the prompts, because the prompts are her
artifacts and she reviews them; the ENG-881 sweep follows that and reads Python literals
only. So this file is the whole guard over the two back-translation prompts, over the H and
I lines the room speaks in Portuguese and Spanish, and over the two prompt-key descriptions.

The English *told back* stays: it is the glossary's English term for the act, not the
retired Portuguese, and a sweep that took it would be a sweep of the wrong language.
"""

import re

import pytest

from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import _PROMPTS_DIR, default_prompt
from app.services.internalization_room.fail_safe import FailSafe

ANALYST = default_prompt(IRPromptKey.BT_ANALYST)["prompt"]
SPEAKER = default_prompt(IRPromptKey.BT_VERDICT_SPEAKER)["prompt"]

#: The address and the vocabulary the ticket retires, as patterns rather than words: `tua`
#: bare matches "ac**tua**lly" under *What to check*, and `você` bare matches the "vocês"
#: that replaces it, so each one is bounded and the two would pass a test that was not.
RETIRED = (
    r"\bvocê\b",
    r"\bteu\b",
    r"\btua\b",
    r"me conta\b",
    r"\bcontou\b",
    r"\bcontaram\b",
    r"explicação",
    r"told it back",
    r"\bfifteen\b",
    r"\btwenty\b",
    r"\bseconds\b",
)

#: Her section on the addressee, adopted verbatim. Pinned whole and not by its heading: the
#: sweep below cuts this section away, so a heading-only guard would let a sentence appended
#: under it say anything at all and be cut away with it.
WHO_YOU_ARE_TALKING_TO = "## Who you are talking to"
THE_RULE_ITSELF = """## Who you are talking to

A team, never one person: **"vocês", "de vocês", "traduziram", "traduzam", "gravem"** — never
"você", "teu", "tua", "me conta", "escuta". The recording is "a gravação de vocês"; what they did
is "a tradução de vocês" / "o que vocês me traduziram". The word is always **traduzir**: never
"contar de volta", never "contaram", never "explicaram" or "descreveram" for what they did."""
#: That section, from its heading to the next, cut out before the sweep below reads the
#: prompt. It is the one place the retired words belong, because naming them is how it
#: forbids them — *never "você", "teu", "tua", "me conta"* is the rule itself.
THE_RULE_THAT_NAMES_THEM = re.compile(
    rf"^{re.escape(WHO_YOU_ARE_TALKING_TO)}\n.*?(?=^## )", re.M | re.S
)
#: Her ruling of 2026-09-06 on the boundary question the Addition frame asks. What entered
#: is a *tradução*; *explicação* was the word for an act the team is no longer asked to do.
THE_ADDITION_QUESTION = "entrou agora na tradução?"
#: Her pronoun example under *How you speak*. Spoken-register placement is the point, and
#: the example has to be the verb the room actually uses.
THE_PRONOUN_EXAMPLE = '"me traduzam", never "traduzam-me"'
#: The sentence that replaces the July ceiling, removed on her word of 2026-09-04: a verdict
#: that names a whole relation does not fit in twenty seconds, and a voice told to fit drops
#: a path or trims the relation, which makes "isso a história não conta" untrue of what it
#: just said. One finding per turn carries the discipline instead.
NO_LENGTH_LIMIT = "No length limit: say what the moment needs, and stop."
#: The one law, in her words. Lower-cased on purpose: the Missing bullet opens a quoted
#: sentence with "No que vocês me traduziram", and a case-blind count would find that too
#: and pass while the law itself was gone.
THE_ONE_LAW = "no que vocês me traduziram"
#: Her analysis prompt's relation rule, where ours said "as the team told it back". The
#: Speaker quotes the note, so the note has to be in the words the Speaker may speak.
AS_THE_TEAM_TRANSLATED_IT = "as the team translated it"

#: Ours, not hers, and the reason nothing else of her verdict file comes across here: the
#: closing is the server's, filled per finding, and the Speaker is only given the slot.
CLOSING_SLOT = "{{CLOSING}}"
#: The glossary's English for the act. This ticket retires the Portuguese, not this.
THE_GLOSSARYS_ENGLISH = "told back"

#: The two families the Room speaks rather than ships: H when a stretch is still waiting,
#: I when the stretch pointed at will be replaced. Both are synthesized in the request that
#: needs them, so the new wording reaches a team with no app release in between. Keyed by
#: the enum that already names them, which is also how the sibling count table keys them.
SPOKEN_FAMILIES = {FailSafe.UNTOLD_STRETCH: 3, FailSafe.STRETCH_TO_CORRECT: 1}
#: The languages whose H and I lines this ticket rewrites. The Spanish supplement stays a
#: draft and reaches no mouth; it takes the swap so the draft does not have to be found
#: again on the day the room claims the language.
SPOKEN_LANGUAGES = ("pt", "es")
#: What a spoken line may no longer say, in either language. Case-blind and carrying `cuént`
#: because the Spanish imperative the ticket rewrote is *Cuéntenmelo*: it opens its sentence,
#: so a case-sensitive pattern misses it, and its accent breaks a literal `cuenten`. Measured
#: — a line that swapped only its first verb passed both assertions until this was fixed.
RETIRED_IN_A_SPOKEN_LINE = re.compile(
    r"contar|contem|contado|contarem|contaram|contarme|contaron|cuenten|cuént",
    re.IGNORECASE,
)
#: What it has to say instead, short enough to hold both languages: *traduzir* and
#: *traducir*, in every person the eight lines put them in. Asserted positively because the
#: sweep above only takes the old verb away, and a line that asked for neither would pass it.
THE_STEM = "tradu"

#: The parser reads a block from its heading to the next one and a line from its bullet
#: (`fail_safe.py`), so the block is what a test has to cut to: a sweep of the whole file
#: would pass on a line that had drifted into the family above it.
_HEADING = "^### {family}-{language}\\..*?(?=^##|\\Z)"
_BULLET = re.compile(r'^- "(.+)"$', re.M)


def _one_line(text: str) -> str:
    """The text with its wrapping folded away, so a sentence is one sentence to search for."""
    return re.sub(r"\s+", " ", text)


def _block(text: str, family: FailSafe, language: str) -> str:
    found = re.search(_HEADING.format(family=family, language=language), text, re.M | re.S)
    assert found, f"o bloco {family}-{language} não está no suplemento"
    return found.group(0)


def _the_cut_region(prompt: str) -> str:
    found = THE_RULE_THAT_NAMES_THEM.search(prompt)
    return found.group(0).strip() if found else ""


def _supplement(language: str) -> str:
    return (_PROMPTS_DIR / f"_fail_safe_{language}_supplement.md").read_text(encoding="utf-8")


def test_the_two_prompts_speak_to_a_team_and_never_of_contar() -> None:
    """Neither prompt addresses one person, names the act *contar*, nor times the voice.

    Both are asserted in one place because the Speaker quotes the Analyst: a note written
    about what the team *told back* is spoken as what they *traduziram*, and the two words
    cannot both be the room's.

    *Who you are talking to* is cut out of the verdict first. Her rule forbids the retired
    address by quoting it — *never "você", "teu", "tua", "me conta", "escuta"* — so the words
    have to stand there, and a sweep of the whole file could never pass while the section it
    also requires was present. The cut is not a hiding place: the test below requires that
    what is cut be her section verbatim, so a sentence appended under its heading to escape
    this sweep is a sentence that turns that test red.

    The analyst is swept whole, and the heading is asserted absent from it. Only the
    verdict's cut region is pinned, so cutting by heading wherever one appeared would make
    the analyst prompt the hiding place instead: a section pasted there under that heading
    would be carried off before this sweep ever read it, and nothing would pin what it said.

    Every match is gathered before the assertion rather than asserted where it is found. An
    assertion inside the loop stops at the verdict's first match and reports it as the whole
    truth, so the analyst's own word would never be seen to fail and its guard would have
    been taken on faith.
    """
    swept = (("verdict", THE_RULE_THAT_NAMES_THEM.sub("", SPEAKER)), ("analyst", ANALYST))
    still_said = [
        (name, retired)
        for name, prompt in swept
        for retired in RETIRED
        if re.search(retired, _one_line(prompt))
    ]

    assert WHO_YOU_ARE_TALKING_TO not in ANALYST, (
        "o prompt do analista carrega a seção que a varredura recorta, e só a do veredito é fixada"
    )
    assert still_said == [], f"os prompts ainda dizem o que este ticket aposentou: {still_said}"


def test_the_verdict_carries_marcias_frame() -> None:
    """The six passages of hers this ticket adopts, each exactly once.

    Once and not merely present: a paragraph pasted twice is a prompt that says the rule
    and then says it again in the older words, and the model reads both. Counted together
    for the same reason the sweep above is: five assertions in a row report only the first
    passage that never arrived.

    *Who you are talking to* is pinned by what the sweep cuts away rather than by a count,
    and the difference was measured, not assumed: a count says the section is there, so a
    sentence appended under it left both this test and the sweep green while the prompt told
    the Speaker to say *no que você me contou*. What is cut has to be her section and nothing
    else.
    """
    adopted = {
        THE_ONE_LAW: _one_line(SPEAKER),
        THE_ADDITION_QUESTION: _one_line(SPEAKER),
        THE_PRONOUN_EXAMPLE: _one_line(SPEAKER),
        NO_LENGTH_LIMIT: _one_line(SPEAKER),
        AS_THE_TEAM_TRANSLATED_IT: _one_line(ANALYST),
    }
    counted = {passage: prompt.count(passage) for passage, prompt in adopted.items()}

    assert _the_cut_region(SPEAKER) == THE_RULE_ITSELF, (
        "o que a varredura recorta não é a seção dela, palavra por palavra"
    )

    assert counted == dict.fromkeys(adopted, 1), (
        f"as passagens dela não estão nos prompts exatamente uma vez: {counted}"
    )


def test_the_closing_slot_and_the_english_term_stay() -> None:
    """What the adoption may not carry away with the retired words.

    Her file has no `{{CLOSING}}`: the closings are ours, and a paste of her sections that
    took the slot with it would leave the Speaker to invent the end of every turn.
    """
    assert SPEAKER.count(CLOSING_SLOT) == 1, "o veredito perdeu a vaga do fechamento"
    assert THE_GLOSSARYS_ENGLISH in SPEAKER, (
        "o termo inglês do glossário saiu junto com o português aposentado"
    )


@pytest.mark.parametrize("family", SPOKEN_FAMILIES)
@pytest.mark.parametrize("language", SPOKEN_LANGUAGES)
def test_the_h_and_i_lines_say_traduzir_in_portuguese_and_spanish(
    language: str, family: FailSafe
) -> None:
    """The lines the room speaks say *traduzir* too, and there are still as many of them.

    One case per family and language, so each block is seen to fail on its own: a single
    case over both families stops at H and leaves I's guard unwatched.

    Said and not merely not-said: the absence of *contar* is half the ruling, and a line
    rewritten around neither verb would satisfy it while asking the team for something the
    room no longer has a word for. Each line has to carry the stem itself.

    The count is asserted beside the words because a swap done line by line is exactly the
    edit that drops one: the H family says the same thing three ways so a second failure in
    a row is not the same sentence, and `test_ir_the_room_asks_for_the_whole_stretch`'s
    table of families would go red one slice later, far from here.
    """
    block = _block(_supplement(language), family, language)
    spoken = _BULLET.findall(block)
    retired = RETIRED_IN_A_SPOKEN_LINE.findall(block)
    silent = [line for line in spoken if THE_STEM not in line.lower()]

    assert retired == [], f"a fala {family}-{language} ainda diz {retired} do que a equipe fez"
    assert silent == [], f"a fala {family}-{language} não pede tradução em: {silent}"
    assert len(spoken) == SPOKEN_FAMILIES[family], (
        f"a família {family} em {language} não tem mais "
        f"{SPOKEN_FAMILIES[family]} fala(s) escrita(s)"
    )


@pytest.mark.parametrize("key", list(IRPromptKey))
def test_no_prompt_key_description_says_retrotraducao(key: IRPromptKey) -> None:
    """The word the room retired does not survive in what names the prompt to a reader."""
    assert "retrotradução" not in default_prompt(key)["description"], (
        f"a descrição de {key} ainda chama a tradução de retrotradução"
    )
