"""BE-21 (OBT-527) — the handoff code, held to each line of its Definition of Done.

A person signed in to one app asks for a code; another app trades it for a session of the
same person. Each test below is one promise, grouped by the DoD line it proves, with fixtures
chosen so the wrong implementation answers differently: a role the cache still remembers
after the database revoked it, a context whose ``1`` and ``1.0`` a lax comparison would call
equal, a different code on every rate-limited attempt so a bucket keyed on the code cannot
pass for one keyed on the address.

**No negative case uses a platform admin.** ``create_handoff`` admits one without a grant,
as ``require_app_access`` does, so a refusal proved with an admin account would prove nothing.

**Rows changed mid-test are changed through the ORM object on the shared session.** The app
under test and the test share one session that does not expire on commit, so a row aged with
raw SQL would be read back stale by the exchange and the test would pass for the wrong reason.

The addresses are RFC 5737 documentation addresses, not anybody's.
"""

from __future__ import annotations

import ast
import json
import re
import secrets
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from importlib import import_module
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.resource_requests._deps import APP_KEY as FORM_APP_KEY
from app.core.auth_cache import _roles_cache, _user_cache, set_cached_roles, set_cached_user
from app.core.config import get_settings
from app.core.database import Base
from app.core.rate_limit import limiter
from app.db.models.auth import App, AuthHandoffCode, RefreshToken, User, UserAppRole
from app.services.auth import (
    HandoffRefused,
    create_handoff,
    exchange_handoff,
    issue_tokens,
    revoke_refresh_token,
)
from app.services.common import tokens
from app.utils.jwt import decode_token
from tests.baker import grant_app_role, make_app, make_user
from tests.test_resource_requests.conftest import make_membership

#: The package ``__init__`` rebinds this name to the function, so the module itself is
#: reached through the import machinery.
exchange_module = import_module("app.services.auth.exchange_handoff")

HANDOFF = "/api/auth/handoff"
EXCHANGE = "/api/auth/handoff/exchange"
APP_KEY = "handoff-target"
HERE = "192.0.2.10"
ELSEWHERE = "198.51.100.20"
NOW = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
REVISION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260927_acc21_auth_handoff_codes.py"
)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """slowapi counts in a process-global store, so one test's calls are another's budget."""
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture(autouse=True)
def _clear_auth_caches():
    """Both caches are process-global; a test that plants a stale entry must not leak it."""
    _roles_cache.clear()
    _user_cache.clear()
    yield
    _roles_cache.clear()
    _user_cache.clear()


@pytest.fixture()
def client_from(db_session: AsyncSession) -> Callable[[str], object]:
    """An ASGI client for the real auth router, seen as coming from ``address``."""
    from fastapi import FastAPI
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded

    from app.api.auth import router as auth_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    test_app = FastAPI()
    test_app.state.limiter = limiter
    test_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    test_app.include_router(auth_router, prefix="/api/auth")
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db

    @asynccontextmanager
    async def _client(address: str) -> AsyncIterator[httpx.AsyncClient]:
        transport = ASGITransport(app=test_app, client=(address, 50000))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    return _client


@pytest.fixture()
async def client(client_from) -> AsyncIterator[httpx.AsyncClient]:
    async with client_from(HERE) as c:
        yield c


@pytest.fixture()
async def target(db_session: AsyncSession) -> App:
    return await make_app(db_session, app_key=APP_KEY, name="Handoff target")


async def a_session(db: AsyncSession, user: User) -> tuple[dict[str, str], str]:
    """A real bearer header for ``user`` and the refresh token of the same session."""
    access, refresh = await issue_tokens(db, user)
    return {"Authorization": f"Bearer {access}"}, refresh


async def a_member(db: AsyncSession, app: App, *, email: str = "member@example.com"):
    """A user holding a live role in ``app``, and a session of theirs."""
    user = await make_user(db, email=email)
    await grant_app_role(db, user, app, role_key="member")
    headers, refresh = await a_session(db, user)
    return user, headers, refresh


def a_body(refresh: str, *, app_key: str = APP_KEY, context: object = None) -> dict:
    body: dict[str, object] = {"app_key": app_key, "refresh_token": refresh}
    if context is not None:
        body["context"] = context
    return body


async def codes_in(db: AsyncSession) -> list[AuthHandoffCode]:
    """Every code row as the database holds it now, not as the identity map remembers it."""
    stmt = select(AuthHandoffCode).execution_options(populate_existing=True)
    return list((await db.execute(stmt)).scalars())


