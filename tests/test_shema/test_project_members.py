"""Project members (OBT-524): who may write a roster, who may read it, and what a member reaches.

The DoD's lines, each held here by the test named for the guarantee it gives:

* one live membership per account and project, as a partial unique index that holds on the suite's
  SQLite and is written for PostgreSQL by the revision; removal marks the row and keeps it;
* only the Admin writes — every other persona is refused, the five the DoD names and more;
* ``GET /me/projects`` answers the caller's live memberships and nothing else, and a member with no
  regional role reaches no other project.

**No account here is an installation admin.** ``is_platform_admin`` passes every guard in this
repository, so a refusal proved with one would pass for the wrong reason. The Admin of OBT-522 is
the ``admin`` role granted in ``shema`` — a different thing, and the one these routes read.

**The member's own record is not asserted either way.** Whether a member opens the ficha of their
own project is OBT-544's to decide; what this issue pins is that they reach no *other* project.
"""

from __future__ import annotations

import importlib.util
import io
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateIndex

from app.db.models.shema_enums import ShemaRegionKey
from app.db.models.shema_project_member import MEMBER_ROLE, ShemaProjectMember
from app.services import authorization_service
from app.services.shema._scope import EQUIPE_ROLE
from tests.baker import make_user
from tests.test_shema.conftest import (
    PREFIX,
    REGIONS,
    SCOPE_PROBE,
    UNGUARDED_PROBE,
    auth_header,
    grant,
    make_scoped_user,
    make_shema_project,
)

AFRICA = ShemaRegionKey.AFRICA
ASIA = ShemaRegionKey.ASIA

ME_PROJECTS = f"{PREFIX}/me/projects"

_REVISION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260927_shema524_project_members.py"
)


def _roster(project_id: str) -> str:
    return f"{PREFIX}/projects/{project_id}/members"


def _member_path(project_id: str, user_id: str) -> str:
    return f"{_roster(project_id)}/{user_id}"


async def _admin(db_session, shema_app, email: str = "the-admin@members.test"):
    """The Admin of OBT-522: ``admin`` granted in ``shema``, no region, no other role."""
    user = await make_user(db_session, email=email, is_platform_admin=False)
    await grant(db_session, user, shema_app, "admin")
    return user


async def _join(db_session, project, user, *, by, removed: bool = False) -> ShemaProjectMember:
    """A membership row written straight to the table — for tests about what reads it."""
    now = datetime.now(UTC)
    row = ShemaProjectMember(
        project_id=project.id,
        user_id=user.id,
        role=MEMBER_ROLE,
        added_by=by.id,
        removed_at=now if removed else None,
        removed_by=by.id if removed else None,
    )
    db_session.add(row)
    await db_session.commit()
    return row


async def _live_rows(db_session, project_id: str, user_id: str) -> list[ShemaProjectMember]:
    stmt = (
        select(ShemaProjectMember)
        .where(
            ShemaProjectMember.project_id == project_id,
            ShemaProjectMember.user_id == user_id,
            ShemaProjectMember.removed_at.is_(None),
        )
        .execution_options(populate_existing=True)
    )
    return list((await db_session.execute(stmt)).scalars())


# --- the table: one live row per pair, and removal keeps the row -----------------------------


