"""The team's instance: *Iniciar*, the pen, cancelling — BE-25 (OBT-534).

GATE-04 D2 and D6 (OBT-519, Daniel, 23/sep/2026): a member starts the project's instance, only
they write it until it is submitted or cancelled, the rest of the team reads it, and a project
has one open instance at a time. The mesa and the Gestor read and do not write, which revises
GATE-02 D4 (27/aug/2026) on the same decision; the Admin writes.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models.resource_request import RRDecision, RRRequest
from tests.baker import make_user
from tests.test_resource_requests.conftest import auth_header, grant, make_membership, make_project
from tests.test_resource_requests.test_history import trail_rows
from tests.test_resource_requests.test_requests import REQUESTS, _decide, draft

START = f"{REQUESTS}/start"


async def member_of(db_session, project_id: str, email: str):
    user = await make_user(db_session, email=email)
    await make_membership(db_session, user, project_id)
    return user, await auth_header(db_session, user)


async def as_role(db_session, rrf_app, role: str) -> dict[str, str]:
    user = await make_user(db_session, email=f"{role}@instancia.test")
    await grant(db_session, user, rrf_app, role)
    return await auth_header(db_session, user)


async def as_admin(db_session, email: str = "admin@instancia.test"):
    user = await make_user(db_session, email=email, is_platform_admin=True)
    return user, await auth_header(db_session, user)


async def start(client, headers, project_id: str | None = None, request_type: str = "traducao"):
    body: dict[str, object] = {"request_type": request_type}
    if project_id is not None:
        body["project_id"] = project_id
    return await client.post(START, json=body, headers=headers)


# ——— Iniciar, and one open instance per project ——————————————————————————————————


async def test_starting_opens_an_empty_instance_held_by_the_starter(
    db_session, client, rrf_app
) -> None:
    ana, headers = await member_of(db_session, "kadiweu", "ana@instancia.test")

    res = await start(client, headers)

    assert res.status_code == 201, res.text
    body = res.json()
    assert body["started_by"] == ana.id
    assert body["created_by"] == ana.id
    assert body["cancelled_at"] is None
    assert body["can_edit"] is True
    assert not any(body["document"]["fields"].values()), "an instance starts empty"
    row = await db_session.get(RRRequest, body["id"])
    assert row.shema_project_id == "kadiweu"


async def test_a_second_start_in_the_same_project_is_refused_until_the_first_is_cancelled(
    db_session, client, rrf_app
) -> None:
    """The DoD's first line, both halves: 409 while one is open, 201 once it is given up —
    and by another member, which is what *libera outro membro* means."""
    _ana, ana = await member_of(db_session, "kadiweu", "ana@instancia.test")
    _bia, bia = await member_of(db_session, "kadiweu", "bia@instancia.test")
    first = (await start(client, ana)).json()

    refused = await start(client, bia)
    await client.post(f"{REQUESTS}/{first['id']}/cancel", headers=ana)
    accepted = await start(client, bia)

    assert refused.status_code == 409, refused.text
    assert "one is open" in refused.json()["detail"]
    assert accepted.status_code == 201, accepted.text


async def test_the_older_door_is_under_the_same_lock(db_session, client, rrf_app) -> None:
    """``POST /requests`` starts the instance too, so choosing it does not step around D6."""
    _ana, ana = await member_of(db_session, "kadiweu", "ana@instancia.test")
    await start(client, ana)

    res = await client.post(REQUESTS, json=draft(), headers=ana)

    assert res.status_code == 409, res.text


async def test_a_submitted_instance_frees_the_project(db_session, client, rrf_app) -> None:
    """*Enviar fecha*: the lock counts open instances; OBT-508 counts submitted ones."""
    _ana, ana = await member_of(db_session, "kadiweu", "ana@instancia.test")
    sent = await client.post(REQUESTS, json=draft(), headers=ana)
    await client.post(f"{REQUESTS}/{sent.json()['id']}/submit", headers=ana)

    res = await start(client, ana)

    assert res.status_code == 201, res.text


async def test_another_project_is_not_locked_by_this_one(db_session, client, rrf_app) -> None:
    _ana, ana = await member_of(db_session, "kadiweu", "ana@instancia.test")
    _caio, caio = await member_of(db_session, "fataluku", "caio@instancia.test")
    await start(client, ana)

    assert (await start(client, caio)).status_code == 201


async def test_the_index_holds_where_the_question_is_not_asked(db_session, client, rrf_app) -> None:
    """Two members pressing *Iniciar* in the same second pass the check together; the partial
    unique index is what refuses the second row. Written straight to the table to be that
    race, with no service in front of it."""
    ana, _ = await member_of(db_session, "kadiweu", "ana@instancia.test")
    await make_project(db_session, "kadiweu")
    for _ in range(2):
        db_session.add(
            RRRequest(
                request_type="traducao",
                created_by=ana.id,
                started_by=ana.id,
                shema_project_id="kadiweu",
            )
        )

    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_requests_with_no_project_are_outside_the_lock(db_session, client, rrf_app) -> None:
    """The board's door (FE-41) and the link's until OBT-547: NULL never collides."""
    gestor = await as_role(db_session, rrf_app, "gestor")

    first = await client.post(REQUESTS, json=draft(), headers=gestor)
    second = await client.post(REQUESTS, json=draft(), headers=gestor)

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text


async def test_the_admin_starts_for_a_project_by_naming_it(db_session, client, rrf_app) -> None:
    admin, headers = await as_admin(db_session)
    await make_project(db_session, "kadiweu")

    res = await start(client, headers, project_id="kadiweu")

    assert res.status_code == 201, res.text
    assert res.json()["started_by"] == admin.id
    row = await db_session.get(RRRequest, res.json()["id"])
    assert row.shema_project_id == "kadiweu"


# ——— the pen ————————————————————————————————————————————————————————————————————


async def test_a_teammate_reads_the_instance_and_does_not_write_it(
    db_session, client, rrf_app
) -> None:
    _ana, ana = await member_of(db_session, "kadiweu", "ana@instancia.test")
    _bia, bia = await member_of(db_session, "kadiweu", "bia@instancia.test")
    started = (await start(client, ana)).json()

    read = await client.get(f"{REQUESTS}/{started['id']}", headers=bia)
    res = await client.patch(f"{REQUESTS}/{started['id']}", json=draft(), headers=bia)

    assert read.status_code == 200
    assert read.json()["can_edit"] is False
    assert res.status_code == 403, res.text
    assert await trail_rows(db_session, started["id"]) == []


@pytest.mark.parametrize("role", ["mesa", "gestor"])
async def test_the_mesa_and_the_gestor_do_not_write_a_teams_instance(
    db_session, client, rrf_app, role: str
) -> None:
    """GATE-02 D4 revised: they read the draft from the board, and writing it is not theirs."""
    _ana, ana = await member_of(db_session, "kadiweu", "ana@instancia.test")
    headers = await as_role(db_session, rrf_app, role)
    started = (await start(client, ana)).json()

    read = await client.get(f"{REQUESTS}/{started['id']}", headers=headers)
    res = await client.patch(f"{REQUESTS}/{started['id']}", json=draft(), headers=headers)

    assert read.status_code == 200
    assert read.json()["can_edit"] is False
    assert res.status_code == 403, res.text


async def test_the_admin_writes_a_teams_instance(db_session, client, rrf_app) -> None:
    _ana, ana = await member_of(db_session, "kadiweu", "ana@instancia.test")
    _admin, headers = await as_admin(db_session)
    started = (await start(client, ana)).json()

    read = await client.get(f"{REQUESTS}/{started['id']}", headers=headers)
    res = await client.patch(f"{REQUESTS}/{started['id']}", json=draft(), headers=headers)

    assert read.json()["can_edit"] is True
    assert res.status_code == 200, res.text
    assert res.json()["can_edit"] is True


async def test_the_starters_own_save_answers_can_edit(db_session, client, rrf_app) -> None:
    """The ``PATCH`` answers ``can_edit`` without asking the roles again — the autosave is the
    call a field connection pays most — and the answer is still the rule's."""
    _ana, ana = await member_of(db_session, "kadiweu", "ana@instancia.test")
    started = (await start(client, ana)).json()

    res = await client.patch(f"{REQUESTS}/{started['id']}", json=draft(), headers=ana)

    assert res.status_code == 200, res.text
    assert res.json()["can_edit"] is True


