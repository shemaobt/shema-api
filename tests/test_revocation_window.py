"""ENG-551 — how long an access that was already taken away keeps working.

`auth_cache` holds two answers for every signed-in person: which roles they have, and
whether the account is still active. Both are read once and kept, and while they are kept
nothing asks the database again. That is what makes the two gates in `access_control` cheap,
and it is also what makes a withdrawal take effect late.

The asymmetry is the whole point. Someone who *gains* access and waits is inconvenienced.
Someone who *lost* access and keeps working is the damage — and it is the case that never
ran, because the gate returns before it would have asked. So the cases below take access
away and then knock, rather than granting it and knocking, which would stay green with the
defect standing.

Nothing here sleeps. The caches are rebuilt with a clock the test moves by hand, carrying
the **real** `ttl` and `maxsize` off the live objects, so the only thing the test supplies
is the passage of time. The number of seconds it advances is written out literally: that is
what turns a window that grew back into a red case instead of a silent one.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from cachetools import TTLCache  # type: ignore[import-untyped]
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import auth_cache
from app.core.enums import ProjectRole
from app.db.models.auth import Role, UserAppRole
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

#: Longer than the window this slice sets, and written as a number rather than read off the
#: cache. A test that advanced `ttl + 1` would keep passing at five minutes, which is the one
#: thing these cases exist to catch.
PAST_THE_WINDOW = 31


class Clock:
    """A monotonic reading the test moves, in the shape `cachetools` expects."""

    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture()
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    """Both caches, rebuilt on a hand-moved clock and keeping their real window."""
    moved = Clock()
    for name in ("_roles_cache", "_user_cache"):
        live = getattr(auth_cache, name)
        monkeypatch.setattr(
            auth_cache,
            name,
            TTLCache(maxsize=live.maxsize, ttl=live.ttl, timer=moved),
        )
    return moved


@pytest.fixture()
async def client(test_engine, db_session: AsyncSession):
    """The real application, on a fresh session per request.

    Production hands every request its own session, so what the cache keeps is a snapshot
    detached from any live identity map. Sharing the test's session instead would let a row
    updated here reach into the cached object, and a withdrawal would appear to take effect
    the moment it was written — green, on a gate that never re-read anything.
    """
    from app.core.database import get_db
    from app.main import app

    session_factory = async_sessionmaker(
        test_engine, expire_on_commit=False, class_=AsyncSession, autoflush=False
    )

    async def _get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    """The app and role `20260812_room04` registers. Tests build tables, not migrations."""
    app = await make_app(db_session, app_key=APP_KEY, name="Sala de Internalização")
    await make_role(
        db_session, app.id, role_key=FACILITATOR_ROLE, label="Facilitador", is_system=True
    )
    return app


async def a_facilitator_with_a_team(db: AsyncSession, room, *, email: str, tag: str):
    """Somebody who passes the gate today: the app role, and a team of their own."""
    user = await make_user(db, email=email)
    role = (
        await db.execute(
            select(Role).where(Role.app_id == room.id, Role.role_key == FACILITATOR_ROLE)
        )
    ).scalar_one()
    await make_user_app_role(db, user.id, room.id, role.id)
    language = await make_language(db, name=f"Lang {tag}", code=tag[:3])
    project = await make_project(db, language.id, name=f"Team {tag}")
    await make_project_user_access(db, project.id, user.id, role=ProjectRole.FACILITATOR)
    return user, project


async def auth_header(db: AsyncSession, user) -> dict[str, str]:
    from app.services.auth.issue_tokens import issue_tokens

    access, _refresh = await issue_tokens(db, user)
    return {"Authorization": f"Bearer {access}"}


@pytest.mark.asyncio
async def test_a_role_revoked_elsewhere_stops_opening_the_door_within_the_window(
    client, db_session, room_app, clock
):
    """The Console takes the role away, and the gate is still holding the old answer.

    Revoked straight on the row, without `revoke_role`, because `revoke_role` calls
    `invalidate_roles` and would clear the very entry under test. That is not a contrivance:
    the cache lives inside one process, so a revocation written by the Console, by hand, or
    by another Cloud Run instance reaches this one exactly this way — as a row that changed
    under a gate that is not looking.
    """
    user, team = await a_facilitator_with_a_team(
        db_session, room_app, email="ex-facilitadora@example.com", tag="revogada"
    )
    headers = await auth_header(db_session, user)
    url = f"/api/facilitator/teams/{team.id}/devices"

    assert (await client.get(url, headers=headers)).status_code == 200, (
        "a facilitadora tinha de passar antes da revogacao, senao o caso nao mede nada"
    )

    grant = (
        await db_session.execute(select(UserAppRole).where(UserAppRole.user_id == user.id))
    ).scalar_one()
    grant.revoked_at = datetime.now(UTC)
    await db_session.commit()

    clock.advance(PAST_THE_WINDOW)

    assert (await client.get(url, headers=headers)).status_code == 403, (
        f"um papel revogado ainda abria a porta {PAST_THE_WINDOW}s depois"
    )


@pytest.mark.asyncio
async def test_a_deactivated_account_stops_getting_in_within_the_window(
    client, db_session, room_app, clock
):
    """The strongest withdrawal the Console has, and it was the slowest to land.

    `is_active` is read off the cached `User`, so deactivating an account left it working for
    as long as the entry survived — a longer reach than a revoked role, since it is every
    authenticated route on the platform and not one app's.
    """
    user, team = await a_facilitator_with_a_team(
        db_session, room_app, email="desativada@example.com", tag="desativada"
    )
    headers = await auth_header(db_session, user)
    url = f"/api/facilitator/teams/{team.id}/devices"

    assert (await client.get(url, headers=headers)).status_code == 200, (
        "a conta tinha de passar antes de ser desativada, senao o caso nao mede nada"
    )

    user.is_active = False
    await db_session.commit()

    clock.advance(PAST_THE_WINDOW)

    assert (await client.get(url, headers=headers)).status_code == 403, (
        f"uma conta desativada ainda entrava {PAST_THE_WINDOW}s depois"
    )


def test_both_windows_are_declared_at_thirty_seconds():
    """The number itself, because it is the number that was never decided.

    Five minutes was a default nobody chose; thirty seconds is a measured trade — a ceiling
    of two reads per user per minute, against a withdrawal that lands in half a minute. The
    two caches are asserted together: they are read on the same request, and a window that
    is short on one and long on the other is only as short as the longer one.

    Read off the cache objects rather than off ``AUTH_CACHE_TTL_SECONDS``, and the private
    name is the point rather than a compromise: **the public constant does not prove the
    property**. Asserting a constant against itself passes on the day somebody declares it
    and forgets to wire it — which is the easiest version of this case to write and the one
    that guards least. What has to be true is that the caches *carry* the window, and the
    only place that is observable is the objects doing the carrying.
    """
    assert (auth_cache._roles_cache.ttl, auth_cache._user_cache.ttl) == (30, 30), (
        "a janela dos caches de autenticacao mudou sem passar por aqui"
    )
