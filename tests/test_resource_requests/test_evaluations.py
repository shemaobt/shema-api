"""Parte C through the real routes: scores, ata, decision — and what each role may touch.

The rule under all of it is GATE-02 D5 plus D6 in one breath: **one evaluation per
snapshot, signed on behalf of the mesa, and recording its decision moves the card** — with
the ledger written in the same transaction when the decision is ``approved``. The rest is
the shape of the fences around it: the Gestor reads and never writes (*"ele nem pontua nem
decide"*), the team reads a four-field status and nothing else (GATE-03 D4), and the
server stamps evaluator and instant where a payload cannot.

No test here uses a platform-admin account: an admin passes every guard in the module
unconditionally (``_deps.py``), so a negative test written with one passes for the wrong
reason.

The draft builders are ``test_requests``'s own, imported rather than repeated — a second
copy of the 26-row payload would drift exactly the way second serializers do.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import event, select

from app.db.models.resource_request import (
    RRBoardTransition,
    RREvaluation,
    RREvaluationAttendee,
    RRFund,
    RRFundMovement,
    RRMovementKind,
    RRRequest,
    RRSnapshot,
)
from app.utils import resource_request_vocabularies as v
from tests.baker import make_user
from tests.test_resource_requests.conftest import auth_header, grant
from tests.test_resource_requests.test_requests import as_mesa, as_team, create

REQUESTS = "/api/resource-requests/requests"


def evaluation(request_type: str = "traducao", **over: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "request_type": request_type,
        "scores": [{"criterion_key": key, "score": 4} for key in v.CRITERION_KEYS[request_type]],
        "comments": "avaliado",
    }
    payload.update(over)
    return payload


async def as_gestor(db_session, rrf_app, email: str = "gestor@rr.test") -> dict[str, str]:
    user = await make_user(db_session, email=email)
    await grant(db_session, user, rrf_app, "gestor")
    return await auth_header(db_session, user)


async def submitted_request(client, headers) -> dict:
    created = await create(client, headers)
    res = await client.post(f"{REQUESTS}/{created['id']}/submit", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


async def give_fund(db_session, request_id: str, fund_id: str = "linguas") -> None:
    """The mesa assigns the fund at triage (GATE-01 D4); the route for it is BE-11's,
    so until it exists a test writes the column the way the mesa's screen will."""
    if (
        await db_session.execute(select(RRFund).where(RRFund.id == fund_id))
    ).scalar_one_or_none() is None:
        db_session.add(RRFund(id=fund_id, name="Shema Línguas"))
    request = (
        await db_session.execute(select(RRRequest).where(RRRequest.id == request_id))
    ).scalar_one()
    request.fund_id = fund_id
    await db_session.commit()


async def put_evaluation(client, headers, request_id: str, **over: object):
    return await client.put(
        f"{REQUESTS}/{request_id}/evaluation", json=evaluation(**over), headers=headers
    )


# ——— who may touch it ————————————————————————————————————————————————————————————


async def test_a_team_reads_no_evaluation_and_writes_none(db_session, client, rrf_app) -> None:
    """``view_evaluation`` and ``edit_evaluation`` both exclude ``equipe`` — even on the
    team's own request, which is the case worth pinning."""
    headers = await as_team(db_session, rrf_app)
    created = await submitted_request(client, headers)

    read = await client.get(f"{REQUESTS}/{created['id']}/evaluation", headers=headers)
    write = await put_evaluation(client, headers, created["id"])

    assert read.status_code == 403
    assert write.status_code == 403


async def test_the_gestor_reads_and_does_not_write(db_session, client, rrf_app) -> None:
    """*"ele nem pontua nem decide, essa função é exclusiva da mesa"* — client, 28/aug/2026."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    gestor = await as_gestor(db_session, rrf_app)
    created = await submitted_request(client, team)
    assert (await put_evaluation(client, mesa, created["id"])).status_code == 200

    read = await client.get(f"{REQUESTS}/{created['id']}/evaluation", headers=gestor)
    write = await put_evaluation(client, gestor, created["id"], comments="do gestor")

    assert read.status_code == 200
    assert write.status_code == 403


# ——— the save ————————————————————————————————————————————————————————————————————


async def test_nothing_is_evaluated_before_submission(db_session, client, rrf_app) -> None:
    """An evaluation scores a frozen document; a draft still moving has none."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await create(client, team)

    res = await put_evaluation(client, mesa, created["id"])

    assert res.status_code == 409