async def test_the_listing_says_who_writes_each_row(db_session, client, rrf_app) -> None:
    _ana, ana = await member_of(db_session, "kadiweu", "ana@instancia.test")
    _bia, bia = await member_of(db_session, "kadiweu", "bia@instancia.test")
    started = (await start(client, ana)).json()

    as_ana = {row["id"]: row for row in (await client.get(REQUESTS, headers=ana)).json()}
    as_bia = {row["id"]: row for row in (await client.get(REQUESTS, headers=bia)).json()}

    assert as_ana[started["id"]]["can_edit"] is True
    assert as_bia[started["id"]]["can_edit"] is False


# ——— submitting ———————————————————————————————————————————————————————————————————


async def test_only_the_starter_submits(db_session, client, rrf_app) -> None:
    _ana, ana = await member_of(db_session, "kadiweu", "ana@instancia.test")
    _bia, bia = await member_of(db_session, "kadiweu", "bia@instancia.test")
    started = (await client.post(REQUESTS, json=draft(), headers=ana)).json()

    by_teammate = await client.post(f"{REQUESTS}/{started['id']}/submit", headers=bia)
    by_starter = await client.post(f"{REQUESTS}/{started['id']}/submit", headers=ana)

    assert by_teammate.status_code == 403, by_teammate.text
    assert by_starter.status_code == 200, by_starter.text
    assert by_starter.json()["can_edit"] is False


