"""Fencing: a write by someone who is not the holder must not land.

The lock is only advisory until the writes enforce it. The guard is deliberately
permissive by default — a session nobody locked accepts autosaves as it always has,
because the real SPA client autosaves without ever acquiring a lock and would otherwise
lose every keystroke behind a retry loop that ends at the tab closing.

Two different 409s live on the autosave route and demand opposite reactions, so the
tests here pin the code that tells them apart, not just the status.
"""

from __future__ import annotations

from datetime import UTC, datetime
from importlib import import_module

from tests.test_sound_necklace.conftest import SN, expire_lease, new_session

JSON_HEADERS = {"content-type": "application/json"}


def state_bytes(mode: str = "escuta") -> str:
    return '{"schema_version": 1, "mode": "' + mode + '"}'


async def autosave(client, headers, session_id: str, body: str, if_match: str | None = None):
    extra = {"If-Match": if_match} if if_match is not None else {}
    return await client.put(
        f"{SN}/sessions/{session_id}/state",
        headers={**headers, **JSON_HEADERS, **extra},
        content=body,
    )


async def current_version(client, headers, session_id: str) -> int:
    res = await client.get(f"{SN}/sessions/{session_id}/state", headers=headers)
    return int(res.headers["ETag"].strip('"'))


# ── The permissive default: do not break the client that never locks ──────────


async def test_autosave_on_an_unlocked_session_still_lands(client, alice, project):
    """The real client autosaves without ever acquiring a lock. This must keep working."""
    _user, headers = alice
    session_id = await new_session(client, headers, project.id)

    res = await autosave(client, headers, session_id, state_bytes())

    assert res.status_code == 200, res.text


async def test_the_holder_can_autosave(client, alice, project):
    _user, headers = alice
    session_id = await new_session(client, headers, project.id)
    await client.put(f"{SN}/sessions/{session_id}/lock", headers=headers)

    res = await autosave(client, headers, session_id, state_bytes())

    assert res.status_code == 200, res.text


async def test_autosave_lands_once_the_other_holder_lease_expired(
    client, db_session, alice, bob, project
):
    """An abandoned tab must not lock the session out forever."""
    _alice_user, alice_headers = alice
    _bob_user, bob_headers = bob
    session_id = await new_session(client, alice_headers, project.id)
    await client.put(f"{SN}/sessions/{session_id}/lock", headers=bob_headers)
    await expire_lease(db_session, session_id)

    res = await autosave(client, alice_headers, session_id, state_bytes())

    assert res.status_code == 200, res.text


# ── The bite: a non-holder cannot overwrite the holder ────────────────────────


async def test_autosave_by_a_non_holder_is_refused_with_the_holder_info(
    client, alice, bob, project
):
    """The "sessão em uso por…" body: the loser is told who won, not just that it lost."""
    _alice_user, alice_headers = alice
    _bob_user, bob_headers = bob
    session_id = await new_session(client, alice_headers, project.id)
    await client.put(f"{SN}/sessions/{session_id}/lock", headers=bob_headers)

    res = await autosave(client, alice_headers, session_id, state_bytes())

    assert res.status_code == 409, res.text
    body = res.json()
    assert body["code"] == "SESSION_LOCKED"
    assert body["holder_name"] == "Bob"
    # An instant, offset and all — the lock routes carry one and this must match them.
    # SQLite hands back naive datetimes where Postgres hands back aware, so an
    # un-normalized column reaches the wire as a different type of thing under test than
    # in production. Comparing against an aware now() is what makes that a failure.
    assert datetime.fromisoformat(body["expires_at"]) > datetime.now(UTC)


async def test_the_refused_autosave_does_not_advance_the_state(client, alice, bob, project):
    """A rejected write must be a no-op, not a partial one: the winner's bytes stand."""
    _alice_user, alice_headers = alice
    _bob_user, bob_headers = bob
    session_id = await new_session(client, alice_headers, project.id)
    await client.put(f"{SN}/sessions/{session_id}/lock", headers=bob_headers)
    await autosave(client, bob_headers, session_id, state_bytes("bob-wrote-this"))
    version_before = await current_version(client, bob_headers, session_id)

    refused = await autosave(client, alice_headers, session_id, state_bytes("alice-lost"))

    assert refused.status_code == 409
    assert await current_version(client, bob_headers, session_id) == version_before
    kept = await client.get(f"{SN}/sessions/{session_id}/state", headers=bob_headers)
    assert "bob-wrote-this" in kept.text


# ── Two 409s, one route ──────────────────────────────────────────────────────


async def test_a_stale_version_is_a_different_conflict_from_a_lost_lock(client, alice, project):
    """Same status, opposite instruction: reload and retry, versus stop and go review."""
    _user, headers = alice
    session_id = await new_session(client, headers, project.id)
    await autosave(client, headers, session_id, state_bytes())

    res = await autosave(client, headers, session_id, state_bytes(), if_match="0")

    assert res.status_code == 409, res.text
    body = res.json()
    assert body["code"] == "CONFLICT"
    assert "current_version" in body


async def test_losing_the_lock_outranks_a_stale_version(client, alice, bob, project):
    """A locked-out writer told to "reload and retry" would loop on it forever."""
    _alice_user, alice_headers = alice
    _bob_user, bob_headers = bob
    session_id = await new_session(client, alice_headers, project.id)
    await autosave(client, alice_headers, session_id, state_bytes())
    await client.put(f"{SN}/sessions/{session_id}/lock", headers=bob_headers)

    res = await autosave(client, alice_headers, session_id, state_bytes(), if_match="0")

    assert res.status_code == 409, res.text
    assert res.json()["code"] == "SESSION_LOCKED"


# ── Complete ─────────────────────────────────────────────────────────────────


