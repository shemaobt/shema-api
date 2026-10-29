"""The board's badges in one read: ``GET /evaluation-totals`` (OBT-665, RRF-MESA-084).

The Painel used to ask ``GET /requests/{id}/evaluation`` once per card, and every request the
mesa had not started answered 404. The totals route answers the same number for every card at
once — so the property worth pinning is that it **is** the same number, read from the same
snapshot, for the same readers, and that it stays one read however many cards there are.

No test here uses a platform-admin account, for ``test_evaluations.py``'s reason: an admin
passes every guard and a refusal written with one passes for the wrong reason.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import event, select, text

from app.db.models.resource_request import RRSnapshot
from tests.resource_request_harness import (
    REQUESTS,
    as_gestor,
    as_mesa,
    as_team,
    put_evaluation,
    submitted_request,
)

TOTALS = "/api/resource-requests/evaluation-totals"


async def totals(client, headers) -> dict[str, int]:
    res = await client.get(TOTALS, headers=headers)
    assert res.status_code == 200, res.text
    return {row["request_id"]: row["total"] for row in res.json()}


async def test_each_total_is_the_one_the_request_s_own_evaluation_answers(
    db_session, client, rrf_app
) -> None:
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    scored = await submitted_request(client, team)
    untouched = await submitted_request(client, team)
    keys = [
        row["criterion_key"]
        for row in (await put_evaluation(client, mesa, scored["id"])).json()["scores"]
    ]
    partial = [{"criterion_key": key, "score": 5 if i < 2 else None} for i, key in enumerate(keys)]
    await put_evaluation(client, mesa, scored["id"], scores=partial)

    own = await client.get(f"{REQUESTS}/{scored['id']}/evaluation", headers=mesa)

    assert own.json()["total"] == 10
    assert await totals(client, mesa) == {scored["id"]: 10}
    assert untouched["id"] not in await totals(client, mesa)


async def test_a_newer_snapshot_nobody_scored_carries_no_total(db_session, client, rrf_app) -> None:
    """The latest snapshot's evaluation, as ``get_evaluation`` and the team's status read it: a
    resubmission nobody scored is *not evaluated yet*, never the previous one's number."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await submitted_request(client, team)
    await put_evaluation(client, mesa, created["id"])
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

    assert await totals(client, mesa) == {}


async def test_two_snapshots_of_one_instant_name_the_same_one_as_the_evaluation_read(
    db_session, client, rrf_app
) -> None:
    """``created_at`` is the database's clock and can tie (one-second on SQLite): the badge and
    Parte C break it the same way, by id, so they never answer from two snapshots — nor add two
    evaluations into one total (review of shema-api#985). One twin sorts before the evaluated
    snapshot and one after, each on a request of its own: snapshots are append-only."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    for twin_id in ("0" * 32, "f" * 32):
        created = await submitted_request(client, team)
        await put_evaluation(client, mesa, created["id"])
        # The twin copies the stamp in SQL, so the tie is the column's own value, not a
        # Python datetime that the driver could write back in another format.
        await db_session.execute(
            text(
                "INSERT INTO rr_snapshots (id, request_id, document, created_at) "
                "SELECT :twin, request_id, document, created_at FROM rr_snapshots "
                "WHERE request_id = :request"
            ),
            {"twin": twin_id, "request": created["id"]},
        )
        await db_session.commit()

        own = await client.get(f"{REQUESTS}/{created['id']}/evaluation", headers=mesa)
        listed = (await totals(client, mesa)).get(created["id"])

        assert listed == (own.json()["total"] if own.status_code == 200 else None), twin_id


async def test_the_gestor_reads_the_totals_and_the_team_does_not(
    db_session, client, rrf_app
) -> None:
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    gestor = await as_gestor(db_session, rrf_app)
    created = await submitted_request(client, team)
    await put_evaluation(client, mesa, created["id"])

    assert created["id"] in await totals(client, gestor)
    refused = await client.get(TOTALS, headers=team)
    assert refused.status_code == 403
    assert created["id"] not in refused.text


async def test_the_totals_are_one_read_however_many_cards_there_are(
    db_session, client, rrf_app, test_engine
) -> None:
    """What replaced one request per card must not become one query per card: the statements
    touching the evaluation tables are counted with one evaluated request and with four."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)

    async def evaluation_reads() -> int:
        statements: list[str] = []

        @event.listens_for(test_engine.sync_engine, "before_cursor_execute")
        def _record(conn, cursor, statement, parameters, context, executemany) -> None:
            statements.append(statement)

        try:
            await totals(client, mesa)
        finally:
            event.remove(test_engine.sync_engine, "before_cursor_execute", _record)
        return len([s for s in statements if "rr_evaluation" in s])

    first = await submitted_request(client, team)
    await put_evaluation(client, mesa, first["id"])
    one = await evaluation_reads()
    for _ in range(3):
        another = await submitted_request(client, team)
        await put_evaluation(client, mesa, another["id"])

    assert len(await totals(client, mesa)) == 4
    assert await evaluation_reads() == one == 1
