"""Renaming a session, and deleting one for good.

Two properties carry this file. The first is that a rename is cosmetic: ``slug`` names
all three artifact files (PRD §10.5) and a downstream pipeline diffs them by name, so a
rename that moved the slug would quietly turn an edit of a label into a migration of
objects. Every rename test therefore asserts the slug did not move.

The second is that a delete sweeps only what the session produced. The project's source
audio belongs to the project and outlives every session cut from it; it lives in the
Oral Collector's bucket, reached through ``sn_audio_refs``. The delete tests seed one
into the fake bucket and assert it is still there afterwards — the sweep is driven off
the session's own rows, never off a bucket prefix, and that is the claim being made.

A sweep driven off the rows can only reach what the rows still point at, which is why
the re-upload tests are here rather than beside the other artifact ones. An artifact key
is content-addressed, so re-exporting with changed bytes writes a *second* object and
moves the pointer; the predecessor is then unreferenced and no later delete can name it.
These tests therefore assert on what the bucket still holds, not on which keys the sweep
named — the previous suite passed while three superseded objects survived a delete.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.db.models.sound_necklace import (
    SnAnswerTranscript,
    SnArtifact,
    SnConsent,
    SnSessionState,
    SnSessionTick,
    SnVoiceAnswer,
)
from app.services.oral_collector import gcs_utils
from tests.baker import make_user
from tests.test_sound_necklace.conftest import (
    auth_header,
    grant_role,
    hand_lease_to,
    new_session,
)

SN = "/api/sound-necklace"

WEBM = b"\x1a\x45\xdf\xa3 fake webm/opus bytes \x00\x01\x02"
P1 = "respostas/level1/recontar.webm"
P2 = "respostas/level2/PT3/quem.webm"

# The project's source audio, as the Oral Collector stores it. Not in the Sound
# Necklace's bucket and not reachable from any session row — which is precisely why a
# sweep driven off a prefix would take it and a sweep driven off the rows cannot.
PROJECT_AUDIO_KEY = "oral-collector/audios/aud-source-recording.wav"

JSON = "application/json"
ARTIFACT_PAYLOADS = {
    "manifest": (b'{"manifest_id":"fnv1a32:d31a8419"}', "manifesto-contas.json", JSON),
    "anchoring": (b'{"scenes":[]}', "retorno-ancoragem.json", JSON),
    "report": ("# Relatório\n".encode(), "relatorio-mapeamento.md", "text/markdown"),
}

# A second export in which only the report changed. The report is the one that carries
# the storyteller's transcript and translation, so it is the artifact whose superseded
# copy matters most; leaving the other two untouched keeps their keys identical, which is
# the case a naive "delete the old key" gets wrong.
REVISED_REPORT = "# Relatório revisado\n".encode()
REVISED_PAYLOADS = {
    **ARTIFACT_PAYLOADS,
    "report": (REVISED_REPORT, "relatorio-mapeamento.md", "text/markdown"),
}


@pytest.fixture()
def storage(monkeypatch):
    """A fake bucket that remembers what was deleted from it.

    ``deleted`` is the observable effect this feature exists to produce: the sweep's
    whole job is to move objects out of storage, and which keys it named is the only
    place that claim can be read. The project's source audio is seeded in ``objects`` so
    a test can watch it survive.
    """

    class FakeStorage:
        def __init__(self) -> None:
            self.objects: dict[str, bytes] = {PROJECT_AUDIO_KEY: b"the project's own audio"}
            self.signed: list[dict] = []
            self.deleted: list[str] = []
            self.deleted_buckets: set[str] = set()

        async def upload(
            self, bucket: str, key: str, data: bytes, content_type: str, *, content_encoding=None
        ) -> str:
            self.objects[key] = data
            return f"gs://{bucket}/{key}"

        async def sign(
            self, bucket: str, key: str, *, expiry_minutes: int = 15, response_content_type=None
        ) -> str:
            self.signed.append({"bucket": bucket, "key": key, "ttl": expiry_minutes})
            return f"https://storage.googleapis.com/{bucket}/{key}?X-Goog-Signature=beef"

        async def delete(self, bucket: str, key: str) -> None:
            self.deleted.append(key)
            self.deleted_buckets.add(bucket)
            self.objects.pop(key, None)

        def session_keys(self) -> set[str]:
            """Everything in the bucket that this session put there."""
            return set(self.objects) - {PROJECT_AUDIO_KEY}

    fake = FakeStorage()
    monkeypatch.setattr(gcs_utils, "upload_gcs_object", fake.upload)
    monkeypatch.setattr(gcs_utils, "generate_signed_download_url", fake.sign)
    monkeypatch.setattr(gcs_utils, "delete_gcs_object", fake.delete)
    return fake


@pytest.fixture()
async def stranger(db_session, sound_necklace_app):
    """A sound-necklace user with no access to the project under test."""
    user = await make_user(db_session, email="stranger@example.com")
    await grant_role(db_session, sound_necklace_app.id, user.id, "facilitator")
    return user, await auth_header(db_session, user)


@pytest.fixture()
async def auditor(db_session, sound_necklace_app, project):
    """The only role that may read the audit trail."""
    from tests.baker import make_project_user_access

    user = await make_user(db_session, email="auditor@example.com")
    await grant_role(db_session, sound_necklace_app.id, user.id, "project_admin")
    await make_project_user_access(db_session, project.id, user.id)
    return user, await auth_header(db_session, user)


async def put_answer(client, headers, session_id: str, path: str):
    res = await client.put(
        f"{SN}/sessions/{session_id}/resources",
        headers={**headers, "content-type": "audio/webm"},
        params={"path": path},
        content=WEBM,
    )
    assert res.status_code == 201, res.text
    return res


async def put_artifacts(client, headers, session_id: str, payloads: dict | None = None):
    triple = payloads or ARTIFACT_PAYLOADS
    files = {kind: (name, data, ctype) for kind, (data, name, ctype) in triple.items()}
    res = await client.post(f"{SN}/sessions/{session_id}/artifacts", headers=headers, files=files)
    assert res.status_code in (200, 201), res.text
    return res


async def served(client, headers, session_id: str, kind: str, storage) -> tuple[str, bytes]:
    """The key the row points at now, and the bytes a client following the redirect gets.

    Reading through the download route rather than the table is what makes the second
    half of the tuple meaningful: it is the object still sitting in the bucket under the
    key the API just signed, so a pointer left aimed at a deleted object raises here.
    """
    res = await client.get(
        f"{SN}/sessions/{session_id}/artifacts/{kind}", headers=headers, follow_redirects=False
    )
    assert res.status_code == 307, f"{kind}: {res.text}"
    key = storage.signed[-1]["key"]
    return key, storage.objects[key]


async def rows_for(db_session, model, session_id: str) -> int:
    return (
        await db_session.execute(
            select(func.count()).select_from(model).where(model.session_id == session_id)
        )
    ).scalar_one()


async def fully_furnished(client, db_session, headers, project_id: str) -> str:
    """A session carrying one of everything a delete has to take with it.

    The transcript draft is inserted directly: the route that produces one runs a
    transcription, which is not what these tests are about. Everything else goes in
    through its own endpoint.
    """
    session_id = await new_session(client, headers, project_id)

    await client.put(
        f"{SN}/sessions/{session_id}/state",
        headers=headers,
        json={"schema_version": 1, "notes": "em progresso"},
    )
    await client.post(
        f"{SN}/sessions/{session_id}/working-time/ticks",
        headers=headers,
        json={"client_tick_id": "tick-1"},
    )
    await client.post(
        f"{SN}/sessions/{session_id}/consent", headers=headers, json={"type": "voice_answers"}
    )
    await put_answer(client, headers, session_id, P1)
    await put_answer(client, headers, session_id, P2)
    await put_artifacts(client, headers, session_id)

    db_session.add(
        SnAnswerTranscript(session_id=session_id, resource_path=P1, language="por", generation=0)
    )
    await db_session.commit()

    return session_id


# ── Rename ───────────────────────────────────────────────────────────────────


async def test_a_renamed_session_reports_its_new_name_and_keeps_its_slug(client, alice, project):
    """The slug is frozen on purpose: it names the three artifact files, and moving it
    would turn a cosmetic edit into an object migration. The name itself is Terena, so
    this doubles as the round-trip that a non-ASCII story name survives unchanged."""
    _user, headers = alice
    session_id = await new_session(client, headers, project.id)
    before = (await client.get(f"{SN}/sessions/{session_id}", headers=headers)).json()

    res = await client.patch(
        f"{SN}/sessions/{session_id}", headers=headers, json={"story_name": "Ôkovo Éxina Kaxé"}
    )

    assert res.status_code == 200, res.text
    fetched = (await client.get(f"{SN}/sessions/{session_id}", headers=headers)).json()
    assert fetched["story_name"] == "Ôkovo Éxina Kaxé"
    assert fetched["story_slug"] == before["story_slug"]

    listing = (await client.get(f"{SN}/sessions", headers=headers)).json()["sessions"]
    listed = next(s for s in listing if s["id"] == session_id)
    assert listed["story_name"] == "Ôkovo Éxina Kaxé"
    assert listed["story_slug"] == before["story_slug"]


@pytest.mark.parametrize("blank", ["", "   "])
async def test_a_blank_name_is_refused_and_changes_nothing(client, alice, project, blank):
    _user, headers = alice
    session_id = await new_session(client, headers, project.id)
    original = (await client.get(f"{SN}/sessions/{session_id}", headers=headers)).json()[
        "story_name"
    ]

    res = await client.patch(
        f"{SN}/sessions/{session_id}", headers=headers, json={"story_name": blank}
    )

    assert res.status_code == 422, res.text
    after = (await client.get(f"{SN}/sessions/{session_id}", headers=headers)).json()
    assert after["story_name"] == original


async def test_a_name_is_stored_without_its_surrounding_whitespace(client, alice, project):
    _user, headers = alice
    session_id = await new_session(client, headers, project.id)

    res = await client.patch(
        f"{SN}/sessions/{session_id}", headers=headers, json={"story_name": "  Ana  "}
    )

    assert res.status_code == 200, res.text
    fetched = await client.get(f"{SN}/sessions/{session_id}", headers=headers)
    assert fetched.json()["story_name"] == "Ana"


async def test_renaming_to_the_same_name_is_an_ordinary_write(client, alice, project):
    _user, headers = alice
    session_id = await new_session(client, headers, project.id)
    current = (await client.get(f"{SN}/sessions/{session_id}", headers=headers)).json()

    res = await client.patch(
        f"{SN}/sessions/{session_id}", headers=headers, json={"story_name": current["story_name"]}
    )

    assert res.status_code == 200, res.text
    after = (await client.get(f"{SN}/sessions/{session_id}", headers=headers)).json()
    assert after["story_name"] == current["story_name"]
    assert after["story_slug"] == current["story_slug"]


async def test_renaming_a_session_someone_else_holds_is_refused(
    client, db_session, alice, bob, project
):
    _alice, alice_headers = alice
    bob_user, _bob_headers = bob
    session_id = await new_session(client, alice_headers, project.id)
    original = (await client.get(f"{SN}/sessions/{session_id}", headers=alice_headers)).json()[
        "story_name"
    ]
    await hand_lease_to(db_session, session_id, bob_user.id)

    res = await client.patch(
        f"{SN}/sessions/{session_id}", headers=alice_headers, json={"story_name": "Nome Novo"}
    )

    assert res.status_code == 409, res.text
    assert res.json()["code"] == "SESSION_LOCKED"
    after = (await client.get(f"{SN}/sessions/{session_id}", headers=alice_headers)).json()
    assert after["story_name"] == original


# ── Delete ───────────────────────────────────────────────────────────────────


async def test_deleting_a_session_sweeps_exactly_its_own_objects(
    client, db_session, alice, project, storage
):
    """The safety property of the whole issue. The five objects the session produced go;
    the project's source audio, which outlives every session cut from it, stays."""
    _user, headers = alice
    session_id = await new_session(client, headers, project.id)
    await put_answer(client, headers, session_id, P1)
    await put_answer(client, headers, session_id, P2)
    await put_artifacts(client, headers, session_id)
    produced = storage.session_keys()
    assert len(produced) == 5, produced

    res = await client.delete(f"{SN}/sessions/{session_id}", headers=headers)

    assert res.status_code == 204, res.text
    assert sorted(storage.deleted) == sorted(produced)
    assert PROJECT_AUDIO_KEY not in storage.deleted
    assert PROJECT_AUDIO_KEY in storage.objects
    assert storage.deleted_buckets == {"sound-necklace-private"}


