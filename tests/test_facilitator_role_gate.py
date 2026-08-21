"""ENG-438 — who is allowed to reach a facilitator route at all.

Two route families answer to the word facilitator and they were open in two different ways.
The Desk's device routes carried no app gate whatsoever, so any authenticated user on the
platform reached the handler. The room's facilitator routes carried `require_app_access`,
which asks whether you hold *a* role on the app and never which one — a team's own role
opened them exactly as a facilitator's did.

The enumeration below reads the mounted application rather than a list written here, because
the failure this slice is guarding against is a route nobody remembered. A hand-kept list
would have been written from the same memory that missed it.

The cases stop at the door. Whether the caller then gets the team or the question they asked
for belongs to the scoping issues, and a case here asserting 200 would be asserting both.
"""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.db.models.auth import Role
from tests.baker import (
    make_app,
    make_language,
    make_project,
    make_project_user_access,
    make_role,
    make_user,
    make_user_app_role,
)

APP_KEY = "internalization-room"
FACILITATOR_ROLE = "facilitator"

#: A request shaped well enough to reach the gate on each route, so that a refusal is the
#: gate's and not the body parser's. A route missing from here cannot be exercised, and the
#: knock treats that as a failure rather than skipping it — see `test_the_audit_covers_...`.
_REQUESTS: dict[tuple[str, str], dict] = {
    ("POST", "/api/facilitator/devices/claim"): {
        "json": {"code": "ABC123", "project_id": "algum-time"}
    },
    ("PATCH", "/api/facilitator/devices/{device_id}"): {"json": {"label": "tablet da sala"}},
    ("DELETE", "/api/facilitator/devices/{device_id}"): {},
    ("GET", "/api/facilitator/teams"): {},
    ("GET", "/api/facilitator/teams/{team_id}/devices"): {},
    ("GET", "/api/facilitator/coverage-legend"): {},
    ("GET", "/api/facilitator/teams/{team_id}/coverage"): {"params": {"pericope": "P01"}},
    ("GET", "/api/facilitator/teams/{team_id}/pericopes"): {},
    ("GET", "/api/internalization-room/facilitator/questions"): {},
    ("GET", "/api/internalization-room/facilitator/questions/{question_id}/audio"): {},
    ("GET", "/api/internalization-room/facilitator/questions/audio/{handle}"): {},
    ("POST", "/api/internalization-room/facilitator/questions/{question_id}/reply"): {
        "files": {"file": ("resposta.m4a", b"resposta falada", "audio/mp4")}
    },
    ("POST", "/api/internalization-room/facilitator/questions/{question_id}/resolve"): {},
    ("GET", "/api/internalization-room/facilitator/sessions/{session_id}/takes"): {},
    ("GET", "/api/internalization-room/facilitator/takes/{take_id}/audio"): {},
}

_PLACEHOLDER = "algum-id"


def facilitator_routes() -> list[tuple[str, str]]:
    """Every mounted route whose path is a facilitator's, as (method, path)."""
    from app.main import app

    found = []
    for route in app.routes:
        path = getattr(route, "path", "")
        if "/facilitator" not in path:
            continue
        for method in sorted(getattr(route, "methods", set()) - {"HEAD", "OPTIONS"}):
            found.append((method, path))
    return sorted(found)


@pytest.fixture()
async def client(db_session: AsyncSession):
    """The real application, so no route can be out of scope by not being mounted here."""
    from app.core.database import get_db
    from app.main import app

    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    """The app and roles `20260812_room04` registers. Tests build tables, not migrations."""
    app = await make_app(db_session, app_key=APP_KEY, name="Sala de Internalização")
    await make_role(
        db_session, app.id, role_key=FACILITATOR_ROLE, label="Facilitador", is_system=True
    )
    await make_role(db_session, app.id, role_key="admin", label="Administrador", is_system=True)
    return app


