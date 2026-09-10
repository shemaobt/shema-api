"""The lines of DOCTRINE.md §4 that nothing in this repo was holding.

§4 is the acceptance bar — "what must not regress" — and eleven of its lines already had tests
that found them by another name: containment on P01, the second law, omission and addition,
the two languages, the voice opening the session, YHWH spoken. Six had nothing at all. The
rules were in the Guide prompt and would have survived exactly as long as nobody tightened the
paragraph they sit in, which is the drift the doctrine was written against.

The seam is the rendered Guide prompt, `default_prompt(IRPromptKey.GUIDE)`, the same one
`test_ir_a_request_to_understand_is_answered_from_the_map.py` reads. These lines are about what
the team hears, and what the team hears is decided in the prompt: §2 gives the model the
conversation, so there is no code branch below this to assert on instead.

Each expectation is written down from §4 and from her prompt at the pin, never recomputed from
ours. Where ours and hers diverge the divergence is named in the docstring rather than asserted
away — her send-off is "gravem o ensaio de vocês, na língua de vocês" and ours hands the
directions to the app, and ENG-835 adds no behaviour to the room.
"""

from __future__ import annotations

from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt

GUIDE = default_prompt(IRPromptKey.GUIDE)["prompt"]
NEVERS = "## What you never do"


def test_the_send_off_names_the_ensaio_and_the_teams_own_language() -> None:
    """§4: "final rehearsal → the send-off is always 'gravem o ensaio, na língua de vocês'".

    Hers says it in one sentence. Ours splits it: the Guide gives a readiness cue naming the
    ensaio and the team's own language, and the app plays the fixed navigation directions, which
    the Guide is told never to recite itself. Both halves of her line are in the cue, and that
    is what this holds — the wording divergence is recorded in the PR, not decided here.
    """
    assert "na língua de vocês" in GUIDE, (
        "the send-off stopped naming the language the rehearsal is in"
    )
    assert "ensaio" in GUIDE
    assert "Do not recite, replace, or improvise those navigation directions yourself." in GUIDE, (
        "the Guide may improvise the recording directions, which is how the send-off drifts"
    )


def test_the_first_rehearsal_is_the_first_oral_draft_never_the_final_translation() -> None:
    """§4: "the first rehearsal is the first oral draft, never 'the final translation'".

    A team told their first rehearsal is the final translation stops rehearsing it. The rule is
    one clause inside a numbered step about preparing the recording, so it is exactly the kind
    of line a tightening of that step drops without anyone noticing it had been a ruling.
    """
    assert "It is not the final translation, and you never call it that." in GUIDE, (
        "the Guide is no longer told not to call the first rehearsal the final translation"
    )


def test_the_guide_ends_plainly_with_no_blessing_of_its_own() -> None:
    """§4: "no blessings".

    Her reason, in the prompt at the pin: the passage carries the sacred content, and the
    Guide's own words stay plain. The two examples are named because a ban with no example is
    a ban a model reads as being about tone.
    """
    step = GUIDE[GUIDE.index("Hand the recording directions to the app") :]
    step = step[: step.index("\n## ")]
    nevers = GUIDE[GUIDE.index(NEVERS) :]
    nevers = nevers[: nevers.index("\n## ")]

    for place in (step, nevers):
        assert "blessing" in place, "one of the two places the ban is stated lost it"
        assert "Vão com Deus" in place
        assert "God bless" in place


def test_the_team_never_hears_the_words_o_mapa() -> None:
    """§4: "never 'o mapa'".

    The Meaning Map, the coverage ledger and the Validator do not exist for the team, and a
    Guide that cites the map turns a conversation about a passage into a conversation about a
    document. §6 records this one as Claude's proposal, consistent with her design law, which
    is why it is on the bar and not only in the prompt.
    """
    assert 'Never mention "the map"' in GUIDE, "the Guide may name the map to the team again"
    assert "segundo o mapa" in GUIDE, "the Portuguese form the rule exists to forbid is gone"


def test_the_register_is_eighth_grade_and_the_proclisis_is_the_spoken_one() -> None:
    """§4: "ALFE 8th-grade register (adults, L2, never dumbed down); spoken-BR proclisis".

    Both are about a team that only ever hears the Guide, once, with no way to reread — and
    both are the first thing a prompt loses when it is edited for concision. The register line
    carries "never dumbed down" with it, because the ban is on hard words, not on adults.
    """
    assert "eighth-grade level" in GUIDE, "the register the team can actually hear is unnamed"
    assert "second language" in GUIDE
    assert '*"se levantou"*' in GUIDE, "the spoken-BR pronoun placement rule is gone"
    assert '*"levantou-se"*' in GUIDE, "the written-formal form the rule rejects is unnamed"
