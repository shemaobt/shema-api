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

#: Her sub-bullet for the swapped relation, from the verdict prompt she merged on 2026-09-08
#: (`shemaobt/Tripod-Internalization`, `prompts/backtranslation_verdict_system_prompt.md`).
#: Pinned from her file and not from ours: the prompt is her artifact (ADR 0012), so the
#: oracle for it is her wording, read from her repository, and never the copy under test.
THE_SAME_FRASE_RULE = """\
  - **An addition and a missing element on the SAME frase** (the telling swapped one relation for
    another): treat them as ONE thing — quote what they translated, say what the story tells in
    its place (never anything the story keeps quiet), and ask for ONE fix: translate that frase
    again if it only entered in the translation, or record that part again, once, with the
    story's version. Never send the team to record the same part twice for one swap."""
#: The title of each sub-bullet of *How to speak the verdict*, in the order they are written.
#: The rule above has to be the one right under *Addition*: read anywhere else, it is a rule
#: about a pair the Speaker was never told it is holding.
_SUB_BULLET_TITLE = re.compile(r"^  - \*\*(.+?)\*\*", re.M)
THE_ADDITION_BULLET = "Addition:"
THE_SAME_FRASE_TITLE = "An addition and a missing element on the SAME frase"

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


def test_the_verdict_prompt_carries_marcias_same_frase_rule() -> None:
    """Her rule for the swapped relation, verbatim and where it can be read.

    Once, for the reason the frame above is counted once: a paragraph pasted twice is a prompt
    that says the rule and then says it again, and the model reads both.

    Under *Addition* rather than merely present. The rule is written as a case of an addition
    — it opens on what the team translated and ends on the one fix to ask for — so read under
    *Missing* or *Unclear* it would be an instruction about a pair the Speaker is not holding.
    Asserted as the sub-bullet that follows *Addition*, so a paste at the end of the section
    fails here while a plain `in` would pass.
    """
    titles = _SUB_BULLET_TITLE.findall(SPEAKER)

    assert THE_ADDITION_BULLET in titles, "o veredito não tem mais o item da Addition"
    assert titles[-1] != THE_ADDITION_BULLET, "a Addition é o último item: nada foi escrito sob ela"
    assert SPEAKER.count(THE_SAME_FRASE_RULE) == 1, (
        "a regra da mesma frase não está no veredito exatamente uma vez, palavra por palavra"
    )
    assert titles[titles.index(THE_ADDITION_BULLET) + 1] == THE_SAME_FRASE_TITLE, (
        f"a regra da mesma frase não é o item logo abaixo da Addition: {titles}"
    )


def test_the_closing_slot_and_the_english_term_stay() -> None:
    """What the adoption may not carry away with the retired words.

    Her file has no `{{CLOSING}}`: the closings are ours, and a paste of her sections that
    took the slot with it would leave the Speaker to invent the end of every turn.

    The glossary's English is guarded on the analyst prompt, where it is hers. ENG-876
    reverted the verdict's own sentences to her *translated* and left none of it there: the
    verdict describes what the room speaks about, and *told back* is the term for the act,
    not the word the room speaks. The guard is for the sweep that takes the Portuguese,
    which must not take the English with it wherever it is still hers.
    """
    assert SPEAKER.count(CLOSING_SLOT) == 1, "o veredito perdeu a vaga do fechamento"
    assert THE_GLOSSARYS_ENGLISH in ANALYST, (
        "o termo inglês do glossário saiu junto com o português aposentado"
    )


#: Ours, not hers: the four sentences of the verdict prompt that described the room's own
#: work in the retired words, and the one that gave the turn a length. Marcia's lines beside
#: them already say *translated*, so the file said both and the Speaker read both.
OUR_OWN_LINES_IN_HER_WORDS = (
    "translated for you, in {{SESSION_LANGUAGE}}, what it says",
    "An internal comparison of that translation against the passage",
    "in what they translated, no clear difference appeared",
    "this part is translated and checked",
    "only ever quote what THEY translated",
    "just ask them to tap that frase and translate it again",
)
#: What each of them said before, folded the same way. Asserted absent as well as present
#: because a sentence rewritten around neither wording would satisfy one half alone.
WHAT_OUR_LINES_USED_TO_SAY = (
    "told you back",
    "telling-back against",
    "told back, no clear",
    "told back and checked",
    "THEY told back",
    "tell that piece again",
)
#: Hers, and not this ticket's to revert: the law is *translated for you* already, and the
#: analyst's output rule is phrased about the telling-back in her own hand.
THE_LAW_IN_HER_WORDS = "only what they translated for you"
THE_ANALYSTS_OWN_TELLING_BACK = "phrased about the telling-back"
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


def test_our_own_lines_in_the_verdict_say_translated() -> None:
    """The prompt says *translated* in her sentences and in ours, never one of each.

    The Speaker is told what the team did six times in this file. Four of them were hers and
    already said *translated*; the rest were ours and said *told back*, which is the English
    the glossary keeps for the act and not the word the room speaks about it. A file that
    says both leaves the model to choose, and it chose.

    Gathered before the assertion rather than asserted one by one: a case that stops at the
    first sentence that never arrived reports it as the whole truth and leaves the other five
    unwatched.
    """
    folded = _one_line(SPEAKER)
    missing = [line for line in OUR_OWN_LINES_IN_HER_WORDS if line not in folded]
    still_said = [line for line in WHAT_OUR_LINES_USED_TO_SAY if line in folded]

    assert missing == [], f"as frases nossas não foram revertidas para as dela: {missing}"
    assert still_said == [], f"o veredito ainda diz o que era nosso: {still_said}"
    assert THE_LAW_IN_HER_WORDS in folded, "a lei dela saiu junto com as frases nossas"
    assert THE_ANALYSTS_OWN_TELLING_BACK in _one_line(ANALYST), (
        "a regra de saída do analista, que é dela, saiu junto"
    )


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
