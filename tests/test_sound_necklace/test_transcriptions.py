"""Transcription drafts for the recorded answers (ENG-325).

The job is one pass per answer: transcribe in the language it was spoken, then, if that is
not English, translate. Both outputs are DRAFTS — the API never merges them into an
artifact, a human confirms them in the SPA first.

The state of the job IS the per-answer rows: there is no job table. That is what makes it
idempotent (a ready answer is never paid for twice), resumable (a lost worker leaves
`pending` behind) and partial-failure-proof (one bad answer is one `failed` row, never a
500 and never a blocked report).
"""

from __future__ import annotations

import pytest

from app.core.enums import SnTranscriptionEvent
from app.core.exceptions import UpstreamServiceError
from app.core.inngest_client import inngest_client
from app.services import sound_necklace_service as sn_service
from app.services.oral_collector import gcs_utils
from app.services.sound_necklace import transcribe_answers
from tests.test_sound_necklace.conftest import SN, new_session

WEBM = b"\x1a\x45\xdf\xa3 fake webm/opus bytes"
P1 = "respostas/level1/recontar.webm"
P2 = "respostas/level2/PT3/quem.webm"
P3 = "respostas/level3/P12/oque.webm"


@pytest.fixture()
def storage(monkeypatch):
    """The bucket: answers land in a dict and the job reads them back from it."""

    class FakeStorage:
        def __init__(self) -> None:
            self.objects: dict[str, bytes] = {}

        async def upload(
            self, bucket: str, key: str, data: bytes, content_type: str, *, content_encoding=None
        ) -> str:
            self.objects[key] = data
            return f"gs://{bucket}/{key}"

        async def download(self, bucket: str, key: str) -> bytes:
            return self.objects[key]

        async def delete(self, bucket: str, key: str) -> None:
            self.objects.pop(key, None)

    fake = FakeStorage()
    monkeypatch.setattr(gcs_utils, "upload_gcs_object", fake.upload)
    monkeypatch.setattr(gcs_utils, "download_gcs_object", fake.download)
    monkeypatch.setattr(gcs_utils, "delete_gcs_object", fake.delete)
    return fake


@pytest.fixture()
def no_background(monkeypatch):
    """Swallow the queue event; record which sessions the trigger asked work for."""
    launched: list[str] = []

    async def _fake_request(session_id: str) -> None:
        launched.append(session_id)

    monkeypatch.setattr(sn_service, "request_transcription", _fake_request)
    return launched


class FakeProviders:
    """One STT + one translator, counting every (billed) call."""

    def __init__(self, *, fail_on: str | None = None) -> None:
        self.fail_on = fail_on
        self.transcribed: list[str] = []
        self.translated: list[str] = []

    async def stt(self, audio: bytes, *, language: str, mime_type: str) -> str:
        self.transcribed.append(language)
        if self.fail_on and self.fail_on.encode() in audio:
            raise UpstreamServiceError("Scribe is down")
        return f"transcrição em {language}"

    async def translate(self, text: str, *, source_language: str) -> str:
        self.translated.append(text)
        return f"english of: {text}"


async def record(client, headers, session_id: str, path: str, data: bytes = WEBM) -> None:
    res = await client.put(
        f"{SN}/sessions/{session_id}/resources",
        headers=headers,
        params={"path": path},
        content=data,
    )
    assert res.status_code == 201, res.text


async def start(client, headers, session_id: str, **body):
    return await client.post(
        f"{SN}/sessions/{session_id}/transcriptions",
        headers=headers,
        json={"language": "pt-BR", **body},
    )


async def progress(client, headers, session_id: str) -> dict:
    res = await client.get(f"{SN}/sessions/{session_id}/transcriptions", headers=headers)
    assert res.status_code == 200, res.text
    return dict(res.json())


@pytest.fixture()
async def session_with_answers(client, alice, project, storage):
    _user, headers = alice
    session_id = await new_session(client, headers, project.id)
    for path in (P1, P2, P3):
        await record(client, headers, session_id, path)
    return session_id, headers


async def test_the_trigger_queues_one_pending_draft_per_recorded_answer(
    client, db_session, session_with_answers, no_background
) -> None:
    session_id, headers = session_with_answers

    res = await start(client, headers, session_id)

    assert res.status_code == 202, res.text
    body = res.json()
    assert (body["total"], body["pending"], body["ready"], body["failed"]) == (3, 3, 0, 0)
    assert [a["path"] for a in body["answers"]] == [P1, P2, P3]
    assert no_background == [session_id]