async def refresh_rows(db: AsyncSession) -> int:
    return (await db.execute(select(func.count()).select_from(RefreshToken))).scalar_one()


async def a_code(client: httpx.AsyncClient, headers: dict[str, str], refresh: str, **kw) -> str:
    response = await client.post(HANDOFF, json=a_body(refresh, **kw), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["code"]


# --- DoD 1: only with a session, only for an app the user can reach -----------------------


@pytest.mark.parametrize(
    "case",
    [
        "no-bearer",
        "garbage-bearer",
        "refresh-as-bearer",
        "logged-out-refresh",
        "another-users-refresh",
        "access-as-refresh",
    ],
)
async def test_a_handoff_without_a_live_session_is_refused_and_mints_nothing(
    client, db_session, target, case
) -> None:
    """The logged-out case is the one the bearer alone cannot see: its access token is still
    inside its thirty minutes, and it is the refresh row that says the session ended."""
    _user, headers, refresh = await a_member(db_session, target)
    if case == "no-bearer":
        headers = {}
    elif case == "garbage-bearer":
        headers = {"Authorization": "Bearer not-a-token"}
    elif case == "refresh-as-bearer":
        headers = {"Authorization": f"Bearer {refresh}"}
    elif case == "logged-out-refresh":
        await revoke_refresh_token(db_session, refresh)
    elif case == "another-users-refresh":
        other = await make_user(db_session, email="other@example.com")
        _, refresh = await a_session(db_session, other)
    elif case == "access-as-refresh":
        refresh = headers["Authorization"].removeprefix("Bearer ")

    response = await client.post(HANDOFF, json=a_body(refresh), headers=headers)

    assert response.status_code == 401, response.text
    assert await codes_in(db_session) == []


async def test_a_handoff_to_an_app_the_user_holds_no_role_in_is_refused_before_a_code_exists(
    client, db_session, target
) -> None:
    elsewhere = await make_app(db_session, app_key="another-app", name="Another app")
    _user, headers, refresh = await a_member(db_session, elsewhere)

    response = await client.post(HANDOFF, json=a_body(refresh), headers=headers)

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
    assert await codes_in(db_session) == []


async def test_a_revoked_grant_does_not_open_a_handoff(client, db_session, target) -> None:
    user, headers, refresh = await a_member(db_session, target)
    grant = (
        await db_session.execute(select(UserAppRole).where(UserAppRole.user_id == user.id))
    ).scalar_one()
    grant.revoked_at = datetime.now(UTC)
    await db_session.commit()

    response = await client.post(HANDOFF, json=a_body(refresh), headers=headers)

    assert response.status_code == 403
    assert await codes_in(db_session) == []


@pytest.mark.parametrize("case", ["revoked-role-still-cached", "demoted-admin-still-cached"])
async def test_a_stale_cache_does_not_open_a_handoff(client, db_session, target, case) -> None:
    """The two 30-second caches the request gates read are right for *may this account use
    the app* and wrong for minting a credential. Each case plants an entry the database has
    already contradicted; an implementation that reads the cache mints a code here."""
    if case == "revoked-role-still-cached":
        user, headers, refresh = await a_member(db_session, target)
        grant = (
            await db_session.execute(select(UserAppRole).where(UserAppRole.user_id == user.id))
        ).scalar_one()
        grant.revoked_at = datetime.now(UTC)
        await db_session.commit()
        set_cached_roles(user.id, APP_KEY, [(APP_KEY, "member")])
    else:
        user = await make_user(db_session, email="demoted@example.com")
        headers, refresh = await a_session(db_session, user)
        set_cached_user(
            user.id,
            User(
                id=user.id,
                email=user.email,
                password_hash=user.password_hash,
                is_active=True,
                is_platform_admin=True,
            ),
        )

    response = await client.post(HANDOFF, json=a_body(refresh), headers=headers)

    assert response.status_code == 403
    assert await codes_in(db_session) == []


async def test_a_handoff_to_an_app_that_does_not_exist_is_an_unknown_reference(
    client, db_session, target
) -> None:
    _user, headers, refresh = await a_member(db_session, target)

    response = await client.post(
        HANDOFF, json=a_body(refresh, app_key="no-such-app"), headers=headers
    )

    assert response.status_code == 422
    assert response.json()["code"] == "UNKNOWN_REFERENCE"
    assert await codes_in(db_session) == []


async def test_a_platform_admin_is_handed_off_as_require_app_access_admits_them(
    client, db_session, target
) -> None:
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    headers, refresh = await a_session(db_session, admin)

    response = await client.post(HANDOFF, json=a_body(refresh), headers=headers)

    assert response.status_code == 201


# --- the form's door is wider than a grant (BE-19, OBT-520) ---------------------------------


@pytest.fixture()
async def form(db_session: AsyncSession) -> App:
    return await make_app(db_session, app_key=FORM_APP_KEY, name="Resource Request Form")


async def a_project_member(db: AsyncSession, *, email: str = "team@example.com"):
    """A live member of a PME project holding no grant anywhere — the team since GATE-04."""
    user = await make_user(db, email=email)
    membership = await make_membership(db, user, "projeto-da-equipe")
    headers, refresh = await a_session(db, user)
    return membership, headers, refresh


async def test_a_project_member_with_no_grant_is_handed_a_code_for_the_form(
    client, db_session, form
) -> None:
    """The PME → form flow (OBT-538, OBT-544): the form's door admits a live member of a
    project, so the code that opens it has to be minted for one — or the flow never starts."""
    membership, headers, refresh = await a_project_member(db_session)

    response = await client.post(
        HANDOFF,
        json=a_body(refresh, app_key=FORM_APP_KEY, context={"projectId": membership.project_id}),
        headers=headers,
    )

    assert response.status_code == 201, response.text
    [row] = await codes_in(db_session)
    assert (row.user_id, row.app_id) == (membership.user_id, form.id)


@pytest.mark.parametrize("case", ["never-a-member", "membership-removed"])
async def test_an_account_with_no_grant_and_no_live_membership_is_refused_the_form(
    client, db_session, form, case
) -> None:
    if case == "never-a-member":
        user = await make_user(db_session, email="outsider@example.com")
        headers, refresh = await a_session(db_session, user)
    else:
        membership, headers, refresh = await a_project_member(db_session)
        membership.removed_at = datetime.now(UTC)
        await db_session.commit()

    response = await client.post(
        HANDOFF, json=a_body(refresh, app_key=FORM_APP_KEY), headers=headers
    )

    assert response.status_code == 403
    assert await codes_in(db_session) == []


async def test_a_project_membership_opens_no_app_but_the_form(
    client, db_session, form, target
) -> None:
    """Membership holds the form's ``equipe`` and nothing else: every other app still asks
    for a grant of its own."""
    _membership, headers, refresh = await a_project_member(db_session)

    response = await client.post(HANDOFF, json=a_body(refresh), headers=headers)

    assert response.status_code == 403
    assert await codes_in(db_session) == []


def test_the_form_the_handoff_widens_is_the_form_module_s_own_key() -> None:
    """The key is written again in ``create_handoff.py`` because a service may not import a
    router; this keeps that copy from drifting from ``_deps.APP_KEY`` in silence."""
    assert import_module("app.services.auth.create_handoff").FORM_APP_KEY == FORM_APP_KEY


async def test_a_member_is_handed_a_code_for_the_app_it_asked_for(
    client, db_session, target
) -> None:
    user, headers, refresh = await a_member(db_session, target)

    response = await client.post(
        HANDOFF, json=a_body(refresh, context={"projectId": "p-1"}), headers=headers
    )

    assert response.status_code == 201
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", response.json()["code"])
    [row] = await codes_in(db_session)
    assert (row.user_id, row.app_id, row.created_ip) == (user.id, target.id, HERE)
    assert row.context == {"projectId": "p-1"}
    assert row.used_at is None


@pytest.mark.parametrize(
    ("address", "stored"),
    [
        (HERE, HERE),
        ("fe80::1%" + "z" * 80, "fe80::1"),
        ("not-an-address", None),
    ],
    ids=["plain", "scoped-ipv6-with-long-zone", "not-an-address"],
)
async def test_the_stored_client_address_is_an_ip_or_nothing(
    client_from, db_session, target, address, stored
) -> None:
    """Behind a proxy that trusts every ``X-Forwarded-For`` the host is whatever the caller
    wrote. SQLite does not enforce ``String(45)`` and Postgres does, with a 500."""
    _user, headers, refresh = await a_member(db_session, target)

    async with client_from(address) as c:
        await a_code(c, headers, refresh)

    [row] = await codes_in(db_session)
    assert row.created_ip == stored
    assert row.created_ip is None or len(row.created_ip) <= 45


# --- DoD 2: single use, sixty seconds, stored as a digest; replay and expiry refused ------


async def test_the_code_lives_as_long_as_the_configuration_says(
    db_session, target, monkeypatch
) -> None:
    """Five seconds rather than the default, so a sixty written into the service fails."""
    assert get_settings().auth_handoff_code_expire_seconds == 60
    user, _headers, refresh = await a_member(db_session, target)
    monkeypatch.setattr(get_settings(), "auth_handoff_code_expire_seconds", 5)

    minted = await create_handoff(
        db_session,
        user,
        app_key=APP_KEY,
        refresh_token=refresh,
        context=None,
        created_ip=None,
        now=NOW,
    )

    assert minted.expires_at == NOW + timedelta(seconds=5)
    [row] = await codes_in(db_session)
    assert row.expires_at == NOW + timedelta(seconds=5)


async def test_the_table_keeps_the_digest_and_never_the_code(client, db_session, target) -> None:
    _user, headers, refresh = await a_member(db_session, target)
    code = await a_code(client, headers, refresh, context={"projectId": "p-1"})

    for moment in ("minted", "spent"):
        if moment == "spent":
            assert (await client.post(EXCHANGE, json={"code": code})).status_code == 200
        [row] = await codes_in(db_session)
        assert row.code_hash == tokens.digest(code)
        stored = [str(getattr(row, column.key)) for column in AuthHandoffCode.__table__.columns]
        assert not [value for value in stored if code in value], moment


async def test_a_second_exchange_of_one_code_is_refused_as_used_and_issues_nothing(
    client, db_session, target
) -> None:
    _user, headers, refresh = await a_member(db_session, target)
    code = await a_code(client, headers, refresh)

    first = await client.post(EXCHANGE, json={"code": code})
    issued = await refresh_rows(db_session)
    second = await client.post(EXCHANGE, json={"code": code})

    assert first.status_code == 200
    assert second.status_code == 401
    assert second.json() == {
        "detail": "This handoff code has already been used.",
        "code": "HANDOFF_CODE_USED",
    }
    assert await refresh_rows(db_session) == issued


async def test_an_exchange_once_the_clock_ran_out_is_refused_as_expired_and_spends_nothing(
    client, db_session, target
) -> None:
    user, headers, refresh = await a_member(db_session, target)
    minted = await create_handoff(
        db_session,
        user,
        app_key=APP_KEY,
        refresh_token=refresh,
        context=None,
        created_ip=None,
        now=NOW,
    )
    with pytest.raises(HandoffRefused) as refused:
        await exchange_handoff(db_session, minted.code, now=minted.expires_at)
    assert refused.value.reason == "expired"

    code = await a_code(client, headers, refresh)
    row = next(r for r in await codes_in(db_session) if r.code_hash == tokens.digest(code))
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.commit()
    issued = await refresh_rows(db_session)

    response = await client.post(EXCHANGE, json={"code": code})

    assert response.status_code == 401
    assert response.json()["code"] == "HANDOFF_CODE_EXPIRED"
    assert all(r.used_at is None for r in await codes_in(db_session))
    assert await refresh_rows(db_session) == issued


async def test_the_code_still_opens_at_the_last_instant_before_its_expiry(
    db_session, target
) -> None:
    user, _headers, refresh = await a_member(db_session, target)
    minted = await create_handoff(
        db_session,
        user,
        app_key=APP_KEY,
        refresh_token=refresh,
        context=None,
        created_ip=None,
        now=NOW,
    )

    exchanged = await exchange_handoff(
        db_session, minted.code, now=minted.expires_at - timedelta(microseconds=1)
    )

    assert exchanged.user.id == user.id


async def test_a_spent_code_presented_after_its_clock_ran_out_reads_as_expired(
    db_session, target
) -> None:
    """The module's order — expired before used — is inherited, not chosen here, and the
    receiving app words its message knowing it (OBT-538)."""
    user, _headers, refresh = await a_member(db_session, target)
    minted = await create_handoff(
        db_session,
        user,
        app_key=APP_KEY,
        refresh_token=refresh,
        context=None,
        created_ip=None,
        now=NOW,
    )
    await exchange_handoff(db_session, minted.code, now=NOW + timedelta(seconds=1))

    with pytest.raises(HandoffRefused) as within:
        await exchange_handoff(db_session, minted.code, now=NOW + timedelta(seconds=2))
    with pytest.raises(HandoffRefused) as after:
        await exchange_handoff(db_session, minted.code, now=NOW + timedelta(seconds=61))

    assert (within.value.reason, after.value.reason) == ("used", "expired")


async def test_a_code_this_server_never_issued_is_refused_as_unknown(client) -> None:
    response = await client.post(EXCHANGE, json={"code": secrets.token_urlsafe(32)})

    assert response.status_code == 401
    assert response.json() == {
        "detail": "This handoff code is not valid.",
        "code": "HANDOFF_CODE_UNKNOWN",
    }


async def test_a_code_spent_between_the_check_and_the_write_is_refused_and_issues_nothing(
    db_session, target, monkeypatch
) -> None:
    """The race the sequential replay cannot reach: two exchanges both read the code as
    pending. The interleaving is forced rather than raced — a competing exchange runs from
    inside the step between the state read and the write — so the test is deterministic, and
    only the ``used_at IS NULL`` on the write stops the second payment."""
    user, _headers, refresh = await a_member(db_session, target)
    minted = await create_handoff(
        db_session, user, app_key=APP_KEY, refresh_token=refresh, context=None, created_ip=None
    )
    real_get_user_by_id = exchange_module.get_user_by_id

    async def spend_it_first(db, user_id):
        monkeypatch.undo()
        await exchange_handoff(db, minted.code)
        return await real_get_user_by_id(db, user_id)

    monkeypatch.setattr(exchange_module, "get_user_by_id", spend_it_first)
    before = await refresh_rows(db_session)

    with pytest.raises(HandoffRefused) as refused:
        await exchange_handoff(db_session, minted.code)

    assert refused.value.reason == "used"
    assert await refresh_rows(db_session) == before + 1


# --- DoD 3: a session of the same user, and the context untouched --------------------------


async def test_the_exchange_answers_with_a_session_of_the_user_who_asked(
    client, db_session, target
) -> None:
    user, headers, refresh = await a_member(db_session, target)
    code = await a_code(client, headers, refresh)

    body = (await client.post(EXCHANGE, json={"code": code})).json()

    assert body["user"]["id"] == user.id
    access = decode_token(body["tokens"]["access_token"])
    assert (access["sub"], access["type"]) == (user.id, "access")
    me = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {body['tokens']['access_token']}"}
    )
    assert me.json()["id"] == user.id
    renewed = await client.post(
        "/api/auth/refresh", json={"refresh_token": body["tokens"]["refresh_token"]}
    )
    assert renewed.status_code == 200
    assert decode_token(renewed.json()["access_token"])["sub"] == user.id


