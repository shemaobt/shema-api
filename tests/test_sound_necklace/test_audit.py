"""The persisted audit log: who reached whose voice, and when (§12).

What the API can honestly record is that it ISSUED a signed URL. The bytes never pass
through it — storage serves them directly — so it never sees a download happen. A URL may
be used once, ten times, or never. The event names say issuance and nothing more.

The other half of §12 is what must NOT be here: the listener's behaviour is never logged
(§14). Only facilitator-account actions on protected resources.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text

from app.db.models.sound_necklace import AuditEvent, SnAuditEvent
from tests.baker import make_language, make_project, make_project_user_access, make_user
from tests.test_sound_necklace.conftest import (
    audio_of,
    auth_header,
    give_project_an_audio,
    grant_role,
)

SN = "/api/sound-necklace"


@pytest.fixture()
def audio_url_patch(monkeypatch):
    """The signing call, stubbed. These tests are about what gets recorded, not GCS."""

    async def _signed(bucket, key, expiry_minutes=15):
        return f"https://storage.example/{bucket}/{key}?sig=x"

    async def _upload(bucket, key, data, content_type):
        return None

    from app.services.oral_collector import gcs_utils

    monkeypatch.setattr(gcs_utils, "generate_signed_download_url", _signed)
    monkeypatch.setattr(gcs_utils, "upload_gcs_object", _upload)


def _patch_audio_url(monkeypatch):
    """Stub the acousteme lookup the audio URL delegates to. Patched on the module the
    service imported, which is the object it actually reaches through at call time."""
    from app.services.oral_collector import acousteme_service

    class _Audio:
        download_url = "https://storage.example/x?sig=y"

    async def _get_audio_url(db, audio_id):
        return _Audio()

    monkeypatch.setattr(acousteme_service, "get_audio_url", _get_audio_url)


@pytest.fixture()
async def facilitator(db_session, sound_necklace_app):
    user = await make_user(db_session, email="facilitator@example.com")
    await grant_role(db_session, sound_necklace_app.id, user.id, "facilitator")
    language = await make_language(db_session, name="Nheengatu", code="yrl")
    project = await make_project(db_session, language.id, name="Projeto A")
    await give_project_an_audio(db_session, project.id)
    await make_project_user_access(db_session, project.id, user.id)
    headers = await auth_header(db_session, user)
    return user, project, headers


@pytest.fixture()
async def project_admin(db_session, sound_necklace_app, facilitator):
    """The only role that may read the log — an auditor, not an editor."""
    _user, project, _headers = facilitator
    user = await make_user(db_session, email="admin@example.com")
    await grant_role(db_session, sound_necklace_app.id, user.id, "project_admin")
    await make_project_user_access(db_session, project.id, user.id)
    return user, await auth_header(db_session, user)


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


async def events(db_session, event: AuditEvent | None = None) -> list[SnAuditEvent]:
    stmt = select(SnAuditEvent).order_by(SnAuditEvent.occurred_at)
    if event is not None:
        stmt = stmt.where(SnAuditEvent.event == event)
    return list((await db_session.execute(stmt)).scalars().all())


async def upload_artifacts(client, headers, session_id: str):
    return await client.post(
        f"{SN}/sessions/{session_id}/artifacts",
        headers=headers,
        files={
            "manifest": ("manifesto-contas.json", io.BytesIO(b'{"a":1}'), "application/json"),
            "anchoring": ("retorno-ancoragem.json", io.BytesIO(b'{"b":2}'), "application/json"),
            "report": ("relatorio-mapeamento.md", io.BytesIO(b"# r"), "text/markdown"),
        },
    )


# ── Each hooked endpoint writes exactly one event ────────────────────────────


async def test_issuing_an_audio_url_is_recorded(client, facilitator, db_session, monkeypatch):
    _user, project, headers = facilitator
    await db_session.execute(
        text("INSERT INTO sn_audio_refs (audio_id, project_id, consent_present) VALUES (:a,:p,1)"),
        {"a": "aud_1", "p": project.id},
    )
    await db_session.commit()

    _patch_audio_url(monkeypatch)

    res = await client.get(f"{SN}/audios/aud_1/url", headers=headers)

    assert res.status_code == 200, res.text
    (event,) = await events(db_session, AuditEvent.AUDIO_URL_ISSUED)
    assert event.user_id == _user.id
    assert event.project_id == project.id
    assert event.resource_ref == "aud_1"
    # An audio is not reached through a session — the story exists before any pass over it.
    assert event.session_id is None


async def test_issuing_an_artifact_url_is_recorded(
    client, facilitator, db_session, audio_url_patch
):
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)
    await upload_artifacts(client, headers, session_id)

    res = await client.get(f"{SN}/sessions/{session_id}/artifacts/manifest", headers=headers)

    assert res.status_code == 307, res.text
    (event,) = await events(db_session, AuditEvent.ARTIFACT_URL_ISSUED)
    assert event.user_id == _user.id
    assert event.project_id == project.id
    assert event.session_id == session_id
    assert event.resource_ref == "manifest"


async def test_uploading_artifacts_is_recorded_once_for_the_triple(
    client, facilitator, db_session, audio_url_patch
):
    """The one event that records a real byte transfer — the bytes do pass through here.

    One event, not three: the upload is atomic (§10.5) and a partial triple is never
    stored, so three rows would describe three transfers that cannot happen apart.
    """
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)

    res = await upload_artifacts(client, headers, session_id)

    assert res.status_code == 201, res.text
    (event,) = await events(db_session, AuditEvent.ARTIFACT_UPLOADED)
    assert event.session_id == session_id
    assert event.project_id == project.id
    # The ref is the three kinds in the same vocabulary artifact_url_issued uses (kind
    # values), sorted and joined — derived from what was stored, not a literal that could
    # drift from the kinds or from the download event's words.
    assert event.resource_ref == "anchoring,manifest,report"


async def test_issuing_a_voice_url_is_recorded(client, facilitator, db_session, audio_url_patch):
    """The listener's own voice. This is the reach §12 most wants a record of."""
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)
    path = "respostas/level1/quem_conta.webm"
    await client.put(
        f"{SN}/sessions/{session_id}/resources",
        headers=headers,
        params={"path": path},
        content=b"x",
    )

    res = await client.get(
        f"{SN}/sessions/{session_id}/resources/url", headers=headers, params={"path": path}
    )

    assert res.status_code == 200, res.text
    (event,) = await events(db_session, AuditEvent.VOICE_URL_ISSUED)
    assert event.user_id == _user.id
    assert event.session_id == session_id
    assert event.resource_ref == path