async def test_the_admin_who_started_submits_and_the_one_who_did_not_does_not(
    db_session, client, rrf_app
) -> None:
    """The Admin writes any instance, but signs only the one they started: no grant transfers
    the electronic acceptance (BE-18)."""
    _admin, admin = await as_admin(db_session)
    _other, other_admin = await as_admin(db_session, "outro-admin@instancia.test")
    await make_project(db_session, "kadiweu")
    started = (
        await client.post(REQUESTS, params={"project_id": "kadiweu"}, json=draft(), headers=admin)
    ).json()

    by_other = await client.post(f"{REQUESTS}/{started['id']}/submit", headers=other_admin)
    by_starter = await client.post(f"{REQUESTS}/{started['id']}/submit", headers=admin)

    assert by_other.status_code == 403, by_other.text
    assert by_starter.status_code == 200, by_starter.text


# ——— cancelling ——————————————————————————————————————————————————————————————————


async def test_cancelling_marks_and_does_not_delete(db_session, client, rrf_app) -> None:
    """The row, its document and its BE-15 trail all stay; only the lock lets go of it."""
    _ana, ana = await member_of(db_session, "kadiweu", "ana@instancia.test")
    started = (await start(client, ana)).json()
    changed = draft()
    changed["fields"]["reg_name"] = "antes de cancelar"
    await client.patch(f"{REQUESTS}/{started['id']}", json=changed, headers=ana)
    trail_before = len(await trail_rows(db_session, started["id"]))

    res = await client.post(f"{REQUESTS}/{started['id']}/cancel", headers=ana)

    assert res.status_code == 200, res.text
    assert res.json()["cancelled_at"] is not None
    assert res.json()["can_edit"] is False
    row = await db_session.get(RRRequest, started["id"])
    await db_session.refresh(row)
    assert row.cancelled_at is not None
    assert row.reg_name == "antes de cancelar"
    assert trail_before > 0
    assert len(await trail_rows(db_session, started["id"])) == trail_before

    read = await client.get(f"{REQUESTS}/{started['id']}", headers=ana)
    listed = [row["id"] for row in (await client.get(REQUESTS, headers=ana)).json()]
    assert read.status_code == 200
    assert started["id"] not in listed