async def auth_header(db: AsyncSession, user) -> dict[str, str]:
    from app.services.auth.issue_tokens import issue_tokens

    access, _refresh = await issue_tokens(db, user)
    return {"Authorization": f"Bearer {access}"}


async def grant_app_role(db: AsyncSession, app, user, role_key: str, **kw) -> None:
    role = (
        await db.execute(select(Role).where(Role.app_id == app.id, Role.role_key == role_key))
    ).scalar_one()
    await make_user_app_role(db, user.id, app.id, role.id, **kw)


async def with_a_team(db: AsyncSession, user, *, tag: str):
    """Project access as a facilitator — everything except the app role."""
    language = await make_language(db, name=f"Lang {tag}", code=tag[:3])
    project = await make_project(db, language.id, name=f"Team {tag}")
    await make_project_user_access(db, project.id, user.id, role=ProjectRole.FACILITATOR)
    return project


async def knock(client, headers) -> dict[tuple[str, str], int]:
    """Send one request to every facilitator route and collect the statuses."""
    statuses = {}
    for method, path in facilitator_routes():
        assert (method, path) in _REQUESTS, (
            f"a rota {method} {path} nao esta na tabela deste teste, entao o portao nunca "
            "foi exercido nela — acrescente-a em vez de deixa-la de fora"
        )
        url = path
        while "{" in url:
            head, _, rest = url.partition("{")
            _, _, tail = rest.partition("}")
            url = f"{head}{_PLACEHOLDER}{tail}"
        response = await client.request(method, url, headers=headers, **_REQUESTS[(method, path)])
        statuses[(method, path)] = response.status_code
    return statuses


def _refused(statuses: dict[tuple[str, str], int]) -> list[str]:
    return [f"{m} {p} -> {s}" for (m, p), s in statuses.items() if s != 403]


@pytest.mark.asyncio
async def test_another_role_on_the_same_app_is_refused_everywhere(client, db_session, room_app):
    """Holding *a* role is not holding *this* one.

    This is the whole difference between the gate that was on the room's routes and the one
    that belongs there: `require_app_access` never asked which role.
    """
    user = await make_user(db_session, email="admin-da-sala@example.com")
    await grant_app_role(db_session, room_app, user, "admin")
    await with_a_team(db_session, user, tag="outro-papel")

    statuses = await knock(client, await auth_header(db_session, user))

    assert _refused(statuses) == [], "rotas abertas a quem tem outro papel do app"


@pytest.mark.asyncio
async def test_project_access_alone_does_not_open_the_door(client, db_session, room_app):
    """The case that separates this gate from the scoping that already existed.

    `ProjectRole.FACILITATOR` is exactly who passed the device routes before this slice. If
    this stayed green without the app role, the swap would have changed nothing.
    """
    user = await make_user(db_session, email="so-projeto@example.com")
    await with_a_team(db_session, user, tag="sem-papel")

    statuses = await knock(client, await auth_header(db_session, user))

    assert _refused(statuses) == [], "rotas abertas a quem so tem acesso de projeto"


@pytest.mark.asyncio
async def test_no_credential_at_all_is_refused_everywhere(client):
    statuses = await knock(client, {})

    assert [f"{m} {p} -> {s}" for (m, p), s in statuses.items() if s != 401] == []


@pytest.mark.asyncio
async def test_a_revoked_grant_closes_the_door_again(client, db_session, room_app):
    """Taking the role away has to take the access away.

    `user_app_roles` revokes by timestamp instead of deleting the row, so a lookup ignoring
    `revoked_at` would keep a removed facilitator working and leave no trace of it.
    """
    from datetime import UTC, datetime

    user = await make_user(db_session, email="ex-facilitadora@example.com")
    await grant_app_role(db_session, room_app, user, FACILITATOR_ROLE, revoked_at=datetime.now(UTC))
    await with_a_team(db_session, user, tag="revogada")

    statuses = await knock(client, await auth_header(db_session, user))

    assert _refused(statuses) == [], "um papel revogado ainda abre portas"