async def test_the_evaluation_comes_back_whole_with_the_total_derived(
    db_session, client, rrf_app
) -> None:
    """The /30 is computed on the read, in the criterion order of the type."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await submitted_request(client, team)

    res = await put_evaluation(client, mesa, created["id"])

    assert res.status_code == 200, res.text
    body = res.json()
    assert [s["criterion_key"] for s in body["scores"]] == list(v.CRITERION_KEYS["traducao"])
    assert body["total"] == 24
    assert body["decision"] is None
    assert body["evaluated_at"] is None
    assert body["evaluator_id"] is not None
    assert body["team_note"] is None


async def test_the_total_is_never_accepted_from_the_client(db_session, client, rrf_app) -> None:
    """A stated total is a claim, checked against the scores; a total field does not exist."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await submitted_request(client, team)

    wrong_claim = await put_evaluation(client, mesa, created["id"], stated_total=30)
    invented_field = await put_evaluation(client, mesa, created["id"], total=30)
    right_claim = await put_evaluation(client, mesa, created["id"], stated_total=24)

    assert wrong_claim.status_code == 422
    assert invented_field.status_code == 422
    assert right_claim.status_code == 200
    assert right_claim.json()["total"] == 24


async def test_a_score_outside_zero_to_five_is_refused(db_session, client, rrf_app) -> None:
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await submitted_request(client, team)

    scores = [{"criterion_key": key, "score": 4} for key in v.CRITERION_KEYS["traducao"]]
    scores[0]["score"] = 6

    res = await put_evaluation(client, mesa, created["id"], scores=scores)

    assert res.status_code == 422


async def test_a_criterion_of_another_type_is_refused(db_session, client, rrf_app) -> None:
    """``CRITERION_KEYS[request_type]`` applied on the write, both ways it can be dodged:
    keys that do not belong to the claimed type, and a claimed type that is not the
    request's."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await submitted_request(client, team)

    foreign_keys = await put_evaluation(
        client,
        mesa,
        created["id"],
        scores=[{"criterion_key": key, "score": 3} for key in v.CRITERION_KEYS["treinamento"]],
    )
    foreign_type = await put_evaluation(client, mesa, created["id"], request_type="treinamento")

    assert foreign_keys.status_code == 422
    assert foreign_type.status_code == 400


async def test_the_payload_cannot_state_the_evaluator_or_the_instant(
    db_session, client, rrf_app
) -> None:
    """Both are the server's stamps; a payload that tries is refused, not ignored."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await submitted_request(client, team)

    with_evaluator = await put_evaluation(client, mesa, created["id"], evaluator_id="alguém")
    with_instant = await put_evaluation(
        client, mesa, created["id"], evaluated_at="2026-08-30T12:00:00Z"
    )

    assert with_evaluator.status_code == 422
    assert with_instant.status_code == 422


async def test_one_evaluation_per_snapshot(db_session, client, rrf_app) -> None:
    """GATE-02 D5: the second save updates the mesa's one row, never adds a second."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await submitted_request(client, team)

    first = await put_evaluation(client, mesa, created["id"], comments="primeira")
    second = await put_evaluation(client, mesa, created["id"], comments="segunda")

    assert first.status_code == 200 and second.status_code == 200
    rows = (await db_session.execute(select(RREvaluation))).scalars().all()
    assert len(rows) == 1
    assert rows[0].comments == "segunda"


# ——— the ata —————————————————————————————————————————————————————————————————————


async def test_the_ata_records_who_was_present(db_session, client, rrf_app) -> None:
    """D5's second record: who was in the room, apart from who signed for the mesa."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    presente = await make_user(db_session, email="presente@rr.test")
    created = await submitted_request(client, team)

    res = await put_evaluation(client, mesa, created["id"], attendees=[presente.id])

    assert res.status_code == 200, res.text
    assert res.json()["attendees"] == [presente.id]
    rows = (await db_session.execute(select(RREvaluationAttendee))).scalars().all()
    assert [row.user_id for row in rows] == [presente.id]