async def test_the_context_comes_back_exactly_as_it_was_sent(client, db_session, target) -> None:
    """Compared as sorted JSON text, because ``1 == 1.0`` in Python and an int drifting into
    a float is exactly what a lax comparison would call intact. The session is expired
    between the two calls so the exchange reads the context back out of the column."""
    sent = {
        "projectId": "3f2a-proj",
        "nested": {"list": [1, 2.5, True, None, "ação"], "one": 1, "one_point_oh": 1.0},
        "empty": {},
    }
    _user, headers, refresh = await a_member(db_session, target)
    code = await a_code(client, headers, refresh, context=sent)
    db_session.expire_all()

    returned = (await client.post(EXCHANGE, json={"code": code})).json()["context"]

    assert json.dumps(returned, sort_keys=True) == json.dumps(sent, sort_keys=True)


async def test_a_handoff_without_context_exchanges_to_a_null_context(
    client, db_session, target
) -> None:
    _user, headers, refresh = await a_member(db_session, target)
    code = await a_code(client, headers, refresh)

    response = await client.post(EXCHANGE, json={"code": code})

    assert response.json()["context"] is None
    [row] = await codes_in(db_session)
    assert row.context is None


@pytest.mark.parametrize(
    ("value", "status"),
    [("x" * 1008, 201), ("x" * 1009, 422), ("ç" * 505, 422)],
    ids=["exactly-a-kilobyte", "one-byte-over", "counted-in-bytes-not-characters"],
)
async def test_a_context_is_measured_in_bytes_and_a_kilobyte_is_the_most_it_may_weigh(
    client, db_session, target, value, status
) -> None:
    """``{"projectId":""}`` is sixteen bytes. The last case is 521 characters and 1026 bytes,
    so a limit counted in characters lets it through."""
    _user, headers, refresh = await a_member(db_session, target)

    response = await client.post(
        HANDOFF, json=a_body(refresh, context={"projectId": value}), headers=headers
    )

    assert response.status_code == status
    if status == 422:
        assert response.json()["code"] == "UNPROCESSABLE_VALUE"
    assert len(await codes_in(db_session)) == (1 if status == 201 else 0)


