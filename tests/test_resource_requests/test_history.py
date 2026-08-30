"""The field-by-field trail, both halves (BE-15, OBT-475).

GATE-02's D7 — *"sim, sempre mantenha os históricos das mudanças"*, granular to *"quem
subiu uma nota de 2 para 5"* — over the solicitação **and** the avaliação. The request
half is tested through the real routes, because ``update_draft`` is where the base
actually writes fields; the evaluation half is tested at the service level, because its
endpoints are BE-06's and do not exist yet — what is pinned here is the generic recorder
BE-06 will thread through them.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.resource_request import (
    RRDecision,
    RREvaluation,
    RREvaluationFieldHistory,
    RREvaluationScore,
    RRRequest,
    RRRequestFieldHistory,
    RRSnapshot,
)
from app.services.resource_request import evaluation_fields, record_evaluation_trail
from tests.baker import make_user
from tests.test_resource_requests.conftest import auth_header, grant
from tests.test_resource_requests.test_requests import (
    REQUESTS,
    as_team,
    create,
    draft,
)


async def trail_rows(db_session: AsyncSession, request_id: str) -> list[RRRequestFieldHistory]:
    rows = await db_session.execute(
        select(RRRequestFieldHistory)
        .where(RRRequestFieldHistory.request_id == request_id)
        .order_by(RRRequestFieldHistory.changed_at, RRRequestFieldHistory.field_key)
    )
    return list(rows.scalars().all())


# ——— what a save records ————————————————————————————————————————————————————————


async def test_an_edit_records_who_changed_what_from_what_to_what(
    db_session, client, rrf_app
) -> None:
    """The sentence D7 asks for, verbatim, off the table itself.

    One field moved, so one row exists — a trail that recorded untouched fields would
    bury the change it exists to show.
    """
    user = await make_user(db_session, email="autora@rr.test")
    await grant(db_session, user, rrf_app, "equipe")
    headers = await auth_header(db_session, user)
    created = await create(client, headers)

    changed = draft()
    changed["fields"]["reg_name"] = "Projeto Xerente"
    res = await client.patch(f"{REQUESTS}/{created['id']}", json=changed, headers=headers)
    assert res.status_code == 200, res.text

    rows = await trail_rows(db_session, created["id"])
    assert len(rows) == 1
    row = rows[0]
    assert row.field_key == "reg_name"
    assert (row.old_value, row.new_value) == ("preenchido", "Projeto Xerente")
    assert row.changed_by == user.id
    assert row.changed_at is not None


async def test_a_save_that_changes_nothing_writes_no_trail(db_session, client, rrf_app) -> None:
    """Autosave re-sending the same document is not an edit, and must not read as one."""
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)

    res = await client.patch(f"{REQUESTS}/{created['id']}", json=draft(), headers=headers)
    assert res.status_code == 200, res.text

    assert await trail_rows(db_session, created["id"]) == []


async def test_a_creation_writes_no_trail(db_session, client, rrf_app) -> None:
    """A birth is not a change: ``created_by``/``created_at`` record it on the document.

    Every past state, the initial one included, reconstructs from the current document
    walked backwards through the trail — recording the ~45 initial values per creation
    would say nothing those two columns do not already say.
    """
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)

    assert await trail_rows(db_session, created["id"]) == []


async def test_a_discarded_stale_copy_leaves_no_trail(db_session, client, rrf_app) -> None:
    """Latest-wins discarded the incoming copy, so no field changed and none may claim to."""
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)
    stale = datetime.now(UTC) - timedelta(days=1)

    sent = draft()
    sent["fields"]["reg_name"] = "nome antigo"
    res = await client.patch(
        f"{REQUESTS}/{created['id']}",
        json=sent,
        params={"saved_at": stale.isoformat()},
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["discarded"] is not None

    assert await trail_rows(db_session, created["id"]) == []


async def test_a_budget_cell_is_recorded_by_its_category(db_session, client, rrf_app) -> None:
    """``budget.<category_key>.amount``, not *the budget changed*.

    The old side is ``None`` — the cell had no value at all — and the new side is the
    money render's own string, the one every later read of the document shows.
    """
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)

    changed = draft()
    lines = changed["budget"]
    assert isinstance(lines, list)
    lines[0]["amount"] = "150.5"
    category = lines[0]["category_key"]
    res = await client.patch(f"{REQUESTS}/{created['id']}", json=changed, headers=headers)
    assert res.status_code == 200, res.text

    rows = await trail_rows(db_session, created["id"])
    assert [row.field_key for row in rows] == [f"budget.{category}.amount"]
    assert rows[0].old_value is None
    assert rows[0].new_value == "150.50"


async def test_the_mesa_editing_is_recorded_as_the_mesa(db_session, client, rrf_app) -> None:
    """Owner and editor are different facts: D4 lets the mesa edit what the team wrote,
    and D7 is what keeps that from being silent."""
    team_headers = await as_team(db_session, rrf_app)
    created = await create(client, team_headers)

    mesa_user = await make_user(db_session, email="mesa-editora@rr.test")
    await grant(db_session, mesa_user, rrf_app, "mesa")
    mesa_headers = await auth_header(db_session, mesa_user)

    changed = draft()
    changed["fields"]["reg_name"] = "corrigido pela mesa"
    res = await client.patch(f"{REQUESTS}/{created['id']}", json=changed, headers=mesa_headers)
    assert res.status_code == 200, res.text

    rows = await trail_rows(db_session, created["id"])
    assert len(rows) == 1
    assert rows[0].changed_by == mesa_user.id

    stored = (
        await db_session.execute(select(RRRequest).where(RRRequest.id == created["id"]))
    ).scalar_one()
    assert stored.created_by != mesa_user.id, "editing must not move ownership"


async def test_two_saves_read_back_in_order(db_session, client, rrf_app) -> None:
    """The rows chain — the old side of the second save is the new side of the first.

    The writer stamps one instant per save in Python precisely so two saves inside the
    same second still order; SQLite's own ``CURRENT_TIMESTAMP`` could not tell them apart.
    """
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)

    first = draft()
    first["fields"]["reg_name"] = "primeiro nome"
    await client.patch(f"{REQUESTS}/{created['id']}", json=first, headers=headers)
    second = draft()
    second["fields"]["reg_name"] = "segundo nome"
    await client.patch(f"{REQUESTS}/{created['id']}", json=second, headers=headers)

    rows = await trail_rows(db_session, created["id"])
    assert [(row.old_value, row.new_value) for row in rows] == [
        ("preenchido", "primeiro nome"),
        ("primeiro nome", "segundo nome"),
    ]


# ——— the read surface ————————————————————————————————————————————————————————————


async def test_the_owner_reads_its_own_trail(db_session, client, rrf_app) -> None:
    """The team is in on purpose: the mesa may edit its document (D4), and the trail is
    how the team sees that happen — part of owning the document."""
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)
    changed = draft()
    changed["fields"]["reg_name"] = "novo nome"
    await client.patch(f"{REQUESTS}/{created['id']}", json=changed, headers=headers)

    res = await client.get(f"{REQUESTS}/{created['id']}/history", headers=headers)

    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body) == 1
    assert body[0]["field_key"] == "reg_name"
    assert body[0]["old_value"] == "preenchido"
    assert body[0]["new_value"] == "novo nome"
    assert body[0]["changed_by"]
    assert body[0]["changed_at"]


async def test_another_team_gets_the_same_404_the_document_answers(
    db_session, client, rrf_app
) -> None:
    """Out of scope is 404 and never 403, for the trail exactly as for the document —
    a trail that answered 403 would confirm the id the document refuses to."""
    mine = await as_team(db_session, rrf_app, "one@rr.test")
    theirs = await as_team(db_session, rrf_app, "two@rr.test")
    created = await create(client, mine)

    res = await client.get(f"{REQUESTS}/{created['id']}/history", headers=theirs)

    assert res.status_code == 404


async def test_the_mesa_reads_any_requests_trail(db_session, client, rrf_app) -> None:
    """Auditing who changed what is the thing D7 asked for, and the mesa is who asked."""
    team_headers = await as_team(db_session, rrf_app)
    created = await create(client, team_headers)

    mesa_user = await make_user(db_session, email="mesa-auditora@rr.test")
    await grant(db_session, mesa_user, rrf_app, "mesa")
    mesa_headers = await auth_header(db_session, mesa_user)

    res = await client.get(f"{REQUESTS}/{created['id']}/history", headers=mesa_headers)

    assert res.status_code == 200
    assert res.json() == []


# ——— the avaliação's half, at the service level ——————————————————————————————————


async def evaluation_fixture(db_session: AsyncSession, author_id: str) -> RREvaluation:
    """A request, its snapshot and one evaluation — the rows BE-06 will edit for real."""
    db_session.add(
        RRRequest(
            id="r-trail",
            request_type="traducao",
            stage="triagem",
            currency="BRL",
            created_by=author_id,
        )
    )
    await db_session.flush()
    db_session.add(RRSnapshot(id="s-trail", request_id="r-trail"))
    await db_session.flush()
    evaluation = RREvaluation(id="e-trail", snapshot_id="s-trail")
    db_session.add(evaluation)
    db_session.add(
        RREvaluationScore(evaluation_id="e-trail", criterion_key="traducao_orcamento", score=2)
    )
    await db_session.commit()
    return evaluation


async def test_a_score_bump_records_both_sides(db_session: AsyncSession) -> None:
    """D7's own example — *quem subiu uma nota de 2 para 5* — through the generic recorder.

    The endpoints that will call this are BE-06's (OBT-455, backlog); what is pinned here
    is that the service they thread through already answers the example.
    """
    mesa = await make_user(db_session, email="mesa@trilha.test")
    evaluation = await evaluation_fixture(db_session, mesa.id)

    before = evaluation_fields(None, "", {"traducao_orcamento": 2})
    after = evaluation_fields(None, "", {"traducao_orcamento": 5})
    record_evaluation_trail(db_session, evaluation.id, mesa.id, before, after)
    await db_session.commit()

    rows = (
        (
            await db_session.execute(
                select(RREvaluationFieldHistory).where(
                    RREvaluationFieldHistory.evaluation_id == evaluation.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].field_key == "traducao_orcamento"
    assert (rows[0].old_value, rows[0].new_value) == ("2", "5")
    assert rows[0].changed_by == mesa.id


async def test_a_first_score_a_decision_and_a_comment_each_leave_their_row(
    db_session: AsyncSession,
) -> None:
    """The two non-score keys are the model docstring's own — ``decision``, ``comments`` —
    and a first score's old side is ``None``: *not scored* is not a scored zero."""
    mesa = await make_user(db_session, email="mesa2@trilha.test")
    evaluation = await evaluation_fixture(db_session, mesa.id)

    before = evaluation_fields(None, "", {"traducao_orcamento": 2, "traducao_equipe": None})
    after = evaluation_fields(
        RRDecision.APPROVED, "orçamento sólido", {"traducao_orcamento": 2, "traducao_equipe": 4}
    )
    rows = record_evaluation_trail(db_session, evaluation.id, mesa.id, before, after)
    await db_session.commit()

    by_key = {row.field_key: (row.old_value, row.new_value) for row in rows}
    assert by_key == {
        "decision": (None, "approved"),
        "comments": ("", "orçamento sólido"),
        "traducao_equipe": (None, "4"),
    }


async def test_an_unchanged_evaluation_records_nothing(db_session: AsyncSession) -> None:
    mesa = await make_user(db_session, email="mesa3@trilha.test")
    evaluation = await evaluation_fixture(db_session, mesa.id)

    same = evaluation_fields(None, "", {"traducao_orcamento": 2})
    rows = record_evaluation_trail(db_session, evaluation.id, mesa.id, same, dict(same))
    await db_session.commit()

    assert rows == []
