"""Consent records: the queryable evidence of a lawful basis (§12 / O6).

The record is the authoritative evidence; ``sn_sessions.pipeline_consent`` is a
write-only leftover the SPA sends on create and never reads back. These tests are written
against what makes the record evidence rather than decoration: that it exists for the path
the SPA actually uses, that a re-confirmation is honest about when it happened, that
nothing asserts a consent nobody gave, and that it outlives the operator who typed it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select, text

from app.db.models.auth import User
from app.db.models.sound_necklace import ConsentType, SnConsent, SnSession
from tests.baker import make_language, make_project, make_project_user_access, make_user
from tests.test_sound_necklace.conftest import (
    audio_of,
    auth_header,
    give_project_an_audio,
    grant_role,
)

SN = "/api/sound-necklace"


async def new_session(client, headers, project_id: str, *, consent: bool = True) -> str:
    res = await client.post(
        f"{SN}/sessions",
        headers=headers,
        json={
            "audio_id": audio_of(project_id),
            "project_id": project_id,
            "story_name": "O Conto do Boto",
            "story_slug": "conto-do-boto",
            "granularity_level": "medium",
            "bead_sec": 0.5,
            "manifest_id": "fnv1a32:d31a8419",
            "pipeline_consent": consent,
        },
    )
    assert res.status_code == 201, res.text
    return str(res.json()["id"])


@pytest.fixture()
async def facilitator(db_session, sound_necklace_app):
    """A sound-necklace facilitator with access to one project."""
    user = await make_user(db_session, email="facilitator@example.com")
    await grant_role(db_session, sound_necklace_app.id, user.id, "facilitator")
    language = await make_language(db_session, name="Nheengatu", code="yrl")
    project = await make_project(db_session, language.id, name="Projeto A")
    await give_project_an_audio(db_session, project.id)
    await make_project_user_access(db_session, project.id, user.id)
    headers = await auth_header(db_session, user)
    return user, project, headers


def as_utc(when: datetime) -> datetime:
    """The stored instant, comparable on either database.

    SQLite has no timezone type and reads back naive where Postgres reads back aware.
    Both hold the same UTC instant, so this normalizes the suite's database to what
    production returns instead of asserting on the difference.
    """
    return when if when.tzinfo else when.replace(tzinfo=UTC)


async def backdate(db_session, session_id: str, when: datetime) -> None:
    """Age a record's confirmed_at without waiting.

    Written behind the ORM's back on purpose. The point is to make the assertion hold
    no matter how confirmed_at is implemented: a plain two-reads comparison passes today
    only because the column is a microsecond-resolution Python value, and would go on
    passing by luck if someone swapped it for ``func.now()`` — which SQLite stores at
    one-second resolution. Back-dating decades makes the test measure the rule, not the
    clock.
    """
    await db_session.execute(
        text("UPDATE sn_consents SET confirmed_at = :when WHERE session_id = :sid"),
        {"when": when, "sid": session_id},
    )
    await db_session.commit()


# ── The record is born where the SPA actually goes ───────────────────────────


async def test_creating_a_session_with_consent_records_the_evidence(
    client, facilitator, db_session
):
    """The path the SPA really uses (ENG-243) has to produce the record.

    If only the explicit route wrote one, the record would have no caller and
    ``sn_sessions.pipeline_consent`` would go on being the only truth.
    """
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id, consent=True)

    res = await client.get(f"{SN}/sessions/{session_id}/consent", headers=headers)

    assert res.status_code == 200, res.text
    (record,) = res.json()["consents"]
    assert record["type"] == "pipeline_use"
    assert record["confirmed_by"] == _user.id


async def test_creating_a_session_without_consent_records_nothing(client, facilitator):
    """Absent is not denied and not granted — it is a consent we do not hold.

    A row saying "false" would be a claim about the facilitator's intent that nobody
    made. The table holds consents that were given; silence stays silence.
    """
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id, consent=False)

    res = await client.get(f"{SN}/sessions/{session_id}/consent", headers=headers)

    assert res.status_code == 200, res.text
    assert res.json()["consents"] == []


async def test_the_explicit_route_records_consent(client, facilitator):
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id, consent=False)

    res = await client.post(
        f"{SN}/sessions/{session_id}/consent",
        headers=headers,
        json={"type": "pipeline_use"},
    )

    assert res.status_code == 201, res.text
    assert res.json()["type"] == "pipeline_use"


async def test_the_sessions_boolean_cannot_contradict_the_record(client, facilitator, db_session):
    """Two columns claiming the same fact must not disagree.

    Opening a session without consent and recording it afterwards is the path that splits
    them: the record says granted while the session still says false. Nothing reads the
    boolean today — no response carries it, and the SPA reads its own copy out of the
    state document — so this costs nothing now and hands a stale false to whoever wires
    the first read of it.
    """
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id, consent=False)

    await client.post(
        f"{SN}/sessions/{session_id}/consent",
        headers=headers,
        json={"type": "pipeline_use"},
    )

    session = await db_session.get(SnSession, session_id)
    await db_session.refresh(session)
    assert session.pipeline_consent is True, (
        "the session still denies a consent the record attests to"
    )


async def test_consenting_to_the_voice_alone_does_not_assert_pipeline_use(
    client, facilitator, db_session
):
    """The two consents are two different claims by two different speakers.

    A listener agreeing to be recorded says nothing about whether the story may be
    processed, and must not be made to."""
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id, consent=False)

    await client.post(
        f"{SN}/sessions/{session_id}/consent",
        headers=headers,
        json={"type": "voice_answers"},
    )

    session = await db_session.get(SnSession, session_id)
    await db_session.refresh(session)
    assert session.pipeline_consent is False


async def test_the_listener_can_consent_to_their_own_voice_being_recorded(client, facilitator):
    """The second moment §12 asks for and the two-moment table above misses.

    The Colar records the listener's voice — 21+ files per story (§8.7). The listener
    has no account and may not read at all, so the facilitator is who witnesses it:
    confirmed_by is the witness, not the subject.
    """
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)

    res = await client.post(
        f"{SN}/sessions/{session_id}/consent",
        headers=headers,
        json={"type": "voice_answers"},
    )

    assert res.status_code == 201, res.text
    assert res.json()["type"] == "voice_answers"

    listed = await client.get(f"{SN}/sessions/{session_id}/consent", headers=headers)
    assert {c["type"] for c in listed.json()["consents"]} == {"pipeline_use", "voice_answers"}


# ── Re-confirmation ──────────────────────────────────────────────────────────


async def test_re_confirming_updates_the_timestamp_instead_of_duplicating_the_row(
    client, facilitator, db_session
):
    """Idempotent per (session, type) — and the timestamp has to actually move.

    This is the assertion that catches ``onupdate=func.now()``: a re-confirmation
    changes no other column, so the ORM emits no UPDATE at all and the timestamp
    silently keeps the first confirmation's time. The record would then answer "when
    was this last confirmed?" with a lie.
    """
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)
    long_ago = datetime(2020, 1, 1, tzinfo=UTC)
    await backdate(db_session, session_id, long_ago)

    res = await client.post(
        f"{SN}/sessions/{session_id}/consent",
        headers=headers,
        json={"type": "pipeline_use"},
    )

    assert res.status_code == 201, res.text
    rows = (
        (await db_session.execute(select(SnConsent).where(SnConsent.session_id == session_id)))
        .scalars()
        .all()
    )
    assert len(rows) == 1, "a re-confirmation must not open a second record"
    assert as_utc(rows[0].confirmed_at) > long_ago + timedelta(days=1), (
        "the re-confirmation did not move confirmed_at — the record now misdates itself"
    )


async def test_re_confirming_names_whoever_confirmed_it_this_time(
    client, db_session, facilitator, sound_necklace_app
):
    """The record answers "who attested this", so it must name the last attester."""
    _alice, project, alice_headers = facilitator
    session_id = await new_session(client, alice_headers, project.id)

    bob = await make_user(db_session, email="bob@example.com")
    await grant_role(db_session, sound_necklace_app.id, bob.id, "facilitator")
    await make_project_user_access(db_session, project.id, bob.id)
    bob_headers = await auth_header(db_session, bob)

    res = await client.post(
        f"{SN}/sessions/{session_id}/consent",
        headers=bob_headers,
        json={"type": "pipeline_use"},
    )

    assert res.status_code == 201, res.text
    assert res.json()["confirmed_by"] == bob.id


# ── Scoping ──────────────────────────────────────────────────────────────────


async def test_a_non_member_cannot_read_the_consents(
    client, db_session, facilitator, sound_necklace_app
):
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)

    outsider = await make_user(db_session, email="outsider@example.com")
    await grant_role(db_session, sound_necklace_app.id, outsider.id, "facilitator")
    outsider_headers = await auth_header(db_session, outsider)

    res = await client.get(f"{SN}/sessions/{session_id}/consent", headers=outsider_headers)

    assert res.status_code == 403


async def test_a_non_member_cannot_record_a_consent(
    client, db_session, facilitator, sound_necklace_app
):
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)

    outsider = await make_user(db_session, email="outsider@example.com")
    await grant_role(db_session, sound_necklace_app.id, outsider.id, "facilitator")
    outsider_headers = await auth_header(db_session, outsider)

    res = await client.post(
        f"{SN}/sessions/{session_id}/consent",
        headers=outsider_headers,
        json={"type": "pipeline_use"},
    )

    assert res.status_code == 403


async def test_recording_a_consent_on_a_session_that_does_not_exist_is_not_found(
    client, facilitator
):
    _user, _project, headers = facilitator

    res = await client.post(
        f"{SN}/sessions/does-not-exist/consent",
        headers=headers,
        json={"type": "pipeline_use"},
    )

    assert res.status_code == 404


async def test_an_unknown_consent_type_is_refused(client, facilitator):
    """The enum backs a database column — an unknown value is a 422, never an insert."""
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)

    res = await client.post(
        f"{SN}/sessions/{session_id}/consent",
        headers=headers,
        json={"type": "whatever_the_client_felt_like"},
    )

    assert res.status_code == 422


# ── Survival ─────────────────────────────────────────────────────────────────


async def test_deleting_the_session_takes_its_consents(client, facilitator, db_session):
    """Cascade, so a deleted session leaves no orphan record behind."""
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)

    await db_session.execute(delete(SnSession).where(SnSession.id == session_id))
    await db_session.commit()

    remaining = (
        (await db_session.execute(select(SnConsent).where(SnConsent.session_id == session_id)))
        .scalars()
        .all()
    )
    assert remaining == []


async def test_deleting_the_confirming_user_keeps_the_record(
    client, db_session, facilitator, sound_necklace_app
):
    """The evidence outlives the operator who typed it.

    Alice opens the session; Bob re-confirms. Deleting Bob must not take the consent —
    Alice's session is still standing, and under CASCADE the proof would vanish with no
    session deletion to explain it. SET NULL keeps the record and says honestly that the
    confirming account is gone.
    """
    _alice, project, alice_headers = facilitator
    session_id = await new_session(client, alice_headers, project.id)

    bob = await make_user(db_session, email="bob@example.com")
    await grant_role(db_session, sound_necklace_app.id, bob.id, "facilitator")
    await make_project_user_access(db_session, project.id, bob.id)
    bob_headers = await auth_header(db_session, bob)
    await client.post(
        f"{SN}/sessions/{session_id}/consent",
        headers=bob_headers,
        json={"type": "pipeline_use"},
    )

    await db_session.execute(delete(User).where(User.id == bob.id))
    await db_session.commit()

    rows = (
        (await db_session.execute(select(SnConsent).where(SnConsent.session_id == session_id)))
        .scalars()
        .all()
    )
    assert len(rows) == 1, "deleting the confirming user destroyed the consent evidence"
    assert rows[0].confirmed_by is None
    assert rows[0].type is ConsentType.PIPELINE_USE


# ── The wire ─────────────────────────────────────────────────────────────────


async def test_the_confirmed_at_on_the_wire_carries_its_offset(client, facilitator):
    """A legal record's "when" must be an unambiguous instant on either database.

    Postgres reads a timestamptz back aware and SQLite naive, so a bare isoformat() would
    ship an offset in production and a bare local-looking string under test.
    """
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)

    res = await client.get(f"{SN}/sessions/{session_id}/consent", headers=headers)

    (record,) = res.json()["consents"]
    assert datetime.fromisoformat(record["confirmed_at"]).tzinfo is not None


async def test_the_type_is_stored_as_its_value_not_its_member_name(client, facilitator, db_session):
    """`values_callable` or the database stores "PIPELINE_USE" — a value the wire never
    uses, and one the SPA's generated types would not match."""
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)

    stored = (
        await db_session.execute(
            text("SELECT type FROM sn_consents WHERE session_id = :sid"), {"sid": session_id}
        )
    ).scalar_one()

    assert stored == "pipeline_use"