@pytest.mark.parametrize(
    ("context", "code"),
    [("[1, 2]", None), ('"a string"', None), ('{"n": NaN}', "UNPROCESSABLE_VALUE")],
    ids=["list", "string", "nan"],
)
async def test_a_context_that_is_not_an_object_or_carries_nan_is_refused(
    client, db_session, target, context, code
) -> None:
    """Sent as raw bytes: httpx will not encode NaN, and the server's parser accepts it. The
    ``json`` column would then fail with a 500 — and so would a refusal from the request
    model, which echoes its input — so NaN is refused by the service, with its own code."""
    _user, headers, refresh = await a_member(db_session, target)
    raw = f'{{"app_key": "{APP_KEY}", "refresh_token": "{refresh}", "context": {context}}}'

    response = await client.post(
        HANDOFF, content=raw, headers={**headers, "Content-Type": "application/json"}
    )

    assert response.status_code == 422
    assert response.json().get("code") == code
    assert await codes_in(db_session) == []


async def test_a_deactivated_account_cannot_exchange_its_code(client, db_session, target) -> None:
    user, headers, refresh = await a_member(db_session, target)
    code = await a_code(client, headers, refresh)
    user.is_active = False
    await db_session.commit()
    issued = await refresh_rows(db_session)

    response = await client.post(EXCHANGE, json={"code": code})

    assert response.status_code == 403
    assert await refresh_rows(db_session) == issued
    [row] = await codes_in(db_session)
    assert row.used_at is None