async def test_complete_by_a_non_holder_is_refused(client, alice, bob, project):
    """A paused tab waking up must not finish a session someone else is editing."""
    _alice_user, alice_headers = alice
    _bob_user, bob_headers = bob
    session_id = await new_session(client, alice_headers, project.id)
    await client.put(f"{SN}/sessions/{session_id}/lock", headers=bob_headers)

    res = await client.post(f"{SN}/sessions/{session_id}/complete", headers=alice_headers)

    assert res.status_code == 409, res.text
    assert res.json()["code"] == "SESSION_LOCKED"
    assert res.json()["holder_name"] == "Bob"


async def test_complete_on_an_unlocked_session_still_works(client, alice, project):
    _user, headers = alice
    session_id = await new_session(client, headers, project.id)

    res = await client.post(f"{SN}/sessions/{session_id}/complete", headers=headers)

    assert res.status_code == 200, res.text


async def test_the_holder_can_complete(client, alice, project):
    _user, headers = alice
    session_id = await new_session(client, headers, project.id)
    await client.put(f"{SN}/sessions/{session_id}/lock", headers=headers)

    res = await client.post(f"{SN}/sessions/{session_id}/complete", headers=headers)

    assert res.status_code == 200, res.text


# ── Reopen ───────────────────────────────────────────────────────────────────


async def test_reopen_by_a_non_holder_is_refused(client, alice, bob, project):
    """Reopen moves the same column complete guards; fencing one and not the other
    would let the loser undo the winner's completion."""
    _alice_user, alice_headers = alice
    _bob_user, bob_headers = bob
    session_id = await new_session(client, alice_headers, project.id)
    await client.post(f"{SN}/sessions/{session_id}/complete", headers=alice_headers)
    await client.put(f"{SN}/sessions/{session_id}/lock", headers=bob_headers)

    res = await client.post(f"{SN}/sessions/{session_id}/reopen", headers=alice_headers)

    assert res.status_code == 409, res.text
    assert res.json()["code"] == "SESSION_LOCKED"
    still = await client.get(f"{SN}/sessions/{session_id}", headers=bob_headers)
    assert still.json()["status"] == "completed"


async def test_reopen_on_an_unlocked_session_still_works(client, alice, project):
    _user, headers = alice
    session_id = await new_session(client, headers, project.id)
    await client.post(f"{SN}/sessions/{session_id}/complete", headers=headers)

    res = await client.post(f"{SN}/sessions/{session_id}/reopen", headers=headers)

    assert res.status_code == 200, res.text
    assert res.json()["status"] == "in_progress"


async def test_the_holder_can_reopen(client, alice, project):
    _user, headers = alice
    session_id = await new_session(client, headers, project.id)
    await client.post(f"{SN}/sessions/{session_id}/complete", headers=headers)
    await client.put(f"{SN}/sessions/{session_id}/lock", headers=headers)

    res = await client.post(f"{SN}/sessions/{session_id}/reopen", headers=headers)

    assert res.status_code == 200, res.text


# ── Refused, but the holder is already gone ──────────────────────────────────
#
# The guarded UPDATE refuses, and by the time the diagnosis read runs the lease has
# lapsed — there is no holder left to name. The write landed nothing, so the honest
# answer is "try again", and it needs a code of its own: CONFLICT is defined as a stale
# version with a `current_version` to reload from, and these two routes have no version
# at all. A client handed CONFLICT here reloads and retries against nothing, forever.
#
# The window is microseconds wide, so the diagnosis is stubbed to find nobody — which is
# precisely what it returns when the lease expires inside it.


def lease_lapsed_before_the_diagnosis(monkeypatch, service: str) -> None:
    """Make the diagnosis read find nobody, as it would if the lease expired inside it.

    Imported by path: the package re-exports each service function under its module's
    own name, so a plain ``from ... import complete_session`` hands back the function.
    """
    module = import_module(f"app.services.sound_necklace.{service}")

    async def nobody_holds_it(*_args, **_kwargs):
        return None

    monkeypatch.setattr(module, "raise_if_locked_by_other", nobody_holds_it)


async def test_a_complete_refused_by_a_lease_that_then_lapsed_is_not_a_stale_version(
    client, alice, bob, project, monkeypatch
):
    _alice_user, alice_headers = alice
    _bob_user, bob_headers = bob
    session_id = await new_session(client, alice_headers, project.id)
    await client.put(f"{SN}/sessions/{session_id}/lock", headers=bob_headers)
    lease_lapsed_before_the_diagnosis(monkeypatch, "complete_session")

    res = await client.post(f"{SN}/sessions/{session_id}/complete", headers=alice_headers)

    assert res.status_code == 409, res.text
    assert res.json()["code"] == "SESSION_LOCK_CHANGED"
    # Refused, not silently dropped: the session must still be open.
    still = await client.get(f"{SN}/sessions/{session_id}", headers=bob_headers)
    assert still.json()["status"] == "in_progress"


async def test_a_reopen_refused_by_a_lease_that_then_lapsed_is_not_a_stale_version(
    client, alice, bob, project, monkeypatch
):
    _alice_user, alice_headers = alice
    _bob_user, bob_headers = bob
    session_id = await new_session(client, alice_headers, project.id)
    await client.post(f"{SN}/sessions/{session_id}/complete", headers=alice_headers)
    await client.put(f"{SN}/sessions/{session_id}/lock", headers=bob_headers)
    lease_lapsed_before_the_diagnosis(monkeypatch, "reopen_session")

    res = await client.post(f"{SN}/sessions/{session_id}/reopen", headers=alice_headers)

    assert res.status_code == 409, res.text
    assert res.json()["code"] == "SESSION_LOCK_CHANGED"