async def test_a_session_that_produced_nothing_still_deletes(client, alice, project, storage):
    """Nothing to sweep is not nothing to do — the session itself still goes."""
    _user, headers = alice
    session_id = await new_session(client, headers, project.id)

    res = await client.delete(f"{SN}/sessions/{session_id}", headers=headers)

    assert res.status_code == 204, res.text
    assert storage.deleted == []
    assert (await client.get(f"{SN}/sessions/{session_id}", headers=headers)).status_code == 404


async def test_a_deleted_session_and_everything_under_it_is_gone(
    client, db_session, alice, project, storage
):
    _user, headers = alice
    session_id = await fully_furnished(client, db_session, headers, project.id)

    res = await client.delete(f"{SN}/sessions/{session_id}", headers=headers)

    assert res.status_code == 204, res.text
    assert (await client.get(f"{SN}/sessions/{session_id}", headers=headers)).status_code == 404
    listing = (await client.get(f"{SN}/sessions", headers=headers)).json()["sessions"]
    assert all(s["id"] != session_id for s in listing)

    for model in (
        SnSessionState,
        SnSessionTick,
        SnArtifact,
        SnVoiceAnswer,
        SnConsent,
        SnAnswerTranscript,
    ):
        assert await rows_for(db_session, model, session_id) == 0, model.__name__