# --- DoD 4: the exchange is limited per address -------------------------------------------


async def test_the_exchange_is_limited_per_address(client_from) -> None:
    """A different code on every attempt, so a bucket keyed on the code never fills — and a
    second address still answered, so a single global bucket fails too."""
    limit = get_settings().auth_handoff_exchange_limit_per_minute

    async with client_from(HERE) as here:
        answered = [
            (await here.post(EXCHANGE, json={"code": secrets.token_urlsafe(32)})).status_code
            for _ in range(limit)
        ]
        blocked = await here.post(EXCHANGE, json={"code": secrets.token_urlsafe(32)})
    async with client_from(ELSEWHERE) as elsewhere:
        other = await elsewhere.post(EXCHANGE, json={"code": secrets.token_urlsafe(32)})

    assert answered == [401] * limit
    assert blocked.status_code == 429
    assert other.status_code == 401


async def test_a_limited_exchange_spends_nothing(client, db_session, target) -> None:
    """The 429 lands before the service, so a live code refused by it is still live."""
    _user, headers, refresh = await a_member(db_session, target)
    code = await a_code(client, headers, refresh)
    for _ in range(get_settings().auth_handoff_exchange_limit_per_minute):
        await client.post(EXCHANGE, json={"code": secrets.token_urlsafe(32)})

    assert (await client.post(EXCHANGE, json={"code": code})).status_code == 429
    [row] = await codes_in(db_session)
    assert row.used_at is None

    limiter.reset()
    assert (await client.post(EXCHANGE, json={"code": code})).status_code == 200


