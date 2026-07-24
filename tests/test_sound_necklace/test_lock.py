"""The advisory single-editor lock: acquire, renew, status, release, takeover.

The lock is advisory and exists for the "sessão em uso por…" UX, so acquiring a session
someone else holds is not an error: it answers 200 with the current holder and the SPA
opens in review mode. A conflict status here would make the real client throw
(adapters/sessions/types.ts: "NUNCA lança por conflito").

Expiry is arranged by writing the lease's expiry into the past rather than by sleeping:
the TTL is a minute and a suite that waited it out four times over would be useless.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tests.baker import make_language, make_project
from tests.test_sound_necklace.conftest import (
    SN,
    expire_lease,
    give_project_an_audio,
    make_facilitator,
    new_session,
    set_lease_expiry,
)

# ── Acquire and renew ────────────────────────────────────────────────────────


async def test_acquiring_an_unheld_session_makes_the_caller_the_holder(client, alice, project):
    user, headers = alice
    session_id = await new_session(client, headers, project.id)

    res = await client.put(f"{SN}/sessions/{session_id}/lock", headers=headers)

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["held"] is True
    assert body["holder"]["user_id"] == user.id
    assert body["holder"]["display_name"] == "Alice"
    assert datetime.fromisoformat(body["expires_at"]) > datetime.now(UTC)


async def test_the_holder_reacquiring_renews_the_full_ttl(client, db_session, alice, project):
    """The heartbeat calls this every 15s; it must extend, not merely not-fail.

    The lease is left half-spent, so a renew that did nothing would leave ~30s and a
    renew that re-applied the TTL leaves ~60s. Only the second passes.
    """
    user, headers = alice
    session_id = await new_session(client, headers, project.id)
    await client.put(f"{SN}/sessions/{session_id}/lock", headers=headers)
    await set_lease_expiry(db_session, session_id, datetime.now(UTC) + timedelta(seconds=30))

    res = await client.put(f"{SN}/sessions/{session_id}/lock", headers=headers)

    assert res.status_code == 200, res.text
    assert res.json()["holder"]["user_id"] == user.id
    renewed = datetime.fromisoformat(res.json()["expires_at"])
    assert renewed > datetime.now(UTC) + timedelta(seconds=50), "renew did not re-apply the TTL"


async def test_the_lease_runs_for_a_minute(client, alice, project):
    """The SPA heartbeats at 15s against this number; four beats of slack is the design."""
    _user, headers = alice
    session_id = await new_session(client, headers, project.id)

    res = await client.put(f"{SN}/sessions/{session_id}/lock", headers=headers)

    expires_at = datetime.fromisoformat(res.json()["expires_at"])
    assert timedelta(seconds=55) < expires_at - datetime.now(UTC) <= timedelta(seconds=60)


async def test_a_second_user_is_told_who_holds_it_instead_of_getting_an_error(
    client, alice, bob, project
):
    """The real client has no handler for a throw here: conflict is 200 + holder info."""
    alice_user, alice_headers = alice
    _bob_user, bob_headers = bob
    session_id = await new_session(client, alice_headers, project.id)
    await client.put(f"{SN}/sessions/{session_id}/lock", headers=alice_headers)

    res = await client.put(f"{SN}/sessions/{session_id}/lock", headers=bob_headers)

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["held"] is True
    assert body["holder"]["user_id"] == alice_user.id
    assert body["holder"]["display_name"] == "Alice"
    # Reported Alice, but did it also quietly hand the lease to Bob?
    status = await client.get(f"{SN}/sessions/{session_id}/lock", headers=alice_headers)
    assert status.json()["holder"]["user_id"] == alice_user.id


async def test_an_expired_lease_is_taken_by_the_next_caller(
    client, db_session, alice, bob, project
):
    """Survives a tab crash with nobody unlocking it by hand: the point of a TTL."""
    _alice_user, alice_headers = alice
    bob_user, bob_headers = bob
    session_id = await new_session(client, alice_headers, project.id)
    await client.put(f"{SN}/sessions/{session_id}/lock", headers=alice_headers)
    await expire_lease(db_session, session_id)

    res = await client.put(f"{SN}/sessions/{session_id}/lock", headers=bob_headers)

    assert res.status_code == 200, res.text
    assert res.json()["holder"]["user_id"] == bob_user.id


# ── Status ───────────────────────────────────────────────────────────────────


async def test_a_session_nobody_opened_reads_as_unheld(client, alice, project):
    _user, headers = alice
    session_id = await new_session(client, headers, project.id)

    res = await client.get(f"{SN}/sessions/{session_id}/lock", headers=headers)

    assert res.status_code == 200, res.text
    assert res.json() == {"held": False, "holder": None, "expires_at": None}


async def test_an_expired_lease_reads_as_unheld(client, db_session, alice, project):
    _user, headers = alice
    session_id = await new_session(client, headers, project.id)
    await client.put(f"{SN}/sessions/{session_id}/lock", headers=headers)
    await expire_lease(db_session, session_id)

    res = await client.get(f"{SN}/sessions/{session_id}/lock", headers=headers)

    assert res.json() == {"held": False, "holder": None, "expires_at": None}


async def test_the_holder_display_name_falls_back_to_the_email(
    client, db_session, project, sound_necklace_app
):
    """display_name is nullable, but the SPA's LockHolder requires a string."""
    _user, headers = await make_facilitator(
        db_session, sound_necklace_app, project, "nameless@example.com", None
    )
    session_id = await new_session(client, headers, project.id)

    res = await client.put(f"{SN}/sessions/{session_id}/lock", headers=headers)

    assert res.json()["holder"]["display_name"] == "nameless@example.com"


