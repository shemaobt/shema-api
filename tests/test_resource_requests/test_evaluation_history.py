"""The avaliação's trail, written by the save and read by its own route (OBT-672).

GATE-02's D7 — *"quem subiu uma nota de 2 para 5"* — over the avaliação. ``test_history.py``
pins the recorder at the service level; what is pinned here is the wiring: ``PUT
/evaluation`` leaves the rows, ``GET /evaluation/history`` serves them, and only the mesa
and the Gestor read them (``view_evaluation``). The team never reads a score, so it never
reads the trail of one.
"""

from __future__ import annotations

from app.utils import resource_request_vocabularies as v
from app.utils.jwt import decode_token
from tests.baker import make_user
from tests.resource_request_harness import (
    REQUESTS,
    as_gestor,
    as_mesa,
    as_team,
    decidable,
    put_evaluation,
    submitted_request,
)

CRITERIA = v.CRITERION_KEYS["traducao"]


def history_url(request_id: str) -> str:
    return f"{REQUESTS}/{request_id}/evaluation/history"


def scored(value: int, *, first: int | None = None) -> list[dict[str, object]]:
    """All six criteria at ``value``, the first optionally at ``first`` instead."""
    scores = [{"criterion_key": key, "score": value} for key in CRITERIA]
    if first is not None:
        scores[0]["score"] = first
    return scores