def test_the_limited_exchange_resolves_its_dependencies() -> None:
    """``@limiter.limit`` wraps the handler, and with ``from __future__ import annotations``
    in the router FastAPI would resolve the annotations against slowapi's module: the session
    would become a required query parameter and every exchange a 422 before the handler ran.
    The same trap ``tests/test_shema/test_forms.py`` guards for the intake routes."""
    from fastapi.routing import APIRoute

    from app.main import create_app

    [route] = [
        route
        for route in create_app().routes
        if isinstance(route, APIRoute) and route.path == EXCHANGE
    ]
    assert {param.name for param in route.dependant.query_params} == set()


# --- DoD 5: no raw code stored; the migration builds what the model declares ---------------


def test_the_migration_creates_and_drops_every_column_the_model_declares() -> None:
    """The suite builds its schema from the models and never runs a migration, so a column
    the revision forgot would pass every test here and fail on the first deploy."""
    source = REVISION.read_text(encoding="utf-8")
    bodies = {
        node.name: ast.get_source_segment(source, node) or ""
        for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef)
    }
    table = Base.metadata.tables["auth_handoff_codes"]

    assert '"auth_handoff_codes"' in bodies["upgrade"]
    assert '"auth_handoff_codes"' in bodies["downgrade"]
    assert [c.name for c in table.columns if f'"{c.name}"' not in bodies["upgrade"]] == []
    assert sorted(i.name for i in table.indexes if i.name and i.name not in bodies["upgrade"]) == []