async def test_the_trigger_hands_the_session_to_the_queue(
    client, db_session, session_with_answers, monkeypatch
) -> None:
    """The 202 means queued, not done: the pass runs off the API process.

    Patched at the client, not at the service, so the event that would go on the wire —
    its name and its data — is what gets asserted.
    """
    sent = []

    async def _capture(event) -> list[str]:
        sent.append(event)
        return ["evt-1"]

    monkeypatch.setattr(inngest_client, "send", _capture)
    session_id, headers = session_with_answers

    await start(client, headers, session_id)

    assert [e.name for e in sent] == [SnTranscriptionEvent.REQUESTED]
    assert sent[0].data == {"session_id": session_id}


async def test_a_session_with_nothing_pending_does_not_wake_the_queue(
    client, db_session, alice, project, monkeypatch
) -> None:
    sent = []
    monkeypatch.setattr(inngest_client, "send", lambda event: sent.append(event))
    _user, headers = alice
    session_id = await new_session(client, headers, project.id)

    await start(client, headers, session_id)  # no answers recorded

    assert sent == []


async def test_the_job_leaves_a_transcript_and_a_translation_per_answer(
    client, db_session, session_with_answers, no_background
) -> None:
    session_id, headers = session_with_answers
    await start(client, headers, session_id)
    providers = FakeProviders()

    await sn_service.run_pending(
        db_session, session_id, stt=providers.stt, translator=providers.translate
    )

    body = await progress(client, headers, session_id)
    assert (body["total"], body["ready"], body["failed"], body["pending"]) == (3, 3, 0, 0)
    first = body["answers"][0]
    assert first["transcript_source"] == "transcrição em pt-BR"
    assert first["translation_en"] == "english of: transcrição em pt-BR"
    assert first["error"] is None
    assert providers.transcribed == ["pt-BR"] * 3


async def test_an_english_interview_is_transcribed_but_not_translated(
    client, db_session, session_with_answers, no_background
) -> None:
    session_id, headers = session_with_answers
    await start(client, headers, session_id, language="en-US")
    providers = FakeProviders()

    await sn_service.run_pending(
        db_session, session_id, stt=providers.stt, translator=providers.translate
    )

    body = await progress(client, headers, session_id)
    assert providers.transcribed == ["en-US"] * 3
    assert providers.translated == []  # nothing to translate, so nothing was billed
    # The answer still carries an English text, so the report reads one field either way.
    assert body["answers"][0]["translation_en"] == body["answers"][0]["transcript_source"]


async def test_one_bad_answer_fails_alone_and_blocks_nothing(
    client, db_session, session_with_answers, storage, no_background
) -> None:
    session_id, headers = session_with_answers
    # Make the middle answer the poisoned one.
    await record(client, headers, session_id, P2, b"\x1a\x45\xdf\xa3 poison")
    await start(client, headers, session_id)
    providers = FakeProviders(fail_on="poison")

    await sn_service.run_pending(
        db_session, session_id, stt=providers.stt, translator=providers.translate
    )

    body = await progress(client, headers, session_id)
    assert (body["ready"], body["failed"], body["pending"]) == (2, 1, 0)
    failed = next(a for a in body["answers"] if a["path"] == P2)
    assert failed["status"] == "failed"
    assert "Scribe is down" in failed["error"]
    assert failed["transcript_source"] is None


async def test_a_second_trigger_does_not_pay_for_a_ready_answer_again(
    client, db_session, session_with_answers, no_background
) -> None:
    session_id, headers = session_with_answers
    await start(client, headers, session_id)
    providers = FakeProviders()
    await sn_service.run_pending(
        db_session, session_id, stt=providers.stt, translator=providers.translate
    )

    await start(client, headers, session_id)
    await sn_service.run_pending(
        db_session, session_id, stt=providers.stt, translator=providers.translate
    )

    assert len(providers.transcribed) == 3


async def test_a_failed_answer_is_retried_by_a_plain_trigger(
    client, db_session, session_with_answers, no_background
) -> None:
    session_id, headers = session_with_answers
    await record(client, headers, session_id, P2, b"\x1a\x45\xdf\xa3 poison")
    await start(client, headers, session_id)
    await sn_service.run_pending(
        db_session,
        session_id,
        stt=FakeProviders(fail_on="poison").stt,
        translator=FakeProviders().translate,
    )

    body = await start(client, headers, session_id)
    assert body.json()["pending"] == 1  # only the failed one is queued again

    healed = FakeProviders()
    await sn_service.run_pending(
        db_session, session_id, stt=healed.stt, translator=healed.translate
    )
    after = await progress(client, headers, session_id)
    assert (after["ready"], after["failed"]) == (3, 0)
    assert len(healed.transcribed) == 1