# ── Release ──────────────────────────────────────────────────────────────────


async def test_releasing_frees_the_session_for_the_next_caller(client, alice, bob, project):
    _alice_user, alice_headers = alice
    bob_user, bob_headers = bob
    session_id = await new_session(client, alice_headers, project.id)
    await client.put(f"{SN}/sessions/{session_id}/lock", headers=alice_headers)

    res = await client.delete(f"{SN}/sessions/{session_id}/lock", headers=alice_headers)

    assert res.status_code == 204, res.text
    taken = await client.put(f"{SN}/sessions/{session_id}/lock", headers=bob_headers)
    assert taken.json()["holder"]["user_id"] == bob_user.id


async def test_releasing_a_lock_held_by_someone_else_does_not_steal_it(client, alice, bob, project):
    """Idempotent must not mean "anyone can unlock": Bob's DELETE is a no-op, not a theft."""
    alice_user, alice_headers = alice
    _bob_user, bob_headers = bob
    session_id = await new_session(client, alice_headers, project.id)
    await client.put(f"{SN}/sessions/{session_id}/lock", headers=alice_headers)

    res = await client.delete(f"{SN}/sessions/{session_id}/lock", headers=bob_headers)

    assert res.status_code == 204, res.text
    status = await client.get(f"{SN}/sessions/{session_id}/lock", headers=alice_headers)
    assert status.json()["held"] is True
    assert status.json()["holder"]["user_id"] == alice_user.id


async def test_releasing_a_session_that_was_never_locked_is_a_no_op(client, alice, project):
    """The SPA releases on unload and can do nothing useful with a failure there."""
    _user, headers = alice
    session_id = await new_session(client, headers, project.id)

    res = await client.delete(f"{SN}/sessions/{session_id}/lock", headers=headers)

    assert res.status_code == 204, res.text


# ── Access control ───────────────────────────────────────────────────────────


async def test_the_lock_of_an_unknown_session_is_not_found(client, alice):
    _user, headers = alice

    res = await client.put(f"{SN}/sessions/does-not-exist/lock", headers=headers)

    assert res.status_code == 404, res.text


async def test_a_session_in_an_unreachable_project_is_closed_on_every_lock_route(
    client, db_session, alice, sound_necklace_app
):
    """The holder's name falls back to their email, so an open GET would leak it."""
    _user, headers = alice
    language = await make_language(db_session, name="Outra", code="oth")
    foreign_project = await make_project(db_session, language.id, name="Projeto B")
    await give_project_an_audio(db_session, foreign_project.id)
    _owner, owner_headers = await make_facilitator(
        db_session, sound_necklace_app, foreign_project, "owner@example.com", "Owner"
    )
    session_id = await new_session(client, owner_headers, foreign_project.id)
    await client.put(f"{SN}/sessions/{session_id}/lock", headers=owner_headers)

    acquire = await client.put(f"{SN}/sessions/{session_id}/lock", headers=headers)
    read = await client.get(f"{SN}/sessions/{session_id}/lock", headers=headers)
    release = await client.delete(f"{SN}/sessions/{session_id}/lock", headers=headers)

    assert [acquire.status_code, read.status_code, release.status_code] == [403, 403, 403]
    assert "owner@example.com" not in read.text