async def test_completing_and_reopening_are_recorded(
    client, facilitator, db_session, audio_url_patch
):
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)

    await client.post(f"{SN}/sessions/{session_id}/complete", headers=headers)
    await client.post(f"{SN}/sessions/{session_id}/reopen", headers=headers)

    (completed,) = await events(db_session, AuditEvent.SESSION_COMPLETED)
    (reopened,) = await events(db_session, AuditEvent.SESSION_REOPENED)
    assert completed.session_id == session_id
    assert completed.project_id == project.id
    assert reopened.session_id == session_id


async def test_recording_a_consent_is_recorded(client, facilitator, db_session):
    """The consent record is the evidence; this is the trail of who filed it."""
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id, consent=False)

    await client.post(
        f"{SN}/sessions/{session_id}/consent", headers=headers, json={"type": "voice_answers"}
    )

    (event,) = await events(db_session, AuditEvent.CONSENT_RECORDED)
    assert event.user_id == _user.id
    assert event.session_id == session_id
    assert event.resource_ref == "voice_answers"


async def test_creating_a_session_with_consent_records_the_consent_event(
    client, facilitator, db_session
):
    """The embedded consent is a consent filed just as much as the explicit one."""
    _user, project, headers = facilitator
    await new_session(client, headers, project.id, consent=True)

    (event,) = await events(db_session, AuditEvent.CONSENT_RECORDED)
    assert event.resource_ref == "pipeline_use"