async def test_the_audit_trail_outlives_the_session(
    client, db_session, alice, auditor, project, storage
):
    """§12: the trail records who reached whose voice, and deleting the session does not
    unrecord it. The event's session_id is SET NULL, not cascaded — it keeps naming its
    project, which is how the log is read."""
    _user, headers = alice
    _admin, admin_headers = auditor
    session_id = await new_session(client, headers, project.id)
    await put_artifacts(client, headers, session_id)
    issued = await client.get(
        f"{SN}/sessions/{session_id}/artifacts/manifest", headers=headers, follow_redirects=False
    )
    assert issued.status_code == 307, issued.text

    res = await client.delete(f"{SN}/sessions/{session_id}", headers=headers)
    assert res.status_code == 204, res.text

    trail = await client.get(f"{SN}/projects/{project.id}/audit", headers=admin_headers)
    assert trail.status_code == 200, trail.text
    events = trail.json()["events"]
    assert any(
        e["event"] == "artifact_url_issued" and e["resource_ref"] == "manifest" for e in events
    )


async def test_a_completed_session_deletes_the_same_way(
    client, db_session, alice, project, storage
):
    _user, headers = alice
    session_id = await fully_furnished(client, db_session, headers, project.id)
    completed = await client.post(f"{SN}/sessions/{session_id}/complete", headers=headers)
    assert completed.status_code == 200, completed.text

    res = await client.delete(f"{SN}/sessions/{session_id}", headers=headers)

    assert res.status_code == 204, res.text
    assert (await client.get(f"{SN}/sessions/{session_id}", headers=headers)).status_code == 404
    listing = (await client.get(f"{SN}/sessions", headers=headers)).json()["sessions"]
    assert all(s["id"] != session_id for s in listing)

    for model in (
        SnSessionState,
        SnSessionTick,
        SnArtifact,
        SnVoiceAnswer,
        SnConsent,
        SnAnswerTranscript,
    ):
        assert await rows_for(db_session, model, session_id) == 0, model.__name__


