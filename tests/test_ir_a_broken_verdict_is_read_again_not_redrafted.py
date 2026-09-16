"""What a Validator reply the room cannot read costs the team.

The Validator is asked for a bare JSON object. When it answered with prose around the
object, or with prose alone, the room read that as `regenerate`, spent a Guide redraft on
a verdict nobody could read, and on the next unreadable reply spent the last one — a team
that did nothing wrong heard the family-A line after three model round-trips. Her policy
names this case as its own: the draft is validated again, and only when the second
reading also fails does a fixed line answer, with the Guide's redrafts unspent.
"""

from app.services.internalization_room.validator_reply import _parse_verdict

PASS = {"verdict": "pass", "issues": []}


def test_a_verdict_inside_a_code_fence_is_read() -> None:
    verdict, refusal = _parse_verdict('```json\n{"verdict": "pass", "issues": []}\n```')

    assert refusal is None
    assert verdict == PASS


def test_a_verdict_wrapped_in_prose_is_read() -> None:
    verdict, refusal = _parse_verdict(
        'Here is my verdict: {"verdict": "pass", "issues": []} — hope that helps.'
    )

    assert refusal is None
    assert verdict == PASS


def test_a_reply_with_no_object_in_it_is_refused_and_is_not_a_regenerate() -> None:
    verdict, refusal = _parse_verdict("desculpe, não consigo")

    assert refusal is not None
    assert verdict.get("verdict") != "regenerate"
    assert verdict.get("issues", []) == []


def test_a_correction_with_nothing_to_say_is_refused_and_is_not_a_regenerate() -> None:
    verdict, refusal = _parse_verdict('{"verdict": "correct", "corrected_response": "  "}')

    assert refusal is not None
    assert verdict.get("verdict") != "regenerate"