@pytest.mark.asyncio
async def test_the_role_gets_past_the_gate(client, db_session, room_app):
    """Past the door, not to a 200: what happens next belongs to the scoping issues."""
    user = await make_user(db_session, email="facilitadora@example.com")
    await grant_app_role(db_session, room_app, user, FACILITATOR_ROLE)
    await with_a_team(db_session, user, tag="com-papel")

    statuses = await knock(client, await auth_header(db_session, user))

    assert 403 not in statuses.values(), f"quem tem o papel foi barrado no portao: {statuses}"


@pytest.mark.asyncio
async def test_a_platform_admin_still_passes(client, db_session, room_app):
    """`require_role` curto-circuita em `is_platform_admin`. Afirmado, nao presumido."""
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)

    statuses = await knock(client, await auth_header(db_session, admin))

    assert 403 not in statuses.values(), f"o admin de plataforma foi barrado: {statuses}"


def test_every_facilitator_route_carries_the_role_gate():
    """The guard against the next route, not against the ten that exist today.

    Compared against the dependency object the routes actually use, so it cannot decay into
    asserting a name copied here, and it reads the mounted application, so a facilitator
    route added in a module nobody thought of still has to answer for itself.
    """
    from app.api.facilitator._deps import facilitator_role
    from app.main import app

    gate = facilitator_role.dependency

    def carries(dependant) -> bool:
        return any(sub.call is gate or carries(sub) for sub in dependant.dependencies)

    ungated = [
        f"{sorted(route.methods)} {route.path}"
        for route in app.routes
        if "/facilitator" in getattr(route, "path", "")
        and getattr(route, "methods", None)
        and not carries(route.dependant)
    ]

    assert ungated == [], f"rota de facilitador sem o portao de papel: {ungated}"


def test_the_audit_covers_both_route_families():
    """The knock is only as good as its reach, and both families have to be in it.

    The device routes and the room's routes were open in different ways, and a run that
    happened to exercise one family would have looked just as green.
    """
    families = {path.split("/facilitator")[0] or "/api" for _method, path in facilitator_routes()}

    assert families == {"/api", "/api/internalization-room"}, families
    assert set(facilitator_routes()) <= set(_REQUESTS), (
        f"rotas fora da tabela: {set(facilitator_routes()) - set(_REQUESTS)}"
    )


@pytest.mark.asyncio
async def test_the_gate_does_not_re_read_the_role_tables_on_every_request(
    client, db_session, room_app, test_engine
):
    """What the gate costs, on ten routes, six of them the room's.

    `require_app_access` — the gate this slice replaced — reads a user's roles once and
    keeps them for five minutes. `require_role` asked `has_role`, which is three reads in
    a row: the app, then the role, then the grant. Tightening the door is not a licence to
    make every screen pay three round trips for it, and a facilitator opens screens with a
    team waiting in the room.

    Measured on the second request, so the first is allowed its cold read. What must not
    happen is the third, and the thirtieth.
    """
    from sqlalchemy import event

    user = await make_user(db_session, email="custo@example.com")
    await grant_app_role(db_session, room_app, user, FACILITATOR_ROLE)
    team = await with_a_team(db_session, user, tag="custo")
    headers = await auth_header(db_session, user)
    url = f"/api/facilitator/teams/{team.id}/devices"

    assert (await client.get(url, headers=headers)).status_code == 200

    read: list[str] = []

    @event.listens_for(test_engine.sync_engine, "before_cursor_execute")
    def _record(conn, cursor, statement, parameters, context, executemany):
        read.append(" ".join(statement.split()))

    try:
        assert (await client.get(url, headers=headers)).status_code == 200
    finally:
        event.remove(test_engine.sync_engine, "before_cursor_execute", _record)

    role_tables = [s for s in read if " apps" in s or " roles" in s or "user_app_roles" in s]

    assert role_tables == [], (
        f"o portao releu as tabelas de papel numa requisicao ja autenticada: {role_tables}"
    )