# ── A re-upload takes its predecessor with it ────────────────────────────────


async def test_reuploading_an_artifact_removes_the_copy_it_replaced(
    client, alice, project, storage
):
    """Re-exporting is reachable through the ordinary reopen-and-re-complete flow, and
    the key is content-addressed, so changed bytes write a new object and move the
    pointer. The predecessor is then referenced by nothing — not by the row, and so not
    by any later sweep — and would sit in the bucket for good."""
    _user, headers = alice
    session_id = await new_session(client, headers, project.id)
    await put_artifacts(client, headers, session_id)
    superseded_key, _ = await served(client, headers, session_id, "report", storage)

    await put_artifacts(client, headers, session_id, REVISED_PAYLOADS)

    current_key, current = await served(client, headers, session_id, "report", storage)
    assert current_key != superseded_key
    assert current == REVISED_REPORT
    assert superseded_key not in storage.objects, "the replaced report is still in the bucket"


async def test_reuploading_identical_bytes_destroys_nothing(client, alice, project, storage):
    """The sharp edge of the fix. The key is a content hash, so re-exporting the same
    bytes produces the *same* key: the object an unguarded "delete the old key" would
    remove is the one it has just written and the row now points at."""
    _user, headers = alice
    session_id = await new_session(client, headers, project.id)
    await put_artifacts(client, headers, session_id)
    key, before = await served(client, headers, session_id, "report", storage)

    await put_artifacts(client, headers, session_id)

    assert key in storage.objects, "the re-upload deleted the object it had just written"
    key_again, after = await served(client, headers, session_id, "report", storage)
    assert key_again == key
    assert after == before


