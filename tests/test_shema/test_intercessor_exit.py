"""The exit link — how a person in the prayer network, who has no account, leaves it.

The client's answer on 22/sep was *"ainda não existe caminho"*. What these tests hold is the
path and its limits: the token is kept as a digest; opening the link changes nothing (a link
previewer opens every URL); confirming erases the person, their consents and every link, and the
tables are read afterwards to prove it; every link that opens nothing gets the same answer; and
the two routes need no login and are limited **per address**, across tokens.

Run over the wire where the claim is about the route — the absent guard, the 204s, the limit —
and against the service where it is about the store.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.routing import APIRoute
from sqlalchemy import func, select, update

from app.api.shema.intercessor_exit import EXIT_READ_RATE_LIMIT, EXIT_WRITE_RATE_LIMIT
from app.core.exceptions import NotFoundError
from app.db.models.shema_consent import ShemaIntercessorConsent
from app.db.models.shema_exit_link import ShemaIntercessorExitLink
from app.db.models.shema_intercessor import ShemaIntercessor
from app.services.common import tokens
from app.services.shema import EXIT_LINK_DAYS, exit_url, issue_exit_link
from app.services.shema._directory import DEAD_EXIT_LINK
from tests.test_shema.conftest import (
    PEOPLE,
    PREFIX,
    auth_header,
    make_intercessor,
    make_scoped_user,
)

CONTACT = "maria.santos@example.org"


def _exit(token: str) -> str:
    return f"{PREFIX}/intercessors/leave/{token}"


@pytest.fixture()
async def circle_headers(db_session, shema_app) -> dict[str, str]:
    user = await make_scoped_user(
        db_session, shema_app, email="circle@exit.test", role_key="resourceCircle", regions=[]
    )
    return await auth_header(db_session, user)


@pytest.fixture()
async def person(client, circle_headers) -> dict:
    """One contact with all three consents, so every table that can hold them does."""
    created = await make_intercessor(client, circle_headers, contact=CONTACT)
    for context in ("directory", "partner-export"):
        res = await client.put(
            f"{PEOPLE}/{created['id']}/consents/{context}",
            headers=circle_headers,
            json={"basis": "said yes"},
        )
        assert res.status_code == 200, res.text
    return created


async def _count(db_session, model) -> int:
    return (await db_session.execute(select(func.count()).select_from(model))).scalar_one()


# --- the token ------------------------------------------------------------------------------


async def test_the_exit_token_is_stored_as_its_digest_and_never_raw(db_session, person) -> None:
    """Its holder has no account, so a database dump is the only place it could be read from."""
    raw = await issue_exit_link(db_session, person["id"])

    link = (await db_session.execute(select(ShemaIntercessorExitLink))).scalar_one()
    assert link.token_hash == tokens.digest(raw)
    assert raw not in {link.id, link.token_hash, link.intercessor_id}
    assert len(raw) == 43


async def test_the_link_lives_the_days_its_key_says(db_session, person) -> None:
    now = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)

    await issue_exit_link(db_session, person["id"], now=now)

    link = (await db_session.execute(select(ShemaIntercessorExitLink))).scalar_one()
    assert EXIT_LINK_DAYS == 365
    assert link.expires_at == now + timedelta(days=EXIT_LINK_DAYS)


async def test_issuing_a_link_for_nobody_is_a_404(db_session, shema_app) -> None:
    """Read before written, so a bad id names what is missing instead of failing in a flush."""
    with pytest.raises(NotFoundError):
        await issue_exit_link(db_session, "nobody")


def test_the_exit_url_is_the_consoles_leave_page() -> None:
    """The console's public page — ``src/App.tsx``'s ``leave/:token`` — carries the token."""
    assert exit_url("https://shema.shemaywam.com/", "abc") == (
        "https://shema.shemaywam.com/leave/abc"
    )
    assert exit_url(None, "abc") == "http://localhost:5173/leave/abc"


# --- opening and confirming ------------------------------------------------------------------


async def test_opening_the_link_needs_no_login_and_erases_nobody(
    client, db_session, person
) -> None:
    """A link previewer fetches every URL it is sent, so the read can never be the act. The
    answer is 204 and empty: nothing about the person reaches whoever holds the link."""
    raw = await issue_exit_link(db_session, person["id"])

    for _ in range(3):
        res = await client.get(_exit(raw))
        assert res.status_code == 204
        assert res.content == b""

    assert await _count(db_session, ShemaIntercessor) == 1
    assert await _count(db_session, ShemaIntercessorConsent) == 3


async def test_confirming_erases_the_person_their_consents_and_their_links(
    client, db_session, person
) -> None:
    """**The DoD's second line, read off the tables afterwards.** No tombstone, no ``removed``
    flag: every table that held anything about the person is empty, and the contact string is
    in none of them — asked of storage, because *absent from the list* is what hiding does too.
    """
    first = await issue_exit_link(db_session, person["id"])
    await issue_exit_link(db_session, person["id"])

    res = await client.post(_exit(first))

    assert res.status_code == 204
    assert res.content == b""
    for model in (ShemaIntercessor, ShemaIntercessorConsent, ShemaIntercessorExitLink):
        assert await _count(db_session, model) == 0, model.__tablename__
    held = await db_session.execute(
        select(func.count())
        .select_from(ShemaIntercessor)
        .where(ShemaIntercessor.contact == CONTACT)
    )
    assert held.scalar_one() == 0


async def test_every_send_mints_its_own_link_and_each_one_works(client, db_session, person) -> None:
    """Nothing is revoked on a new send: somebody holding the older message can still leave."""
    older = await issue_exit_link(db_session, person["id"])
    newer = await issue_exit_link(db_session, person["id"])

    assert older != newer
    assert await _count(db_session, ShemaIntercessorExitLink) == 2
    assert (await client.get(_exit(older))).status_code == 204
    assert (await client.get(_exit(newer))).status_code == 204


async def test_an_expired_link_neither_opens_nor_erases(client, db_session, person) -> None:
    raw = await issue_exit_link(db_session, person["id"])
    await db_session.execute(
        update(ShemaIntercessorExitLink).values(expires_at=datetime.now(UTC) - timedelta(days=1))
    )
    await db_session.commit()

    assert (await client.get(_exit(raw))).status_code == 404
    assert (await client.post(_exit(raw))).status_code == 404
    assert await _count(db_session, ShemaIntercessor) == 1


async def test_an_expired_link_is_pruned_when_the_next_one_is_issued(db_session, person) -> None:
    """The table keeps what can still open something: a link past its clock goes at the next
    send, so rows do not pile up one per month for ever."""
    old = await issue_exit_link(db_session, person["id"])
    await db_session.execute(
        update(ShemaIntercessorExitLink).values(expires_at=datetime.now(UTC) - timedelta(days=1))
    )
    await db_session.commit()

    fresh = await issue_exit_link(db_session, person["id"])

    hashes = set((await db_session.execute(select(ShemaIntercessorExitLink.token_hash))).scalars())
    assert hashes == {tokens.digest(fresh)}
    assert tokens.digest(old) not in hashes


async def test_every_dead_link_gets_the_same_answer(client, db_session, person) -> None:
    """Unknown, expired, already spent: one status and one sentence. Telling *expired* from
    *already left* would tell whoever holds a forwarded link whether the person is still in
    the network."""
    expired = await issue_exit_link(db_session, person["id"])
    await db_session.execute(
        update(ShemaIntercessorExitLink).values(expires_at=datetime.now(UTC) - timedelta(days=1))
    )
    await db_session.commit()
    spent = await issue_exit_link(db_session, person["id"])
    assert (await client.post(_exit(spent))).status_code == 204

    answers = [
        await client.get(_exit("never-issued")),
        await client.post(_exit("never-issued")),
        await client.get(_exit(expired)),
        await client.get(_exit(spent)),
        await client.post(_exit(spent)),
    ]

    assert {res.status_code for res in answers} == {404}
    assert {res.json()["detail"] for res in answers} == {DEAD_EXIT_LINK}


async def test_leaving_logs_the_event_and_not_the_person(
    client, db_session, person, caplog
) -> None:
    """The line an operator reads says *somebody left, which row it was*. Never the name, the
    contact or the token — a log is kept longer and read by more people than a response."""
    raw = await issue_exit_link(db_session, person["id"])
    caplog.set_level(logging.INFO, logger="app.services.shema.leave_intercessor")

    assert (await client.post(_exit(raw))).status_code == 204

    lines = [r for r in caplog.records if r.name == "app.services.shema.leave_intercessor"]
    assert len(lines) == 1
    assert lines[0].__dict__["shema_intercessor_id"] == person["id"]
    written = " ".join(str(value) for value in lines[0].__dict__.values())
    for secret in (person["name"], CONTACT, raw, tokens.digest(raw)):
        assert secret not in written


# --- public, and limited per address ---------------------------------------------------------


async def test_the_exit_routes_need_no_authorization_header(client, db_session, person) -> None:
    """The premise of the whole path: the person has no account. ``tests/shema_harness.py``
    names the path in ``UNAUTHENTICATED_PATHS``; this is the other side of that line."""
    raw = await issue_exit_link(db_session, person["id"])

    assert (await client.get(_exit(raw))).status_code == 204
    assert (await client.post(_exit(raw))).status_code == 204


async def test_the_address_limit_holds_across_tokens(client, db_session, shema_app) -> None:
    """**Per address, not per address and URL.** Every call below carries a different token
    from one address, which is exactly somebody walking tokens; a limit keyed on the URL —
    slowapi's default scope — would give each token a fresh bucket and never answer 429."""
    reads = int(EXIT_READ_RATE_LIMIT.split("/")[0])
    writes = int(EXIT_WRITE_RATE_LIMIT.split("/")[0])

    read_statuses = [(await client.get(_exit(f"walk-{n}"))).status_code for n in range(reads + 1)]
    write_statuses = [
        (await client.post(_exit(f"walk-{n}"))).status_code for n in range(writes + 1)
    ]

    assert read_statuses[:reads] == [404] * reads
    assert read_statuses[-1] == 429
    assert write_statuses[:writes] == [404] * writes
    assert write_statuses[-1] == 429


