"""The Speaker addresses a team, and calls what they did traduzir (ENG-873).

Marcia's merged verdict prompt rules who the Speaker is talking to and in whose words: a
team and never one person, and *traduzir / tradução* for what they did — *contar* belongs to
the Conversation with the Guide alone (`CONTEXT.md`, **Telling back**). Her `check-doctrine`
header rules that the guard scans code and never the prompts, because the prompts are her
artifacts and she reviews them; the ENG-881 sweep follows that and reads Python literals
only. So this file is the whole guard over the two back-translation prompts, over the H and
I lines the room speaks, and over the text of every prompt the room hands a model.

The English *told back* stays where it is hers — the analyst prompt's own output rule is
phrased about the telling-back — because it is the glossary's English term for the act, not
the retired Portuguese, and a sweep that took it would be a sweep of the wrong language.
Our own sentences in the verdict prompt are another matter: ENG-876 reverted those to her
*translated*, so the file says one thing about the act rather than one of each.
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
#: That section, from its heading to the next, cut out before the sweep below reads the
#: prompt. It is the one place the retired words belong, because naming them is how it
#: forbids them — *never "você", "teu", "tua", "me conta"* is the rule itself.
THE_RULE_THAT_NAMES_THEM = re.compile(
    rf"^{re.escape(WHO_YOU_ARE_TALKING_TO)}\n.*?(?=^## )", re.M | re.S
)
#: The sentence that replaces the July ceiling, removed on her word of 2026-09-04: a verdict
#: that names a whole relation does not fit in twenty seconds, and a voice told to fit drops
#: a path or trims the relation, which makes "isso a história não conta" untrue of what it
#: just said. One finding per turn carries the discipline instead.
NO_LENGTH_LIMIT = "No length limit: say what the moment needs, and stop."


#: The glossary's English for the act. This ticket retires the Portuguese, not this.
THE_GLOSSARYS_ENGLISH = "told back"

#: The two families the Room speaks rather than ships: H when a stretch is still waiting,
#: I when the stretch pointed at will be replaced. Both are synthesized in the request that
#: needs them, so the new wording reaches a team with no app release in between. Keyed by
#: the enum that already names them, which is also how the sibling count table keys them.
SPOKEN_FAMILIES = {FailSafe.UNTOLD_STRETCH: 3, FailSafe.STRETCH_TO_CORRECT: 1}
#: The languages whose H and I lines this ticket rewrites.
SPOKEN_LANGUAGES = ("pt",)
#: What a spoken line may no longer say. Case-blind, because a sentence that opens with the
#: retired verb is missed by a case-sensitive pattern.
RETIRED_IN_A_SPOKEN_LINE = re.compile(
    r"contar|contem|contado|contarem|contaram|contarme",
    re.IGNORECASE,
)
#: What it has to say instead: *traduzir*, in every person the lines put it in. Asserted
#: positively because the sweep above only takes the old verb away, and a line that asked for
#: neither would pass it.
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


def test_the_english_term_stays_in_the_analyst() -> None:
    assert THE_GLOSSARYS_ENGLISH in ANALYST, (
        "o termo inglês do glossário saiu junto com o português aposentado"
    )


#: Her line for the turn's shape. *Short* was ours, and both files say there is no length
#: limit a few lines below — so the prompt asked for a short turn and then said not to.
ONE_WARM_TURN = "one warm turn"
A_SHORT_WARM_TURN = "one short, warm turn"

#: The four English lines of the spoken families. Their Portuguese counterparts were put in
#: the room's own word by ENG-873 and these were left behind, so the room asked a team for a
#: *translation* in Portuguese and for a *telling* in English, about the same act.
THE_ENGLISH_STEM = "translat"
#: The English blocks carry no language tag — H and I are written here because the authored
#: file has no English to fall back to — so they are cut by the bare family heading.
_ENGLISH_HEADING = "^### {family}\\..*?(?=^##|\\Z)"
#: What an English spoken line may no longer say. Bounded, because *translate* carries no
#: *tell* and a bare `tell` would match nothing here while `told` would match the heading.
RETIRED_IN_AN_ENGLISH_LINE = re.compile(r"\btell me\b|\btold me\b", re.IGNORECASE)


def _english_block(text: str, family: FailSafe) -> str:
    found = re.search(_ENGLISH_HEADING.format(family=family), text, re.M | re.S)
    assert found, f"o bloco {family} em inglês não está no suplemento"
    return found.group(0)


def test_the_verdict_prompt_asks_for_one_warm_turn() -> None:
    """The turn has her shape and no length of ours on top of it.

    *Short* is the July ceiling by another name: the sentence four lines from the bottom
    says there is no length limit, so the prompt asked for both and the Speaker was free to
    read either. What keeps a verdict from sprawling is one finding per turn, not a word.
    """
    assert ONE_WARM_TURN in SPEAKER, "o veredito não pede mais um turno caloroso"
    assert A_SHORT_WARM_TURN not in SPEAKER, "o veredito ainda pede um turno curto, palavra nossa"
    assert NO_LENGTH_LIMIT in SPEAKER


def test_the_english_h_and_i_lines_ask_for_a_translation() -> None:
    """The lines the room speaks in English ask for the same act as the Portuguese ones.

    Their `-pt` counterparts were put in the room's own word and these were not, so the same
    gate spoke of a *translation* in one language and of a *telling* in the other. The header
    of each family carries the authorization for the wording, by name and date.

    Said and not merely not-said, for the reason the Portuguese case is: a line rewritten
    around neither verb would satisfy the absence while asking for something the room has no
    word for.
    """
    supplement = _supplement("pt")
    spoken = [
        line
        for family in SPOKEN_FAMILIES
        for line in _BULLET.findall(_english_block(supplement, family))
    ]
    retired = [line for line in spoken if RETIRED_IN_AN_ENGLISH_LINE.search(line)]
    silent = [line for line in spoken if THE_ENGLISH_STEM not in line.lower()]

    written = sum(SPOKEN_FAMILIES.values())

    assert len(spoken) == written, (
        f"as famílias faladas em inglês não têm mais {written} fala(s): {spoken}"
    )
    assert retired == [], f"uma fala inglesa ainda pede que a equipe conte: {retired}"
    assert silent == [], f"uma fala inglesa não pede tradução: {silent}"


@pytest.mark.parametrize("family", SPOKEN_FAMILIES)
@pytest.mark.parametrize("language", SPOKEN_LANGUAGES)
def test_the_h_and_i_lines_say_traduzir_in_portuguese(language: str, family: FailSafe) -> None:
    """The lines the room speaks say *traduzir* too, and there are still as many of them.

    One case per family and language, so each block is seen to fail on its own: a single
    case over both families stops at H and leaves I's guard unwatched.

    Said and not merely not-said: the absence of *contar* is half the ruling, and a line
    rewritten around neither verb would satisfy it while asking the team for something the
    room no longer has a word for. Each line has to carry the stem itself.

    The count is asserted beside the words because a swap done line by line is exactly the
    edit that drops one: the H family says the same thing three ways so a second failure in
    a row is not the same sentence, and `SPOKEN_FAMILIES` is the table that holds how many
    each family has.
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
def test_no_prompt_text_says_retrotraducao(key: IRPromptKey) -> None:
    """The word the room retired does not survive in anything a model is handed.

    It guarded the `description` slot until ENG-876, and that slot has had no runtime reader
    since ADR 0016 put the prompt text in the files: a word can only reach a team through
    what a model reads, so the guard moved onto the text itself, where every key is swept.

    The slot is asserted gone in the same case, because a description left in place is a
    second copy of a prompt's name free to drift from the one the room uses.
    """
    served = default_prompt(key)

    assert set(served) == {"name", "prompt"}, f"{key} ainda serve uma descrição sem leitor"
    assert "retrotradução" not in served["prompt"], (
        f"o prompt de {key} ainda chama a tradução de retrotradução"
    )
