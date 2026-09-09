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