# ── The event survives the request ───────────────────────────────────────────


async def test_the_event_is_committed_not_merely_added(client, facilitator):
    """Written, not just pending — the audit has to outlive the request.

    get_db never commits: it yields a session and closing it rolls back. A hook that only
    db.add()s therefore records nothing in production, while every assertion made through
    the test's own session still passes, because the row is sitting right there in it.
    Reading through a SEPARATE connection is the only thing that tells the two apart.
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    from tests.conftest import TEST_DATABASE_URL

    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id, consent=False)

    res = await client.post(
        f"{SN}/sessions/{session_id}/consent", headers=headers, json={"type": "pipeline_use"}
    )
    assert res.status_code == 201, res.text

    engine = create_async_engine(TEST_DATABASE_URL)
    try:
        async with engine.connect() as conn:
            written = (
                await conn.execute(
                    text("SELECT COUNT(*) FROM sn_audit_events WHERE event = 'consent_recorded'")
                )
            ).scalar_one()
    finally:
        await engine.dispose()

    assert written == 1, "the audit event was never committed — get_db rolls it back"


# ── What must NOT be logged (§14) ────────────────────────────────────────────


async def test_reading_a_session_and_autosaving_write_no_audit_event(
    client, facilitator, db_session, audio_url_patch
):
    """The listener's work is never surveilled (§14).

    Reading a session and autosaving are what a pass over a story IS — the equivalent of
    watching someone work. §12 asks for a record of reaching protected voice, not of
    somebody doing their job.

    Uploading a voice answer is the sharpest case, and the one this test exists to pin:
    it is the listener recording their own voice. Issuing the URL to play it back IS
    logged — that is a reach for the voice — but storing it is not, because that is the
    listener at work. Without the PUT below, nothing here defends that distinction, and a
    hook added to store_voice_answer would pass every other test in this file.
    """
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id, consent=False)
    before = len(await events(db_session))

    await client.get(f"{SN}/sessions/{session_id}", headers=headers)
    await client.get(f"{SN}/sessions", headers=headers)
    await client.get(f"{SN}/sessions/{session_id}/state", headers=headers)
    await client.put(
        f"{SN}/sessions/{session_id}/state",
        headers=headers,
        json={"schema_version": 1, "mode": "escuta"},
    )
    await client.put(
        f"{SN}/sessions/{session_id}/resources",
        headers=headers,
        params={"path": "respostas/level1/quem_conta.webm"},
        content=b"x",
    )
    await client.get(f"{SN}/projects/{project.id}/audios", headers=headers)
    await client.get(f"{SN}/sessions/{session_id}/resources", headers=headers)
    await client.get(f"{SN}/sessions/{session_id}/consent", headers=headers)

    assert len(await events(db_session)) == before, "a listener-equivalent path was logged"


async def test_the_lock_heartbeat_writes_no_audit_event(client, facilitator, db_session):
    """The lock is pinned separately because it is the worst thing to get wrong here.

    The SPA heartbeats PUT /lock every 15 seconds against a 60s lease. A hook there would
    write 240 rows an hour per session, and what those rows would describe is precisely
    when the listener was at work and for how long — the §14 surveillance, recorded at a
    resolution nothing else in this app comes close to, plus a table that grows forever.
    """
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id, consent=False)
    before = len(await events(db_session))

    await client.put(f"{SN}/sessions/{session_id}/lock", headers=headers)
    await client.put(f"{SN}/sessions/{session_id}/lock", headers=headers)
    await client.get(f"{SN}/sessions/{session_id}/lock", headers=headers)
    await client.delete(f"{SN}/sessions/{session_id}/lock", headers=headers)

    assert len(await events(db_session)) == before, "the lock heartbeat is being logged"


# ── The query route ──────────────────────────────────────────────────────────


async def test_the_log_is_readable_by_a_project_admin(
    client, facilitator, project_admin, db_session
):
    _user, project, headers = facilitator
    await new_session(client, headers, project.id, consent=True)
    _admin, admin_headers = project_admin

    res = await client.get(f"{SN}/projects/{project.id}/audit", headers=admin_headers)

    assert res.status_code == 200, res.text
    (event,) = res.json()["events"]
    assert event["event"] == "consent_recorded"
    assert event["user_id"] == _user.id


async def test_a_facilitator_cannot_read_the_log(client, facilitator):
    """Auditing is not part of doing the work — a facilitator reading who reached what
    is the surveillance §14 forbids, one step removed."""
    _user, project, headers = facilitator

    res = await client.get(f"{SN}/projects/{project.id}/audit", headers=headers)

    assert res.status_code == 403


async def test_an_admin_of_another_project_cannot_read_this_log(
    client, db_session, facilitator, sound_necklace_app
):
    """The role is not the gate on its own — project membership still is."""
    _user, project, _headers = facilitator
    outsider = await make_user(db_session, email="outsider-admin@example.com")
    await grant_role(db_session, sound_necklace_app.id, outsider.id, "project_admin")
    outsider_headers = await auth_header(db_session, outsider)

    res = await client.get(f"{SN}/projects/{project.id}/audit", headers=outsider_headers)

    assert res.status_code == 403


async def test_the_log_only_shows_this_projects_events(
    client, db_session, facilitator, project_admin, sound_necklace_app
):
    """A log scoped to a project must not leak another project's reach."""
    _user, project, headers = facilitator
    _admin, admin_headers = project_admin

    language = await make_language(db_session, name="Outra", code="oth")
    other = await make_project(db_session, language.id, name="Projeto B")
    await give_project_an_audio(db_session, other.id)
    await make_project_user_access(db_session, other.id, _user.id)
    await new_session(client, headers, other.id, consent=True)

    res = await client.get(f"{SN}/projects/{project.id}/audit", headers=admin_headers)

    assert res.status_code == 200, res.text
    assert res.json()["events"] == []