async def history(client, headers, request_id: str) -> list[dict]:
    res = await client.get(history_url(request_id), headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def user_id(headers: dict[str, str]) -> str:
    return decode_token(headers["Authorization"].removeprefix("Bearer "))["sub"]


async def test_a_score_raised_from_2_to_5_is_in_the_trail_with_author_and_date(
    db_session, client, rrf_app
) -> None:
    """The sentence D7 asks for, verbatim, through the real routes."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await submitted_request(client, team)

    assert (await put_evaluation(client, mesa, created["id"], scores=scored(2))).status_code == 200
    second = await put_evaluation(client, mesa, created["id"], scores=scored(2, first=5))
    assert second.status_code == 200, second.text

    rows = await history(client, mesa, created["id"])
    raised = [row for row in rows if row["field_key"] == CRITERIA[0] and row["old_value"] == "2"]
    assert len(raised) == 1
    assert raised[0]["new_value"] == "5"
    assert raised[0]["changed_by"] == user_id(mesa)
    assert raised[0]["changed_at"]


async def test_the_first_score_of_a_criterion_reads_from_nothing(
    db_session, client, rrf_app
) -> None:
    """A criterion scored for the first time starts from ``None``, which is not a zero —
    the side the module's own docstring says D7's example starts from."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await submitted_request(client, team)

    await put_evaluation(client, mesa, created["id"], scores=scored(3), comments="primeira leitura")

    rows = await history(client, mesa, created["id"])
    by_key = {row["field_key"]: row for row in rows}
    assert set(CRITERIA) <= set(by_key)
    assert all(
        by_key[key]["old_value"] is None and by_key[key]["new_value"] == "3" for key in CRITERIA
    )
    assert (by_key["comments"]["old_value"], by_key["comments"]["new_value"]) == (
        "",
        "primeira leitura",
    )


async def test_a_changed_comment_and_a_changed_ata_are_in_the_trail(
    db_session, client, rrf_app
) -> None:
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    other = await make_user(db_session, email="presente@rr.test")
    created = await submitted_request(client, team)
    await put_evaluation(client, mesa, created["id"], scores=scored(3), attendees=[user_id(mesa)])

    await put_evaluation(
        client,
        mesa,
        created["id"],
        scores=scored(3),
        comments="revisado",
        attendees=[user_id(mesa), other.id],
    )

    rows = await history(client, mesa, created["id"])
    latest_ata = [row for row in rows if row["field_key"] == "attendees"][-1]
    assert latest_ata["old_value"] == f'["{user_id(mesa)}"]'
    assert other.id in latest_ata["new_value"]
    comment = [row for row in rows if row["field_key"] == "comments"][-1]
    assert (comment["old_value"], comment["new_value"]) == ("avaliado", "revisado")


async def test_rewording_the_note_to_the_team_after_the_decision_leaves_a_trace(
    db_session, client, rrf_app
) -> None:
    """Found in review: ``team_note`` is the one text of the evaluation that leaves the mesa,
    and the save rewrites it on every call — a mesa could reword what it told a team after
    deciding without a trace. ``None`` (no note) is a real value, distinct from ``""``."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await decidable(db_session, client, team)
    decided = await put_evaluation(
        client, mesa, created["id"], scores=scored(3), decision="revise", team_note="detalhe"
    )
    assert decided.status_code == 200, decided.text

    # The decision travels again: a save without it reads as undoing the decision (409).
    reworded = await put_evaluation(
        client,
        mesa,
        created["id"],
        scores=scored(3),
        decision="revise",
        team_note="detalhe o orçamento",
    )
    assert reworded.status_code == 200, reworded.text

    rows = [
        row for row in await history(client, mesa, created["id"]) if row["field_key"] == "team_note"
    ]
    assert [(row["old_value"], row["new_value"]) for row in rows] == [
        (None, "detalhe"),
        ("detalhe", "detalhe o orçamento"),
    ]
    assert rows[-1]["changed_by"] == user_id(mesa)


def test_a_score_row_that_goes_away_reads_as_a_removal_not_a_delete_plus_insert() -> None:
    """The save deletes the score rows a sheet no longer names (the leftover) — a path the
    wire cannot drive, because ``EvaluationWriteIn`` refuses a sheet missing a criterion
    (422 *missing criterion*); it is reached when a type's criteria set moves under a
    recorded evaluation. The trail's reading of it is pinned here where it lives: the key
    goes ``n → None`` once, and nothing else moves."""
    from app.services.resource_request._trail import evaluation_fields, field_changes

    before = evaluation_fields(None, "", dict.fromkeys(CRITERIA, 4), attendees=[], team_note=None)
    after = evaluation_fields(
        None, "", dict.fromkeys(CRITERIA[1:], 4), attendees=[], team_note=None
    )

    assert [(c.field_key, c.old_value, c.new_value) for c in field_changes(before, after)] == [
        (CRITERIA[0], "4", None)
    ]


async def test_a_revision_is_another_request_with_a_trail_of_its_own(
    db_session, client, rrf_app
) -> None:
    """The review asked for the trail across a revision, and the honest answer is two ids:
    ``open_revision`` mints a new request (``revision_of_id`` → the evaluated snapshot), the
    revision's evaluation leaves rows under the new id, and the original's trail stays frozen
    with the decision that asked for it."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await decidable(db_session, client, team)
    decided = await put_evaluation(
        client, mesa, created["id"], scores=scored(2), decision="revise", team_note="refaça"
    )
    assert decided.status_code == 200, decided.text
    original = await history(client, mesa, created["id"])

    opened = await client.post(f"{REQUESTS}/{created['id']}/revise", headers=team)
    assert opened.status_code == 201, opened.text
    revision_id = opened.json()["id"]
    assert revision_id != created["id"]
    resubmitted = await client.post(f"{REQUESTS}/{revision_id}/submit", headers=team)
    assert resubmitted.status_code == 200, resubmitted.text
    rescored = await put_evaluation(client, mesa, revision_id, scores=scored(2, first=5))
    assert rescored.status_code == 200, rescored.text

    revised = await history(client, mesa, revision_id)
    first = [row for row in revised if row["field_key"] == CRITERIA[0]]
    assert [(row["old_value"], row["new_value"]) for row in first] == [(None, "5")]
    assert all(row["changed_by"] == user_id(mesa) for row in revised)
    assert await history(client, mesa, created["id"]) == original
    decided_row = next(row for row in original if row["field_key"] == "decision")
    assert decided_row["new_value"] == "revise"


async def test_a_save_that_changes_nothing_adds_no_rows(db_session, client, rrf_app) -> None:
    """The mesa re-sending the same sheet is not an edit, and must not read as one."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await submitted_request(client, team)
    await put_evaluation(client, mesa, created["id"], scores=scored(4))
    before = await history(client, mesa, created["id"])

    await put_evaluation(client, mesa, created["id"], scores=scored(4))

    assert await history(client, mesa, created["id"]) == before


async def test_recording_the_decision_is_in_the_trail(db_session, client, rrf_app) -> None:
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await decidable(db_session, client, team)
    await put_evaluation(client, mesa, created["id"], scores=scored(4))

    res = await put_evaluation(client, mesa, created["id"], scores=scored(4), decision="declined")
    assert res.status_code == 200, res.text

    rows = await history(client, mesa, created["id"])
    decision = [row for row in rows if row["field_key"] == "decision"]
    assert [(row["old_value"], row["new_value"]) for row in decision] == [(None, "declined")]
    assert decision[0]["changed_by"] == user_id(mesa)


async def test_a_refused_save_leaves_no_trail(db_session, client, rrf_app) -> None:
    """The trail rides the save's transaction: a decision with nobody present is a 422 and
    writes nothing, trail included."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await decidable(db_session, client, team)

    res = await put_evaluation(
        client, mesa, created["id"], scores=scored(4), decision="declined", attendees=[]
    )

    assert res.status_code == 422
    assert await history(client, mesa, created["id"]) == []


async def test_an_unevaluated_request_has_an_empty_trail(db_session, client, rrf_app) -> None:
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await submitted_request(client, team)

    assert await history(client, mesa, created["id"]) == []


async def test_the_gestor_reads_the_trail(db_session, client, rrf_app) -> None:
    """``view_evaluation`` opens the read to mesa and Gestor, as it does the evaluation."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    gestor = await as_gestor(db_session, rrf_app)
    created = await submitted_request(client, team)
    await put_evaluation(client, mesa, created["id"], scores=scored(4))

    assert await history(client, gestor, created["id"])


async def test_a_team_reads_no_evaluation_trail(db_session, client, rrf_app) -> None:
    """The team never reads a score, so it never reads who changed one — even on its own
    request, which is the case worth pinning."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await submitted_request(client, team)
    await put_evaluation(client, mesa, created["id"], scores=scored(4))

    res = await client.get(history_url(created["id"]), headers=team)

    assert res.status_code == 403


async def test_an_unknown_request_answers_404(db_session, client, rrf_app) -> None:
    mesa = await as_mesa(db_session, rrf_app)

    res = await client.get(history_url("00000000-0000-0000-0000-000000000000"), headers=mesa)

    assert res.status_code == 404