def test_the_limited_exit_routes_resolve_their_dependencies() -> None:
    """The slowapi trap ``forms.py`` documents: with ``from __future__ import annotations`` in
    the router, ``Db`` would resolve against slowapi's module and turn into a required query
    parameter — every call a mystery 422 on the one route with no guard to blame."""
    from app.main import create_app

    routes = [
        route
        for route in create_app().routes
        if isinstance(route, APIRoute) and route.path == _exit("{token}")
    ]
    assert sorted(method for route in routes for method in route.methods) == ["GET", "POST"]
    for route in routes:
        assert {param.name for param in route.dependant.query_params} == set()


async def test_every_other_network_route_refuses_a_member_without_resource_circle(
    client, db_session, shema_app, circle_headers, person
) -> None:
    """**The DoD's fifth line, other half**: the exit link opened two routes and nothing else.
    Every route of the network still refuses every other Shemá role — never an admin, who
    passes every guard and would make this pass with the guards deleted."""
    target = f"{PEOPLE}/{person['id']}"
    calls = [
        ("GET", PEOPLE, None),
        ("POST", PEOPLE, {"name": "X", "country": "BR", "contact": "x@example.org"}),
        ("PATCH", target, {"name": "Y"}),
        ("DELETE", target, None),
        ("GET", f"{target}/contact", None),
        ("PUT", f"{target}/consents/directory", {"basis": "yes"}),
        ("DELETE", f"{target}/consents/directory", None),
        ("POST", f"{target}/review", None),
    ]
    for role in ("coordinator", "obtLab"):
        user = await make_scoped_user(
            db_session, shema_app, email=f"{role}@exit.test", role_key=role, regions=[]
        )
        headers = await auth_header(db_session, user)
        for method, url, body in calls:
            res = await client.request(method, url, headers=headers, json=body)
            assert res.status_code == 403, (role, method, url)

    assert await _count(db_session, ShemaIntercessor) == 1


async def test_leaving_through_the_link_is_marked_as_the_persons_own_act(
    client, db_session, person
) -> None:
    """OBT-577: no account acted, so the mark names no account — and says who did, in words."""
    from app.db.models.shema_change_log import ShemaChangeLog

    token = await issue_exit_link(db_session, person["id"])

    assert (await client.post(_exit(token))).status_code == 204

    [row] = (
        await db_session.execute(select(ShemaChangeLog).where(ShemaChangeLog.action == "removed"))
    ).scalars()
    assert (row.subject, row.subject_id) == ("intercessor", person["id"])
    assert row.actor_id is None
    assert "exit link" in row.actor_name