async def test_the_log_filters_by_event(client, facilitator, project_admin, db_session):
    _user, project, headers = facilitator
    _admin, admin_headers = project_admin
    session_id = await new_session(client, headers, project.id, consent=True)
    await client.post(f"{SN}/sessions/{session_id}/complete", headers=headers)

    res = await client.get(
        f"{SN}/projects/{project.id}/audit",
        headers=admin_headers,
        params={"event": "session_completed"},
    )

    assert res.status_code == 200, res.text
    (event,) = res.json()["events"]
    assert event["event"] == "session_completed"


async def test_the_log_filters_by_since(client, facilitator, project_admin, db_session):
    _user, project, headers = facilitator
    _admin, admin_headers = project_admin
    await new_session(client, headers, project.id, consent=True)
    await db_session.execute(
        text("UPDATE sn_audit_events SET occurred_at = :w"), {"w": _long_ago()}
    )
    await db_session.commit()

    res = await client.get(
        f"{SN}/projects/{project.id}/audit",
        headers=admin_headers,
        params={"since": datetime(2024, 1, 1, tzinfo=UTC).isoformat()},
    )

    assert res.status_code == 200, res.text
    assert res.json()["events"] == [], "an event older than `since` was returned"


def _long_ago() -> datetime:
    return datetime(2020, 1, 1, tzinfo=UTC)


async def test_the_log_filters_by_until(client, facilitator, project_admin, db_session):
    """`until` is the upper bound the newest-first view lacks — a historical window (the
    March pilot, say) needs both ends, or raising `since` only ever strips older rows and
    the window's far end stays pinned to now."""
    _user, project, headers = facilitator
    _admin, admin_headers = project_admin
    session_id = await new_session(client, headers, project.id, consent=True)
    await client.post(f"{SN}/sessions/{session_id}/complete", headers=headers)
    # The consent event moves to 2020; the completion stays at "now". `until` in 2021 must
    # keep the first and drop the second — an upper bound, not a lower one, and not inclusive.
    await db_session.execute(
        text("UPDATE sn_audit_events SET occurred_at = :w WHERE event = 'consent_recorded'"),
        {"w": _long_ago()},
    )
    await db_session.commit()

    res = await client.get(
        f"{SN}/projects/{project.id}/audit",
        headers=admin_headers,
        params={"until": datetime(2021, 1, 1, tzinfo=UTC).isoformat()},
    )

    assert res.status_code == 200, res.text
    assert [e["event"] for e in res.json()["events"]] == ["consent_recorded"]


