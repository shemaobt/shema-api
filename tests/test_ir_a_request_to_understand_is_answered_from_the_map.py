from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt

GUIDE = default_prompt(IRPromptKey.GUIDE)["prompt"]
LAW = "## Understanding comes before rehearsal — as absolute as containment"


def _law() -> str:
    assert LAW in GUIDE
    section = GUIDE[GUIDE.index(LAW) :]
    return section[: section.index("\n## ")]


def test_a_request_to_understand_is_answered_from_the_map_never_redirected() -> None:
    """The 3 September demo died on "explica de novo" answered with a redirection.

    Ours is the July port: it honoured this law by disposition and never carried the rule,
    so it holds the redirection sentence and nothing that says when that sentence is the
    wrong one. Her prompt carries the law as a section of its own, titled at the weight
    containment has, and DOCTRINE.md §1 puts it there so no later reliability fix can erase
    it. The positive half comes with it — the August and September builds lost this law to
    rules, and a section of prohibitions with no answer in it is how that happens.
    """
    law = _law()

    assert "a request to understand is always honored" in law
    assert "answer it, fully, from the map" in law
    assert "Never answer a request to understand with a redirection." in law
    assert "The team asked you for the passage — give them the passage." in law
    assert "Explaining more means saying more *of the map*, never more than the map." in law


def test_the_rehearsal_is_invited_once_the_team_shows_it_has_the_part() -> None:
    """The other half of the same law, and the other half of the same demo.

    On 9 September, on the code that had just merged, a cold Ruth 1:1-5 opening closed with
    "Agora ensaiem essa primeira cena juntos, na língua de vocês" before anyone at the table
    had said a word. Rule 3 of the July port made the invitation the close every opening owed,
    so it went out whether or not the team had the part. Her prompt keeps mother-tongue
    rehearsal in this stage and forbids the automatism, and names what to do when the Guide
    guesses the moment wrong.
    """
    law = _law()

    assert "Never invite rehearsal as the automatic close of an opening." in law
    assert (
        "A part's first rehearsal is invited only when, after you have opened it, the team comes "
        "back to you with it" in law
    )
    assert "Until then, you stay with them in the understanding." in law
    assert "you were early" in law