async def test_force_re_transcribes_everything_because_a_take_was_re_recorded(
    client, db_session, session_with_answers, no_background
) -> None:
    session_id, headers = session_with_answers
    await start(client, headers, session_id)
    providers = FakeProviders()
    await sn_service.run_pending(
        db_session, session_id, stt=providers.stt, translator=providers.translate
    )

    forced = await start(client, headers, session_id, force=True)

    assert forced.json()["pending"] == 3
    assert forced.json()["answers"][0]["transcript_source"] is None  # the stale draft is gone
    await sn_service.run_pending(
        db_session, session_id, stt=providers.stt, translator=providers.translate
    )
    assert len(providers.transcribed) == 6


async def test_deleting_the_recording_takes_its_draft_with_it(
    client, db_session, session_with_answers, no_background
) -> None:
    session_id, headers = session_with_answers
    await start(client, headers, session_id)
    await sn_service.run_pending(
        db_session, session_id, stt=FakeProviders().stt, translator=FakeProviders().translate
    )

    res = await client.delete(
        f"{SN}/sessions/{session_id}/resources", headers=headers, params={"path": P2}
    )
    assert res.status_code == 204

    body = await progress(client, headers, session_id)
    assert (body["total"], body["ready"]) == (2, 2)
    assert P2 not in [a["path"] for a in body["answers"]]


async def test_a_session_with_no_answers_reports_an_empty_job(
    client, alice, project, no_background
) -> None:
    _user, headers = alice
    session_id = await new_session(client, headers, project.id)

    body = (await start(client, headers, session_id)).json()

    assert (body["total"], body["pending"], body["answers"]) == (0, 0, [])


async def test_a_stranger_cannot_spend_our_provider_budget(
    client, db_session, session_with_answers, sound_necklace_app, no_background
) -> None:
    from tests.baker import make_language, make_project, make_user
    from tests.test_sound_necklace.conftest import auth_header, grant_role

    session_id, _headers = session_with_answers
    language = await make_language(db_session, name="Guarani", code="gug")
    await make_project(db_session, language.id, name="Outro projeto")
    outsider = await make_user(db_session, email="mallory@example.com", display_name="Mallory")
    await grant_role(db_session, sound_necklace_app.id, outsider.id, "facilitator")
    headers = await auth_header(db_session, outsider)

    assert (await start(client, headers, session_id)).status_code == 403
    res = await client.get(f"{SN}/sessions/{session_id}/transcriptions", headers=headers)
    assert res.status_code == 403
    assert no_background == []


async def test_a_force_that_lands_mid_pass_wins_over_the_take_it_replaced(
    client, db_session, session_with_answers, no_background
) -> None:
    """A re-record while the pass is running must not be overwritten by the old take.

    The pass read its rows and paid for a transcript of the recording that has since been
    replaced. Writing it back would leave `ready` holding a draft of a take that no longer
    exists — and the run the force queued finds nothing pending, so nothing ever heals it.
    """
    session_id, headers = session_with_answers
    await start(client, headers, session_id)
    forced: list[str] = []

    async def stt_then_rerecord(audio: bytes, *, language: str, mime_type: str) -> str:
        if not forced:
            forced.append("once")
            await record(client, headers, session_id, P1, b"\x1a\x45\xdf\xa3 the new take")
            await start(client, headers, session_id, force=True)
        return "transcrição da take velha"

    async def translate(text: str, *, source_language: str) -> str:
        return f"english of: {text}"

    await sn_service.run_pending(
        db_session, session_id, stt=stt_then_rerecord, translator=translate
    )

    body = await progress(client, headers, session_id)
    superseded = next(a for a in body["answers"] if a["path"] == P1)
    assert superseded["status"] == "pending"
    assert superseded["transcript_source"] is None


async def test_a_double_submit_is_answered_twice_not_crashed_once(
    client, db_session, session_with_answers, no_background, monkeypatch
) -> None:
    """Two triggers landing together must both get an answer.

    Both read before either commits, so both try to insert the same row and the loser
    hits the composite primary key. Seeding a draft somebody else just seeded is the
    caller's goal already met, not an error to hand back as a 500.

    The stale read is injected rather than raced: two live sessions against SQLite is what
    the project_health concurrency tests had to skip for.
    """
    session_id, headers = session_with_answers
    await start(client, headers, session_id)

    async def _stale_read(db, session_id: str) -> dict:
        return {}

    monkeypatch.setattr(transcribe_answers, "_existing_drafts", _stale_read)
    res = await start(client, headers, session_id)

    assert res.status_code == 202, res.text
    assert (res.json()["total"], res.json()["pending"]) == (3, 3)