async def test_since_is_normalised_to_utc(client, facilitator, project_admin, db_session):
    """A non-UTC `since` must filter by the same instant on SQLite and Postgres.

    SQLite's datetime bind drops the tzinfo, so a `since` carrying a -03:00 offset would
    filter three hours early under test (and correctly in production) unless it is
    normalised to UTC first. The event sits at 12:00Z; a `since` of 10:00-03:00 is 13:00Z,
    which is AFTER it — so a correctly-normalised filter returns nothing.
    """
    _user, project, headers = facilitator
    _admin, admin_headers = project_admin
    await new_session(client, headers, project.id, consent=True)
    await db_session.execute(
        text("UPDATE sn_audit_events SET occurred_at = :w"),
        {"w": datetime(2026, 6, 1, 12, 0, tzinfo=UTC)},
    )
    await db_session.commit()

    res = await client.get(
        f"{SN}/projects/{project.id}/audit",
        headers=admin_headers,
        params={"since": "2026-06-01T10:00:00-03:00"},
    )

    assert res.status_code == 200, res.text
    assert res.json()["events"] == [], "the -03:00 offset was dropped — filtered by wall clock"


async def test_the_log_is_newest_first(client, facilitator, project_admin, db_session):
    """An auditor asks "what happened lately", so the answer starts with lately."""
    _user, project, headers = facilitator
    _admin, admin_headers = project_admin
    session_id = await new_session(client, headers, project.id, consent=True)
    await client.post(f"{SN}/sessions/{session_id}/complete", headers=headers)

    res = await client.get(f"{SN}/projects/{project.id}/audit", headers=admin_headers)

    kinds = [e["event"] for e in res.json()["events"]]
    assert kinds == ["session_completed", "consent_recorded"]


async def test_the_log_honours_its_limit(client, facilitator, project_admin):
    _user, project, headers = facilitator
    _admin, admin_headers = project_admin
    session_id = await new_session(client, headers, project.id, consent=True)
    await client.post(f"{SN}/sessions/{session_id}/complete", headers=headers)

    res = await client.get(
        f"{SN}/projects/{project.id}/audit", headers=admin_headers, params={"limit": 1}
    )

    assert len(res.json()["events"]) == 1


# ── The wire ─────────────────────────────────────────────────────────────────


async def test_the_event_is_stored_as_its_value_not_its_member_name(
    client, facilitator, db_session
):
    """`values_callable`, or Postgres stores CONSENT_RECORDED and the wire never matches."""
    _user, project, headers = facilitator
    await new_session(client, headers, project.id, consent=True)

    stored = (await db_session.execute(text("SELECT event FROM sn_audit_events"))).scalar_one()

    assert stored == "consent_recorded"


async def test_occurred_at_on_the_wire_carries_its_offset(client, facilitator, project_admin):
    _user, project, headers = facilitator
    _admin, admin_headers = project_admin
    await new_session(client, headers, project.id, consent=True)

    res = await client.get(f"{SN}/projects/{project.id}/audit", headers=admin_headers)

    (event,) = res.json()["events"]
    assert datetime.fromisoformat(event["occurred_at"]).tzinfo is not None


async def test_a_lapsed_window_is_not_an_error(client, facilitator, project_admin):
    """An empty log is an answer, not a failure."""
    _user, project, _headers = facilitator
    _admin, admin_headers = project_admin

    res = await client.get(
        f"{SN}/projects/{project.id}/audit",
        headers=admin_headers,
        params={"since": (datetime.now(UTC) + timedelta(days=1)).isoformat()},
    )

    assert res.status_code == 200
    assert res.json()["events"] == []