async def test_a_member_without_an_account_is_not_recordable(db_session, client, rrf_app) -> None:
    """The right refusal, decidable: the way in for that member is an account (BE-17)."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await submitted_request(client, team)
    sem_conta = str(uuid.uuid4())

    res = await put_evaluation(client, mesa, created["id"], attendees=[sem_conta])

    assert res.status_code == 422
    assert sem_conta in res.json()["detail"]
    assert (await db_session.execute(select(RREvaluation))).scalars().all() == []


async def test_the_ata_is_corrected_not_compensated(db_session, client, rrf_app) -> None:
    """Minutes, not a trail: the next save replaces the room list."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    a = await make_user(db_session, email="a@rr.test")
    b = await make_user(db_session, email="b@rr.test")
    created = await submitted_request(client, team)

    await put_evaluation(client, mesa, created["id"], attendees=[a.id])
    res = await put_evaluation(client, mesa, created["id"], attendees=[b.id])

    assert res.json()["attendees"] == [b.id]
    rows = (await db_session.execute(select(RREvaluationAttendee))).scalars().all()
    assert [row.user_id for row in rows] == [b.id]


# ——— the decision ————————————————————————————————————————————————————————————————


async def test_recording_the_decision_moves_the_card(db_session, client, rrf_app) -> None:
    """GATE-02 D6: the save is the move — with author and instant stamped by the server."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await submitted_request(client, team)

    res = await put_evaluation(client, mesa, created["id"], decision="conditional")

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["decision"] == "conditional"
    assert body["evaluated_at"] is not None

    request = (
        await db_session.execute(select(RRRequest).where(RRRequest.id == created["id"]))
    ).scalar_one()
    assert request.stage.value == "condicional"

    transition = (await db_session.execute(select(RRBoardTransition))).scalar_one()
    assert transition.from_stage.value == "triagem"
    assert transition.to_stage.value == "condicional"
    assert transition.moved_by is not None
    assert transition.movement_id is None


async def test_approving_appends_to_the_ledger_in_the_same_write(
    db_session, client, rrf_app
) -> None:
    """Decision → ledger → stage event, one transaction: the event names the movement."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await submitted_request(client, team)
    await give_fund(db_session, created["id"])

    res = await put_evaluation(client, mesa, created["id"], decision="approved")

    assert res.status_code == 200, res.text
    movement = (await db_session.execute(select(RRFundMovement))).scalar_one()
    assert movement.kind is RRMovementKind.APPROVAL_DEDUCTION
    assert str(movement.amount) == "1200.00"
    assert movement.request_id == created["id"]
    assert movement.created_by is not None

    transition = (await db_session.execute(select(RRBoardTransition))).scalar_one()
    assert transition.movement_id == movement.id
    request = (
        await db_session.execute(select(RRRequest).where(RRRequest.id == created["id"]))
    ).scalar_one()
    assert request.stage.value == "aprovado"