async def test_a_cancelled_instance_takes_no_more_writes(db_session, client, rrf_app) -> None:
    _ana, ana = await member_of(db_session, "kadiweu", "ana@instancia.test")
    started = (await client.post(REQUESTS, json=draft(), headers=ana)).json()
    await client.post(f"{REQUESTS}/{started['id']}/cancel", headers=ana)

    patched = await client.patch(f"{REQUESTS}/{started['id']}", json=draft(), headers=ana)
    submitted = await client.post(f"{REQUESTS}/{started['id']}/submit", headers=ana)
    again = await client.post(f"{REQUESTS}/{started['id']}/cancel", headers=ana)

    assert patched.status_code == 409, patched.text
    assert submitted.status_code == 409, submitted.text
    assert again.status_code == 409, again.text


@pytest.mark.parametrize("who", ["teammate", "mesa", "gestor"])
async def test_only_the_starter_or_the_admin_cancels(db_session, client, rrf_app, who: str) -> None:
    _ana, ana = await member_of(db_session, "kadiweu", "ana@instancia.test")
    if who == "teammate":
        _bia, headers = await member_of(db_session, "kadiweu", "bia@instancia.test")
    else:
        headers = await as_role(db_session, rrf_app, who)
    started = (await start(client, ana)).json()

    res = await client.post(f"{REQUESTS}/{started['id']}/cancel", headers=headers)

    assert res.status_code == 403, res.text


async def test_the_admin_cancels_a_teams_instance(db_session, client, rrf_app) -> None:
    _ana, ana = await member_of(db_session, "kadiweu", "ana@instancia.test")
    _admin, headers = await as_admin(db_session)
    started = (await start(client, ana)).json()

    res = await client.post(f"{REQUESTS}/{started['id']}/cancel", headers=headers)

    assert res.status_code == 200, res.text


async def test_a_submitted_request_is_not_cancelled(db_session, client, rrf_app) -> None:
    _ana, ana = await member_of(db_session, "kadiweu", "ana@instancia.test")
    sent = (await client.post(REQUESTS, json=draft(), headers=ana)).json()
    await client.post(f"{REQUESTS}/{sent['id']}/submit", headers=ana)

    res = await client.post(f"{REQUESTS}/{sent['id']}/cancel", headers=ana)

    assert res.status_code == 409, res.text


# ——— the revision is the project's next instance ———————————————————————————————————


async def test_a_revision_inherits_the_pen_and_obeys_the_lock(db_session, client, rrf_app) -> None:
    ana_user, ana = await member_of(db_session, "kadiweu", "ana@instancia.test")
    _bia, bia = await member_of(db_session, "kadiweu", "bia@instancia.test")
    sent = (await client.post(REQUESTS, json=draft(), headers=ana)).json()
    await client.post(f"{REQUESTS}/{sent['id']}/submit", headers=ana)
    await _decide(db_session, sent["id"], RRDecision.REVISE)

    blocking = (await start(client, bia)).json()
    refused = await client.post(f"{REQUESTS}/{sent['id']}/revise", headers=ana)
    await client.post(f"{REQUESTS}/{blocking['id']}/cancel", headers=bia)
    opened = await client.post(f"{REQUESTS}/{sent['id']}/revise", headers=ana)

    assert refused.status_code == 409, refused.text
    assert opened.status_code == 201, opened.text
    assert opened.json()["started_by"] == ana_user.id
    assert opened.json()["can_edit"] is True


def test_the_migration_writes_the_index_the_model_declares() -> None:
    """Two homes for one rule, the ``test_schema`` precedent: production runs the migration,
    the suite runs ``create_all``, and a condition that drifted between them would lock
    differently in the two places without a test going red."""
    import importlib.util
    from pathlib import Path

    revision = (
        Path(__file__).parents[2] / "alembic" / "versions" / "20260929_rr09_the_team_instance.py"
    )
    spec = importlib.util.spec_from_file_location("_rr09", revision)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    index = next(
        index
        for index in RRRequest.__table__.indexes
        if index.name == "uq_rr_requests_one_open_per_project"
    )
    assert index.unique
    assert [column.name for column in index.columns] == ["shema_project_id"]
    for dialect in ("postgresql", "sqlite"):
        assert str(index.dialect_options[dialect]["where"]) == migration.OPEN