async def test_a_delete_after_a_reupload_leaves_nothing_of_the_session_behind(
    client, alice, project, storage
):
    """The gap that let the delete tests pass while objects survived. Asserting on what
    the sweep named cannot see it — the superseded object is exactly the one no row
    names — so this asserts on what the bucket still holds, and the project's own audio
    is the only thing allowed to be left."""
    _user, headers = alice
    session_id = await new_session(client, headers, project.id)
    await put_answer(client, headers, session_id, P1)
    await put_artifacts(client, headers, session_id)
    await put_artifacts(client, headers, session_id, REVISED_PAYLOADS)

    res = await client.delete(f"{SN}/sessions/{session_id}", headers=headers)

    assert res.status_code == 204, res.text
    assert storage.session_keys() == set()
    assert PROJECT_AUDIO_KEY in storage.objects
    assert storage.deleted_buckets == {"sound-necklace-private"}


# ── Who may do either ────────────────────────────────────────────────────────


async def test_a_stranger_can_neither_rename_nor_delete(client, alice, stranger, project, storage):
    _user, headers = alice
    _outsider, outsider_headers = stranger
    session_id = await new_session(client, headers, project.id)
    original = (await client.get(f"{SN}/sessions/{session_id}", headers=headers)).json()[
        "story_name"
    ]

    renamed = await client.patch(
        f"{SN}/sessions/{session_id}", headers=outsider_headers, json={"story_name": "Meu Agora"}
    )
    removed = await client.delete(f"{SN}/sessions/{session_id}", headers=outsider_headers)

    assert renamed.status_code == 403, renamed.text
    assert removed.status_code == 403, removed.text
    assert storage.deleted == []
    still_there = await client.get(f"{SN}/sessions/{session_id}", headers=headers)
    assert still_there.status_code == 200
    assert still_there.json()["story_name"] == original


async def test_deleting_a_session_someone_else_holds_is_refused_and_sweeps_nothing(
    client, db_session, alice, bob, project, storage
):
    """The lease is fenced before the sweep, not after. An empty ``deleted`` list is the
    only way to tell those two orders apart: both refuse, but one has already destroyed
    the recordings by the time it does."""
    _alice, alice_headers = alice
    bob_user, _bob_headers = bob
    session_id = await new_session(client, alice_headers, project.id)
    await put_answer(client, alice_headers, session_id, P1)
    await put_artifacts(client, alice_headers, session_id)
    await hand_lease_to(db_session, session_id, bob_user.id)

    res = await client.delete(f"{SN}/sessions/{session_id}", headers=alice_headers)

    assert res.status_code == 409, res.text
    assert res.json()["code"] == "SESSION_LOCKED"
    assert storage.deleted == []
    assert (
        await client.get(f"{SN}/sessions/{session_id}", headers=alice_headers)
    ).status_code == 200