async def test_approving_with_no_fund_fails_and_writes_nothing(db_session, client, rrf_app) -> None:
    """GATE-01 D4's invariant, bitten on this write path: decidable, and nothing half-saved."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await submitted_request(client, team)

    res = await put_evaluation(client, mesa, created["id"], decision="approved")

    assert res.status_code == 409
    assert "fund" in res.json()["detail"]
    request = (
        await db_session.execute(select(RRRequest).where(RRRequest.id == created["id"]))
    ).scalar_one()
    assert request.stage.value == "triagem"
    assert (await db_session.execute(select(RRFundMovement))).scalars().all() == []
    assert (await db_session.execute(select(RREvaluation))).scalars().all() == []


async def test_a_recorded_decision_is_not_rewritten(db_session, client, rrf_app) -> None:
    """Undoing an ``approved`` is a compensating movement plus a board move — BE-08's
    transaction, refused here rather than half-built."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await submitted_request(client, team)
    await give_fund(db_session, created["id"])
    assert (
        await put_evaluation(client, mesa, created["id"], decision="approved")
    ).status_code == 200

    changed = await put_evaluation(client, mesa, created["id"], decision="declined")
    dropped = await put_evaluation(client, mesa, created["id"])

    assert changed.status_code == 409
    assert dropped.status_code == 409


async def test_the_same_decision_saved_again_re_fires_nothing(db_session, client, rrf_app) -> None:
    """Scores and comments stay editable after the decision — D7 audits exactly that —
    but the card moved once and the ledger was written once."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await submitted_request(client, team)
    await give_fund(db_session, created["id"])
    await put_evaluation(client, mesa, created["id"], decision="approved")

    again = await put_evaluation(
        client, mesa, created["id"], decision="approved", comments="nota revista"
    )

    assert again.status_code == 200, again.text
    assert again.json()["comments"] == "nota revista"
    assert len((await db_session.execute(select(RRFundMovement))).scalars().all()) == 1
    assert len((await db_session.execute(select(RRBoardTransition))).scalars().all()) == 1


async def test_the_signature_freezes_with_the_decision(db_session, client, rrf_app) -> None:
    """Before the decision, whoever last wrote speaks for the mesa; the save that records
    the decision signs it, and edits after it change the row without changing D5's tag —
    who edited afterwards is BE-15's fact, not the signature's."""
    team = await as_team(db_session, rrf_app)
    mesa_a = await as_mesa(db_session, rrf_app, email="mesa.a@rr.test")
    mesa_b = await as_mesa(db_session, rrf_app, email="mesa.b@rr.test")
    created = await submitted_request(client, team)

    drafted = (await put_evaluation(client, mesa_a, created["id"])).json()
    decided = (await put_evaluation(client, mesa_b, created["id"], decision="declined")).json()
    edited = (
        await put_evaluation(client, mesa_a, created["id"], decision="declined", comments="revista")
    ).json()

    assert decided["evaluator_id"] != drafted["evaluator_id"]
    assert edited["comments"] == "revista"
    assert edited["evaluator_id"] == decided["evaluator_id"]


async def test_revise_end_to_end_opens_a_revision(db_session, client, rrf_app) -> None:
    """The whole chain against ``open_revision``: the mesa asks through the real endpoint,
    the card lands on *revisar*, and the team's next move is a new draft."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await submitted_request(client, team)

    decided = await put_evaluation(
        client, mesa, created["id"], decision="revise", team_note="detalhe o orçamento"
    )
    assert decided.status_code == 200, decided.text

    request = (
        await db_session.execute(select(RRRequest).where(RRRequest.id == created["id"]))
    ).scalar_one()
    assert request.stage.value == "revisar"

    revision = await client.post(f"{REQUESTS}/{created['id']}/revise", headers=team)
    assert revision.status_code == 201, revision.text
    assert revision.json()["revision_of_id"] == created["snapshot_id"]


# ——— the team's status ———————————————————————————————————————————————————————————


