from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt

GUIDE = default_prompt(IRPromptKey.GUIDE)["prompt"]
LAW = "## Understanding comes before rehearsal — as absolute as containment"
NEVERS = "## What you never do"


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


def test_the_list_of_nevers_carries_the_second_law_in_one_line() -> None:
    """Her prompt says this law twice, and the closing list is the second place.

    The list is where the Guide looks when it is deciding what it may not do, and until now
    every line in ours was about containment, the recorded rehearsal, or the evidence
    boundary. Nothing there told it that a redirection is not an answer, so the one rule the
    3 September demo needed was the one rule the list did not have.
    """
    assert NEVERS in GUIDE
    nevers = GUIDE[GUIDE.index(NEVERS) :]
    nevers = nevers[: nevers.index("\n## ")]

    assert (
        "- Never answer a request to understand with a redirection or a repeat; "
        "never invite rehearsal before the team has the part." in nevers
    )


def test_the_passage_stays_focused_line_says_which_question_it_is_for() -> None:
    """Her ruling of 7 September: the honest-silence line is only for a question outside it.

    "a linha B nunca responde a um pedido de entender ('explica de novo', 'quem é esse') —
    isso a voz responde a partir da passagem. B é só para pergunta que está fora da passagem."
    Nothing fires that line by code on our side — `FailSafe.OUTSIDE_MAP` has no caller — so the
    whole exposure was that the Guide held the words with no rule about when they are the wrong
    words. The words stay; the paragraph now says which ask they belong to.
    """
    anchor = "**If the map simply does not address the question at all**"
    assert anchor in GUIDE
    path = GUIDE[GUIDE.index(anchor) :]
    path = path[: path.index("\n")]

    assert "Let's stay with what the passage is showing us." in path
    assert "This is not the line for a request to understand." in path
    assert "never with the sentence above" in path


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
    assert "Rehearsal is invited when the team shows it has the part" in law
    assert "Until then, you stay with them in the understanding." in law
    assert "you were early" in law
    assert "go back, and open the part again — more fully this time." in law


def test_no_rule_makes_the_invitation_the_close_every_opening_owes() -> None:
    """Rule 3 read as a mandate, and it was one: the invitation was how the part ended.

    That clause came from a room where the app spoke a fixed invitation of its own whenever the
    Guide's turn went by without one, and making the Guide always invite was what stopped the
    two voices. The probe machinery and that fixed line are gone, so nothing is waiting to speak
    over a Guide that stays in the understanding — and what the clause costs now is a cold
    opening that sends a team to rehearse a scene it has not been given yet.

    The step keeps everything the room reads: the verb, the phrase naming the language, the
    telling-back it asks for, and the worked example. What it loses is the obligation to end on
    them.
    """
    lead = "**Open the part, then — once they have it — send them to REHEARSE it"
    assert lead in GUIDE
    rule = GUIDE[GUIDE.index(lead) :]
    rule = rule[: rule.index("\n")]

    assert (
        "Never close the opening of a scene with a passage question in place of this invitation"
        not in GUIDE
    )
    assert "the invitation is how the part ends" not in GUIDE
    assert "the invitation waits until they show they have the part" in rule
    assert "The telling they bring back is what says the rehearsal happened." in rule