async def test_two_live_rows_for_one_pair_are_refused_by_the_database(db_session, shema_app):
    """The partial unique index, on the suite's own SQLite — the guarantee under the service's
    409, for the race and for any writer that does not come through it."""
    admin = await _admin(db_session, shema_app)
    member = await make_user(db_session, email="twice@members.test")
    project = await make_shema_project(db_session, project_id="p-twice", region_key=AFRICA)
    await _join(db_session, project, member, by=admin)

    db_session.add(
        ShemaProjectMember(
            project_id=project.id, user_id=member.id, role=MEMBER_ROLE, added_by=admin.id
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_a_removed_row_and_a_live_row_for_one_pair_coexist(db_session, shema_app):
    """The index is on the **live** rows only, so a stay that ended leaves room for a new one."""
    admin = await _admin(db_session, shema_app)
    member = await make_user(db_session, email="back@members.test")
    project = await make_shema_project(db_session, project_id="p-back", region_key=AFRICA)
    await _join(db_session, project, member, by=admin, removed=True)
    await _join(db_session, project, member, by=admin, removed=True)
    await _join(db_session, project, member, by=admin)

    rows = (
        await db_session.execute(
            select(ShemaProjectMember).where(ShemaProjectMember.project_id == project.id)
        )
    ).scalars()
    assert len(list(rows)) == 3


def test_the_live_index_is_partial_on_both_dialects():
    """The model declares the same index for the dialect production runs and the one the suite
    builds from ``create_all`` — an index declared for one only is a rule nobody can rely on."""
    index = next(
        i for i in ShemaProjectMember.__table__.indexes if i.name == "uq_shema_project_members_live"
    )
    for dialect in (postgresql.dialect(), sqlite.dialect()):
        ddl = str(CreateIndex(index).compile(dialect=dialect))
        assert "CREATE UNIQUE INDEX uq_shema_project_members_live" in ddl
        assert "(project_id, user_id)" in ddl
        assert "WHERE removed_at IS NULL" in ddl


def test_the_migration_writes_the_partial_index_for_postgres():
    """The revision itself, run for PostgreSQL without a database.

    No migration in this repository runs under SQLite (``docs/shema.md`` §7.2) and no Postgres is
    at hand in the suite, so the revision's two callables are imported from the file — as
    ``test_admin_role.py`` does — and driven in Alembic's offline mode for the ``postgresql``
    dialect, which renders the DDL instead of executing it. The CI's migrations job then runs the
    same revision up and down on a real PostgreSQL 17.
    """
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    spec = importlib.util.spec_from_file_location("_shema524", _REVISION)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.down_revision == "20260927_shema08"

    def emitted(step) -> str:
        buffer = io.StringIO()
        context = MigrationContext.configure(
            dialect_name="postgresql", opts={"as_sql": True, "output_buffer": buffer}
        )
        with Operations.context(context):
            step()
        return " ".join(buffer.getvalue().split())

    up = emitted(migration.upgrade)
    assert "CREATE TABLE shema_project_members" in up
    assert (
        "CREATE UNIQUE INDEX uq_shema_project_members_live ON shema_project_members "
        "(project_id, user_id) WHERE removed_at IS NULL" in up
    )
    assert "CHECK (role IN ('equipe'))" in up
    assert "REFERENCES users (id) ON DELETE SET NULL" in up

    down = emitted(migration.downgrade)
    assert "DROP INDEX uq_shema_project_members_live" in down
    assert "DROP TABLE shema_project_members" in down


async def test_the_role_column_takes_equipe_and_refuses_anything_else(db_session, shema_app):
    """The table's word is the session's word — the membership *is* the ``equipe`` the door
    counts — and the CHECK refuses a role nobody has defined yet."""
    assert MEMBER_ROLE == EQUIPE_ROLE

    admin = await _admin(db_session, shema_app)
    member = await make_user(db_session, email="lider@members.test")
    project = await make_shema_project(db_session, project_id="p-role", region_key=AFRICA)

    db_session.add(
        ShemaProjectMember(
            project_id=project.id, user_id=member.id, role="lider", added_by=admin.id
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


def test_the_roster_is_reachable_by_the_project_it_is_read_for():
    """Reading one roster is a read by ``project_id``, and the live index leads on it."""
    index = next(
        i for i in ShemaProjectMember.__table__.indexes if i.name == "uq_shema_project_members_live"
    )
    assert [column.name for column in index.columns] == ["project_id", "user_id"]


async def test_removal_marks_the_row_and_keeps_it(db_session, client, shema_app):
    """``DELETE`` stamps ``removed_at`` and ``removed_by`` and leaves the row: a request a member
    sent stays the project's after they leave. The roster and ``/me/projects`` stop showing it."""
    admin = await _admin(db_session, shema_app)
    member = await make_user(db_session, email="leaving@members.test")
    project = await make_shema_project(db_session, project_id="p-leave", region_key=AFRICA)
    await _join(db_session, project, member, by=admin)
    admin_headers = await auth_header(db_session, admin)

    res = await client.delete(_member_path(project.id, member.id), headers=admin_headers)
    assert res.status_code == 204, res.text

    rows = list(
        (
            await db_session.execute(
                select(ShemaProjectMember)
                .where(ShemaProjectMember.user_id == member.id)
                .execution_options(populate_existing=True)
            )
        ).scalars()
    )
    assert len(rows) == 1
    assert rows[0].removed_at is not None
    assert rows[0].removed_by == admin.id

    assert (await client.get(_roster(project.id), headers=admin_headers)).json() == []


async def test_a_removed_member_can_be_added_again_and_the_history_stays(
    db_session, client, shema_app
):
    admin = await _admin(db_session, shema_app)
    member = await make_user(db_session, email="again@members.test")
    project = await make_shema_project(db_session, project_id="p-again", region_key=AFRICA)
    await _join(db_session, project, member, by=admin, removed=True)

    res = await client.post(
        _roster(project.id),
        headers=await auth_header(db_session, admin),
        json={"userId": member.id},
    )

    assert res.status_code == 201, res.text
    rows = list(
        (
            await db_session.execute(
                select(ShemaProjectMember)
                .where(ShemaProjectMember.user_id == member.id)
                .execution_options(populate_existing=True)
            )
        ).scalars()
    )
    assert sorted(row.removed_at is None for row in rows) == [False, True]


# --- only the Admin writes ---------------------------------------------------------------------


async def _persona(db_session, shema_app, form_app, project, persona: str):
    """One account per refused persona. The coordinator reaches the project's region, so its
    refusal is by role and not by scope."""
    email = f"{persona.lower()}@writers.test"
    if persona in ("coordinator", "obtLab", "resourceCircle"):
        return await make_scoped_user(
            db_session, shema_app, email=email, role_key=persona, regions=[AFRICA]
        )
    user = await make_user(db_session, email=email, is_platform_admin=False)
    if persona in ("mesa", "gestor"):
        await grant(db_session, user, form_app, persona)
    elif persona == "form-admin":
        await grant(db_session, user, form_app, "admin")
    elif persona == "member":
        admin = await _admin(db_session, shema_app, email="adds-the-member@writers.test")
        await _join(db_session, project, user, by=admin)
    return user


@pytest.mark.parametrize(
    "persona",
    [
        "coordinator",
        "obtLab",
        "resourceCircle",
        "mesa",
        "gestor",
        "form-admin",
        "member",
    ],
)
async def test_only_the_admin_writes_the_roster(db_session, client, shema_app, form_app, persona):
    """The DoD's five, and two more that would each be a plausible hole: the ``admin`` granted
    only in the form (the same word in the other app), and a member of the project itself.
    (The Global Strategist, who reached every region, was a third until OBT-572 retired it.)
    ``POST`` and ``DELETE`` are both 403, and the roster is exactly what it was."""
    admin = await _admin(db_session, shema_app)
    project = await make_shema_project(db_session, project_id="p-writers", region_key=AFRICA)
    sitting = await make_user(db_session, email="sitting@writers.test")
    await _join(db_session, project, sitting, by=admin)
    outsider = await make_user(db_session, email="outsider@writers.test")

    caller = await _persona(db_session, shema_app, form_app, project, persona)
    headers = await auth_header(db_session, caller)

    added = await client.post(_roster(project.id), headers=headers, json={"userId": outsider.id})
    assert added.status_code == 403, added.text
    removed = await client.delete(_member_path(project.id, sitting.id), headers=headers)
    assert removed.status_code == 403, removed.text

    assert await _live_rows(db_session, project.id, outsider.id) == []
    assert len(await _live_rows(db_session, project.id, sitting.id)) == 1


async def test_the_admin_adds_a_member_and_the_roster_reads_it(db_session, client, shema_app):
    admin = await _admin(db_session, shema_app)
    member = await make_user(db_session, email="joins@members.test", display_name="Ana Teste")
    project = await make_shema_project(db_session, project_id="p-add", region_key=AFRICA)
    headers = await auth_header(db_session, admin)

    res = await client.post(_roster(project.id), headers=headers, json={"userId": member.id})

    assert res.status_code == 201, res.text
    today = datetime.now(UTC).date().isoformat()
    expected = {"userId": member.id, "name": "Ana Teste", "role": "equipe", "addedAt": today}
    assert res.json() == expected
    assert (await client.get(_roster(project.id), headers=headers)).json() == [expected]

    row = (await _live_rows(db_session, project.id, member.id))[0]
    assert row.added_by == admin.id


async def test_a_member_with_no_display_name_is_named_by_their_address(
    db_session, client, shema_app
):
    """``author_name``'s rule: the display name is nullable and often is, and the address is the
    one identifier every account has."""
    admin = await _admin(db_session, shema_app)
    member = await make_user(db_session, email="noname@members.test", display_name=None)
    project = await make_shema_project(db_session, project_id="p-noname", region_key=AFRICA)
    await _join(db_session, project, member, by=admin)

    res = await client.get(_roster(project.id), headers=await auth_header(db_session, admin))

    assert [entry["name"] for entry in res.json()] == ["noname@members.test"]


async def test_the_roster_lists_members_in_the_order_they_joined(db_session, client, shema_app):
    admin = await _admin(db_session, shema_app)
    project = await make_shema_project(db_session, project_id="p-order", region_key=AFRICA)
    first = await make_user(db_session, email="zz-first@members.test", display_name="Zé")
    second = await make_user(db_session, email="aa-second@members.test", display_name="Ana")
    await _join(db_session, project, first, by=admin)
    await _join(db_session, project, second, by=admin)

    res = await client.get(_roster(project.id), headers=await auth_header(db_session, admin))

    assert [entry["userId"] for entry in res.json()] == [first.id, second.id]


async def test_the_admin_reaches_every_roster_and_no_record(db_session, client, shema_app):
    """The Admin holds no region (OBT-523) and still writes the roster of a project in any region
    — and that reach stays on the rosters: the collection is empty for it and a record is the
    same 404 as for anybody out of scope. This is the negative that keeps ``RosterReach`` off
    every other read."""
    admin = await _admin(db_session, shema_app)
    member = await make_user(db_session, email="far@members.test")
    project = await make_shema_project(db_session, project_id="p-far", region_key=ASIA)
    headers = await auth_header(db_session, admin)

    added = await client.post(_roster(project.id), headers=headers, json={"userId": member.id})
    assert added.status_code == 201, added.text

    assert (await client.get(f"{PREFIX}/projects", headers=headers)).json()["items"] == []
    assert (await client.get(f"{PREFIX}/projects/{project.id}", headers=headers)).status_code == 404


async def test_adding_a_live_member_twice_is_a_conflict(db_session, client, shema_app):
    admin = await _admin(db_session, shema_app)
    member = await make_user(db_session, email="dup@members.test")
    project = await make_shema_project(db_session, project_id="p-dup", region_key=AFRICA)
    headers = await auth_header(db_session, admin)

    first = await client.post(_roster(project.id), headers=headers, json={"userId": member.id})
    second = await client.post(_roster(project.id), headers=headers, json={"userId": member.id})

    assert first.status_code == 201
    assert second.status_code == 409
    assert "already a member" in second.json()["detail"]
    assert len(await _live_rows(db_session, project.id, member.id)) == 1


async def test_adding_an_unknown_account_is_refused(db_session, client, shema_app):
    """A 422 naming the reference rather than a 500 out of the foreign key."""
    admin = await _admin(db_session, shema_app)
    project = await make_shema_project(db_session, project_id="p-ghost", region_key=AFRICA)

    res = await client.post(
        _roster(project.id),
        headers=await auth_header(db_session, admin),
        json={"userId": "00000000-0000-0000-0000-000000000000"},
    )

    assert res.status_code == 422
    assert res.json()["code"] == "UNKNOWN_REFERENCE"


async def test_adding_to_an_unknown_project_is_a_404(db_session, client, shema_app):
    admin = await _admin(db_session, shema_app)
    member = await make_user(db_session, email="nowhere@members.test")

    res = await client.post(
        _roster("no-such-project"),
        headers=await auth_header(db_session, admin),
        json={"userId": member.id},
    )

    assert res.status_code == 404


async def test_the_body_carries_only_the_account(db_session, client, shema_app):
    """The role is the server's to stamp: a body naming one is refused, not quietly ignored."""
    admin = await _admin(db_session, shema_app)
    member = await make_user(db_session, email="body@members.test")
    project = await make_shema_project(db_session, project_id="p-body", region_key=AFRICA)

    res = await client.post(
        _roster(project.id),
        headers=await auth_header(db_session, admin),
        json={"userId": member.id, "role": "lider"},
    )

    assert res.status_code == 422
    assert await _live_rows(db_session, project.id, member.id) == []


async def test_removing_someone_who_is_not_a_live_member_is_a_404(db_session, client, shema_app):
    admin = await _admin(db_session, shema_app)
    member = await make_user(db_session, email="gone@members.test")
    project = await make_shema_project(db_session, project_id="p-gone", region_key=AFRICA)
    await _join(db_session, project, member, by=admin, removed=True)

    res = await client.delete(
        _member_path(project.id, member.id), headers=await auth_header(db_session, admin)
    )

    assert res.status_code == 404


# --- who reads: scope, the member, the Admin — and nobody else -------------------------------


async def test_a_regional_reader_reads_the_roster_in_their_region(db_session, client, shema_app):
    admin = await _admin(db_session, shema_app)
    project = await make_shema_project(db_session, project_id="p-region", region_key=AFRICA)
    member = await make_user(db_session, email="in-region@members.test")
    await _join(db_session, project, member, by=admin)

    for role in ("coordinator", "obtLab", "resourceCircle"):
        reader = await make_scoped_user(
            db_session,
            shema_app,
            email=f"reader-{role.lower()}@members.test",
            role_key=role,
            regions=[AFRICA],
        )
        res = await client.get(_roster(project.id), headers=await auth_header(db_session, reader))
        assert res.status_code == 200, role
        assert [entry["userId"] for entry in res.json()] == [member.id]


async def test_a_reader_from_another_region_gets_the_same_404_as_a_missing_project(
    db_session, client, shema_app
):
    """``docs/shema.md`` §6.1: a 403 on a direct id would be the existence of the project told by
    status code. Same status, same sentence."""
    await make_shema_project(db_session, project_id="p-asia", region_key=ASIA)
    reader = await make_scoped_user(
        db_session,
        shema_app,
        email="africa-only@members.test",
        role_key="coordinator",
        regions=[AFRICA],
    )
    headers = await auth_header(db_session, reader)

    out_of_scope = await client.get(_roster("p-asia"), headers=headers)
    missing = await client.get(_roster("no-such-project"), headers=headers)

    assert out_of_scope.status_code == missing.status_code == 404
    assert out_of_scope.json() == missing.json()


async def test_a_member_reads_the_roster_of_their_own_project(db_session, client, shema_app):
    """A member holding no role anywhere: the door admits them as ``equipe`` and the roster of
    their own project answers, teammates included."""
    admin = await _admin(db_session, shema_app)
    project = await make_shema_project(db_session, project_id="p-own", region_key=ASIA)
    member = await make_user(db_session, email="me@members.test")
    teammate = await make_user(db_session, email="mate@members.test")
    await _join(db_session, project, member, by=admin)
    await _join(db_session, project, teammate, by=admin)

    res = await client.get(_roster(project.id), headers=await auth_header(db_session, member))

    assert res.status_code == 200, res.text
    assert {entry["userId"] for entry in res.json()} == {member.id, teammate.id}


async def test_a_removed_member_no_longer_reads_the_roster(db_session, client, shema_app):
    admin = await _admin(db_session, shema_app)
    project = await make_shema_project(db_session, project_id="p-left", region_key=ASIA)
    left = await make_user(db_session, email="left@members.test")
    await grant(db_session, left, shema_app, "resourceCircle")
    await _join(db_session, project, left, by=admin, removed=True)

    res = await client.get(_roster(project.id), headers=await auth_header(db_session, left))

    assert res.status_code == 404


async def test_a_form_seat_alone_reads_no_roster(db_session, client, shema_app, form_app):
    """The mesa passes the door and is answered nothing of anybody's: no projects of its own, and
    a roster it neither reaches nor belongs to is the same 404."""
    admin = await _admin(db_session, shema_app)
    project = await make_shema_project(db_session, project_id="p-mesa", region_key=AFRICA)
    await _join(db_session, project, await make_user(db_session, email="x@m.test"), by=admin)
    mesa = await make_user(db_session, email="mesa@members.test")
    await grant(db_session, mesa, form_app, "mesa")
    headers = await auth_header(db_session, mesa)

    assert (await client.get(ME_PROJECTS, headers=headers)).json() == []
    assert (await client.get(_roster(project.id), headers=headers)).status_code == 404


async def test_the_roster_read_reads_the_grants_once(db_session, client, shema_app, monkeypatch):
    """The door and the roster reach share one ``SessionRoles``, solved once by FastAPI — the
    reach and the admission cannot disagree about who is asking."""
    admin = await _admin(db_session, shema_app)
    project = await make_shema_project(db_session, project_id="p-once", region_key=AFRICA)
    member = await make_user(db_session, email="once@members.test")
    await _join(db_session, project, member, by=admin)
    headers = await auth_header(db_session, member)
    real = authorization_service.list_roles
    calls: list[str | None] = []

    async def counting(db, user_id, app_key=None):
        calls.append(app_key)
        return await real(db, user_id, app_key)

    monkeypatch.setattr(authorization_service, "list_roles", counting)

    assert (await client.get(_roster(project.id), headers=headers)).status_code == 200
    assert calls == [None]


# --- /me/projects, and what a member reaches -------------------------------------------------


async def test_my_projects_are_my_live_memberships_and_nothing_else(db_session, client, shema_app):
    """The DoD's third line: a live membership is listed; a stay that ended, somebody else's
    membership and a project with no link at all are not."""
    admin = await _admin(db_session, shema_app)
    me = await make_user(db_session, email="me-projects@members.test")
    other = await make_user(db_session, email="other@members.test")
    live = await make_shema_project(
        db_session, project_id="p-live", region_key=AFRICA, language_name="Língua Viva"
    )
    ended = await make_shema_project(db_session, project_id="p-ended", region_key=AFRICA)
    theirs = await make_shema_project(db_session, project_id="p-theirs", region_key=AFRICA)
    await make_shema_project(db_session, project_id="p-unlinked", region_key=AFRICA)
    await _join(db_session, live, me, by=admin)
    await _join(db_session, ended, me, by=admin, removed=True)
    await _join(db_session, theirs, other, by=admin)

    res = await client.get(ME_PROJECTS, headers=await auth_header(db_session, me))

    assert res.status_code == 200, res.text
    assert res.json() == [{"id": "p-live", "languageName": "Língua Viva"}]


async def test_my_projects_lists_a_project_once_after_leaving_and_coming_back(
    db_session, client, shema_app
):
    admin = await _admin(db_session, shema_app)
    me = await make_user(db_session, email="returning@members.test")
    project = await make_shema_project(db_session, project_id="p-return", region_key=AFRICA)
    await _join(db_session, project, me, by=admin, removed=True)
    await _join(db_session, project, me, by=admin)

    res = await client.get(ME_PROJECTS, headers=await auth_header(db_session, me))

    assert [ref["id"] for ref in res.json()] == ["p-return"]


async def test_a_member_with_no_regional_role_reaches_no_other_project(
    db_session, client, shema_app
):
    """**The DoD's own test.** An account whose only link to the PME is one membership: it lists
    that project, reads that project's roster, and reaches nothing else — another project's
    roster is the 404 of a project that does not exist, another project's record and the
    collection are refused at the app gate, and so is everything else behind it."""
    admin = await _admin(db_session, shema_app)
    mine = await make_shema_project(db_session, project_id="p-mine", region_key=AFRICA)
    other = await make_shema_project(db_session, project_id="p-other", region_key=AFRICA)
    await _join(db_session, other, await make_user(db_session, email="o@m.test"), by=admin)
    member = await make_user(db_session, email="only-member@members.test")
    await _join(db_session, mine, member, by=admin)
    headers = await auth_header(db_session, member)

    assert [ref["id"] for ref in (await client.get(ME_PROJECTS, headers=headers)).json()] == [
        "p-mine"
    ]
    assert (await client.get(_roster(mine.id), headers=headers)).status_code == 200
    assert (await client.get(_roster(other.id), headers=headers)).status_code == 404
    assert (await client.get(f"{PREFIX}/projects/{other.id}", headers=headers)).status_code == 403
    for path in (UNGUARDED_PROBE, SCOPE_PROBE, f"{PREFIX}/projects", REGIONS):
        assert (await client.get(path, headers=headers)).status_code == 403, path


async def test_a_membership_does_not_open_the_rest_of_its_region(db_session, client, shema_app):
    """A membership is not a region. A Resource Circle of Africa who is on one Asian team still
    reaches no other Asian project: not in the collection, not by id, not by roster."""
    admin = await _admin(db_session, shema_app)
    joined = await make_shema_project(db_session, project_id="asia-1", region_key=ASIA)
    await make_shema_project(db_session, project_id="asia-2", region_key=ASIA)
    await make_shema_project(db_session, project_id="africa-1", region_key=AFRICA)
    member = await make_scoped_user(
        db_session,
        shema_app,
        email="circle@members.test",
        role_key="resourceCircle",
        regions=[AFRICA],
    )
    await _join(db_session, joined, member, by=admin)
    headers = await auth_header(db_session, member)

    ids = [
        item["id"]
        for item in (await client.get(f"{PREFIX}/projects", headers=headers)).json()["items"]
    ]
    assert "africa-1" in ids and "asia-2" not in ids
    assert (await client.get(f"{PREFIX}/projects/asia-2", headers=headers)).status_code == 404
    assert (await client.get(_roster("asia-2"), headers=headers)).status_code == 404
    assert [ref["id"] for ref in (await client.get(ME_PROJECTS, headers=headers)).json()] == [
        "asia-1"
    ]