async def test_the_team_reads_status_and_nothing_else(db_session, client, rrf_app) -> None:
    """GATE-03 D4 plus the 28/aug answer: four fields, among them the note addressed to
    the team — and not one field more, which is the assertion that matters."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await submitted_request(client, team)
    await put_evaluation(
        client, mesa, created["id"], decision="revise", team_note="detalhe o orçamento"
    )

    res = await client.get(f"{REQUESTS}/{created['id']}/status", headers=team)

    assert res.status_code == 200, res.text
    body = res.json()
    assert set(body) == {"stage", "submitted_at", "decision", "team_note"}
    assert body["stage"] == "revisar"
    assert body["submitted_at"] is not None
    assert body["decision"] == "revise"
    assert body["team_note"] == "detalhe o orçamento"


async def test_a_team_does_not_read_another_teams_status(db_session, client, rrf_app) -> None:
    """The same 404 as *does not exist* — a 403 would confirm the id."""
    owner = await as_team(db_session, rrf_app, email="dona@rr.test")
    other = await as_team(db_session, rrf_app, email="outra@rr.test")
    created = await submitted_request(client, owner)

    res = await client.get(f"{REQUESTS}/{created['id']}/status", headers=other)

    assert res.status_code == 404


async def test_status_before_any_evaluation_is_the_journey_alone(
    db_session, client, rrf_app
) -> None:
    team = await as_team(db_session, rrf_app)
    created = await submitted_request(client, team)

    res = await client.get(f"{REQUESTS}/{created['id']}/status", headers=team)

    assert res.status_code == 200
    body = res.json()
    assert body["stage"] == "triagem"
    assert body["decision"] is None
    assert body["team_note"] is None


async def test_the_status_read_does_not_load_the_evaluation_whole(
    db_session, client, rrf_app, test_engine
) -> None:
    """The route a team refreshes reads two columns of the evaluation, not three tables.

    ``request_status`` consumes ``decision`` and ``team_note`` and nothing else, and it
    used to reach them through ``load_evaluation`` — which fires the six score rows and the
    ata, after a snapshot read that carries the whole frozen document to use its ``id``.
    Four statements, three of them loaded and dropped.

    The property is asserted rather than a total: counting every statement would count the
    door's own lookups, which are not this route's business and would redden this case for
    a reason it is not about. That the two aggregate tables are never touched, and that the
    evaluation is read once, is what *narrow* means here.
    """
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await submitted_request(client, team)
    await put_evaluation(
        client, mesa, created["id"], decision="revise", team_note="detalhe o orçamento"
    )

    statements: list[str] = []

    @event.listens_for(test_engine.sync_engine, "before_cursor_execute")
    def _record(conn, cursor, statement, parameters, context, executemany) -> None:
        statements.append(statement)

    try:
        res = await client.get(f"{REQUESTS}/{created['id']}/status", headers=team)
    finally:
        event.remove(test_engine.sync_engine, "before_cursor_execute", _record)

    assert res.status_code == 200, res.text
    assert res.json()["decision"] == "revise"
    assert res.json()["team_note"] == "detalhe o orçamento"

    scores = [s for s in statements if "rr_evaluation_scores" in s]
    attendees = [s for s in statements if "rr_evaluation_attendees" in s]
    evaluations = [s for s in statements if "rr_evaluations" in s]
    assert scores == [], f"o status leu as notas: {scores}"
    assert attendees == [], f"o status leu a ata: {attendees}"
    assert len(evaluations) == 1, f"a avaliacao foi lida {len(evaluations)} vezes"


async def test_status_reads_the_latest_snapshot_and_not_an_older_decision(
    db_session, client, rrf_app
) -> None:
    """The join is an outer one on purpose: a snapshot nobody evaluated answers *no
    decision yet*, it does not fall back to what the mesa decided about the one before.

    Only ``submit_request`` writes snapshots and it refuses a second one, so the second
    snapshot is written here the way a resubmission would — the case the ``order_by`` and
    the ``limit`` exist for, which no route can reach today.
    """
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await submitted_request(client, team)
    await put_evaluation(client, mesa, created["id"], decision="declined")

    frozen = (
        await db_session.execute(select(RRSnapshot).where(RRSnapshot.request_id == created["id"]))
    ).scalar_one()
    db_session.add(
        RRSnapshot(
            request_id=created["id"],
            document={},
            created_at=frozen.created_at + timedelta(minutes=1),
        )
    )
    await db_session.commit()

    res = await client.get(f"{REQUESTS}/{created['id']}/status", headers=team)

    assert res.status_code == 200, res.text
    assert res.json()["decision"] is None
    assert res.json()["team_note"] is None
