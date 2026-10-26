"""The Speaker addresses a team, and calls what they did traduzir (ENG-873).

Marcia's merged verdict prompt rules who the Speaker is talking to and in whose words: a
team and never one person, and *traduzir / tradução* for what they did — *contar* belongs to
the Conversation with the Guide alone (`CONTEXT.md`, **Telling back**). Her `check-doctrine`
header rules that the guard scans code and never the prompts, because the prompts are her
artifacts and she reviews them; the ENG-881 sweep follows that and reads Python literals
only. So this file is the whole guard over the two back-translation prompts and over the text
of every prompt the room hands a model.

The English *told back* stays where it is hers — the analyst prompt's own output rule is
phrased about the telling-back — because it is the glossary's English term for the act, not
the retired Portuguese, and a sweep that took it would be a sweep of the wrong language.
Our own sentences in the verdict prompt are another matter: ENG-876 reverted those to her
*translated*, so the file says one thing about the act rather than one of each.
"""

import re

import pytest

from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt

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


def _one_line(text: str) -> str:
    """The text with its wrapping folded away, so a sentence is one sentence to search for."""
    return re.sub(r"\s+", " ", text)


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


def test_the_verdict_prompt_asks_for_one_warm_turn() -> None:
    """The turn has her shape and no length of ours on top of it.

    *Short* is the July ceiling by another name: the sentence four lines from the bottom
    says there is no length limit, so the prompt asked for both and the Speaker was free to
    read either. What keeps a verdict from sprawling is one finding per turn, not a word.
    """
    assert ONE_WARM_TURN in SPEAKER, "o veredito não pede mais um turno caloroso"
    assert A_SHORT_WARM_TURN not in SPEAKER, "o veredito ainda pede um turno curto, palavra nossa"
    assert NO_LENGTH_LIMIT in SPEAKER


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
