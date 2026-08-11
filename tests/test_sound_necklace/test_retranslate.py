"""Confirming an edited transcript, and the English that has to follow it (ENG-394).

The draft pass writes the spoken-language transcript and its English exactly once. A
facilitator then corrects the spoken text on screen, and the report reads the English
field — so without a route that re-translates on confirmation the correction never
reaches the artifact.

The provider is a double with the Protocol's real signature, never a mock, so a keyword
that drifts breaks the call here instead of only in production. Service-level tests pass
it in directly; the tests that go over HTTP substitute it on the service module, because
the route has no parameter to pass one through. Both reach the same seam.

That substitution goes through `importlib` rather than a dotted string, and it has to:
`app/services/sound_necklace/__init__.py` re-exports `retranslate_answer` the function
over `retranslate_answer` the module, and every string-target patcher — `mock.patch`,
`monkeypatch.setattr` — resolves by walking attributes down from the package, so all of
them land on the function and raise. Asking the import system for the module sidesteps
the shadowing. The service reads the provider's name at call time so that replacing it
there is enough.

The split is by what is under test, not by convenience. The guards, the races and the
billing live at the service, where a double can be handed in and a rival write can be
made to land mid-call. The route's own contract — status codes, and the three ways a 409
means different things — lives over HTTP, including the corrected-Portuguese path this
whole issue exists for, end to end.

The two race tests are aimed at the guards riding inside the write statement, which the
cheap pre-checks in front of them would otherwise hide. Both set out from a session that
is free and a counter that matches, so the confirm gets all the way past those, and only
then move the table underneath it from inside the provider call. Each asserts the
provider was reached: that is the evidence the pre-check let it through, leaving the
statement as the only thing that can have refused the write.

These tests spend the same currency the endpoint does: every assertion about the
translator's call list is an assertion about a bill.
"""

from __future__ import annotations

import importlib
from collections.abc import Awaitable, Callable

import pytest
from sqlalchemy import select, text

from app.core.exceptions import SessionLockChanged, UpstreamServiceError
from app.db.models.sound_necklace import SnAnswerTranscript, TranscriptStatus
from app.services import sound_necklace_service as sn_service
from app.services.oral_collector import gcs_utils
from tests.test_sound_necklace.conftest import SN, hand_lease_to, new_session

WEBM = b"\x1a\x45\xdf\xa3 fake webm/opus bytes"
ANSWER = "respostas/level1/recontar.webm"

retranslate_answer_service = importlib.import_module(
    "app.services.sound_necklace.retranslate_answer"
)

DRAFT_PT = "eu vi o boto na beira do rio"
DRAFT_EN = "i saw the boto by the river"
CONFIRMED_PT = "eu vi o boto-cor-de-rosa na beira do rio"
CONFIRMED_EN = "i saw the pink river dolphin by the river"


class FakeTranslator:
    """The provider seam, spelled with the signature the Protocol declares.

    Not a mock: a mock accepts whatever it is called with, so a renamed keyword on the
    real translator would leave every one of these green and production broken.

    ``during`` runs inside the call. The await on the provider is the only window a test
    can reach into, and it is the window the in-statement guards exist to cover — a
    confirm reads the row, goes away to translate, and comes back to a table that has
    moved.
    """

    def __init__(
        self,
        reply: str = CONFIRMED_EN,
        *,
        raises: Exception | None = None,
        during: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self.reply = reply
        self.raises = raises
        self.during = during
        self.calls: list[tuple[str, str]] = []

    async def __call__(self, text: str, *, source_language: str) -> str:
        self.calls.append((text, source_language))
        if self.during is not None:
            await self.during()
        if self.raises is not None:
            raise self.raises
        return self.reply


@pytest.fixture()
def storage(monkeypatch):
    """The bucket: recorded answers land in a dict instead of GCS."""
    objects: dict[str, bytes] = {}

    async def upload(
        bucket: str, key: str, data: bytes, content_type: str, *, content_encoding=None
    ) -> str:
        objects[key] = data
        return f"gs://{bucket}/{key}"

    async def download(bucket: str, key: str) -> bytes:
        return objects[key]

    async def delete(bucket: str, key: str) -> None:
        objects.pop(key, None)

    monkeypatch.setattr(gcs_utils, "upload_gcs_object", upload)
    monkeypatch.setattr(gcs_utils, "download_gcs_object", download)
    monkeypatch.setattr(gcs_utils, "delete_gcs_object", delete)
    return objects


async def record_answer(client, headers, session_id: str, path: str = ANSWER) -> None:
    res = await client.put(
        f"{SN}/sessions/{session_id}/resources",
        headers=headers,
        params={"path": path},
        content=WEBM,
    )
    assert res.status_code == 201, res.text


async def give_draft(
    db_session,
    session_id: str,
    *,
    path: str = ANSWER,
    language: str = "pt-BR",
    generation: int = 0,
    transcript_source: str | None = DRAFT_PT,
    translation_en: str | None = DRAFT_EN,
) -> None:
    """Put the draft pass's own output in the row, without running the pass."""
    db_session.add(
        SnAnswerTranscript(
            session_id=session_id,
            resource_path=path,
            status=TranscriptStatus.READY,
            language=language,
            generation=generation,
            transcript_source=transcript_source,
            translation_en=translation_en,
        )
    )
    await db_session.commit()


async def stored(db_session, session_id: str, path: str = ANSWER) -> SnAnswerTranscript:
    """The row as the table holds it, not as the identity map remembers it."""
    return (
        await db_session.execute(
            select(SnAnswerTranscript)
            .where(
                SnAnswerTranscript.session_id == session_id,
                SnAnswerTranscript.resource_path == path,
            )
            .execution_options(populate_existing=True)
        )
    ).scalar_one()


async def win_the_race(db_session, session_id: str, *, generation: int, path: str = ANSWER) -> None:
    """Let another confirm land, the way one committing mid-translation would.

    Written behind the ORM's back for the reason ``hand_lease_to`` is: the turnover has to
    land *during* a call the test is already awaiting, which a second service call on the
    one session cannot express.
    """
    await db_session.execute(
        text(
            "UPDATE sn_answer_transcripts SET generation = :gen, transcript_source = :src, "
            "translation_en = :eng WHERE session_id = :sid AND resource_path = :path"
        ),
        {
            "gen": generation,
            "src": "o outro facilitador digitou isto",
            "eng": "the other facilitator typed this",
            "sid": session_id,
            "path": path,
        },
    )


async def confirm_over_http(client, headers, session_id: str, path: str, **body):
    return await client.put(
        f"{SN}/sessions/{session_id}/transcriptions/{path}", headers=headers, json=body
    )


@pytest.fixture()
async def drafted(client, db_session, alice, project, storage):
    """A pt-BR answer with the pass's draft already in the table, plus its facilitator."""
    user, headers = alice
    session_id = await new_session(client, headers, project.id)
    await record_answer(client, headers, session_id)
    await give_draft(db_session, session_id)
    return session_id, user, headers


async def test_confirming_an_edited_transcript_stores_the_new_english(db_session, drafted) -> None:
    session_id, user, _headers = drafted
    translator = FakeTranslator()

    confirmed = await sn_service.retranslate_answer(
        db_session,
        session_id,
        ANSWER,
        transcript_source=CONFIRMED_PT,
        expected_generation=0,
        actor_user_id=user.id,
        translator=translator,
    )

    assert translator.calls == [(CONFIRMED_PT, "pt-BR")]
    assert (confirmed.transcript_source, confirmed.translation_en) == (CONFIRMED_PT, CONFIRMED_EN)
    assert confirmed.status is TranscriptStatus.READY
    assert confirmed.generation == 1

    row = await stored(db_session, session_id)
    assert (row.transcript_source, row.translation_en) == (CONFIRMED_PT, CONFIRMED_EN)


async def test_confirming_the_text_already_stored_is_never_billed(db_session, drafted) -> None:
    session_id, user, _headers = drafted
    translator = FakeTranslator()

    confirmed = await sn_service.retranslate_answer(
        db_session,
        session_id,
        ANSWER,
        transcript_source=DRAFT_PT,
        expected_generation=0,
        actor_user_id=user.id,
        translator=translator,
    )

    assert translator.calls == []
    assert (confirmed.transcript_source, confirmed.translation_en) == (DRAFT_PT, DRAFT_EN)


async def test_re_confirming_unchanged_text_from_a_stale_generation_is_still_a_no_op(
    db_session, drafted
) -> None:
    session_id, user, _headers = drafted
    await win_the_race(db_session, session_id, generation=4)
    translator = FakeTranslator()

    confirmed = await sn_service.retranslate_answer(
        db_session,
        session_id,
        ANSWER,
        transcript_source="o outro facilitador digitou isto",
        expected_generation=0,
        actor_user_id=user.id,
        translator=translator,
    )

    assert translator.calls == []
    assert confirmed.generation == 4


async def test_confirming_an_english_answer_leaves_the_english_equal_to_the_text(
    client, db_session, alice, project, storage
) -> None:
    user, headers = alice
    session_id = await new_session(client, headers, project.id)
    await record_answer(client, headers, session_id)
    await give_draft(
        db_session,
        session_id,
        language="en-US",
        transcript_source="i saw the dolphin",
        translation_en="i saw the dolphin",
    )
    translator = FakeTranslator()

    confirmed = await sn_service.retranslate_answer(
        db_session,
        session_id,
        ANSWER,
        transcript_source="i saw the pink river dolphin",
        expected_generation=0,
        actor_user_id=user.id,
        translator=translator,
    )

    assert translator.calls == []
    assert confirmed.transcript_source == "i saw the pink river dolphin"
    assert confirmed.translation_en == "i saw the pink river dolphin"


async def test_confirming_from_a_generation_that_has_moved_on_is_refused(
    client, db_session, alice, project, storage
) -> None:
    user, headers = alice
    session_id = await new_session(client, headers, project.id)
    await record_answer(client, headers, session_id)
    await give_draft(db_session, session_id, generation=2)
    translator = FakeTranslator()

    with pytest.raises(sn_service.TranscriptConfirmConflict):
        await sn_service.retranslate_answer(
            db_session,
            session_id,
            ANSWER,
            transcript_source=CONFIRMED_PT,
            expected_generation=1,
            actor_user_id=user.id,
            translator=translator,
        )

    assert translator.calls == []
    row = await stored(db_session, session_id)
    assert (row.transcript_source, row.translation_en) == (DRAFT_PT, DRAFT_EN)
    assert row.generation == 2


async def test_a_confirm_that_lands_after_another_has_won_does_not_overwrite_it(
    db_session, drafted
) -> None:
    session_id, user, _headers = drafted

    async def someone_else_confirms() -> None:
        await win_the_race(db_session, session_id, generation=1)

    translator = FakeTranslator(during=someone_else_confirms)

    with pytest.raises(sn_service.TranscriptConfirmConflict):
        await sn_service.retranslate_answer(
            db_session,
            session_id,
            ANSWER,
            transcript_source=CONFIRMED_PT,
            expected_generation=0,
            actor_user_id=user.id,
            translator=translator,
        )

    assert translator.calls == [(CONFIRMED_PT, "pt-BR")]
    row = await stored(db_session, session_id)
    assert row.transcript_source == "o outro facilitador digitou isto"
    assert row.translation_en == "the other facilitator typed this"
    assert row.generation == 1


async def test_a_lock_taken_during_the_translation_still_refuses_the_write(
    db_session, drafted, bob
) -> None:
    session_id, user, _headers = drafted
    bob_user, _bob_headers = bob

    async def bob_takes_over() -> None:
        await hand_lease_to(db_session, session_id, bob_user.id)

    translator = FakeTranslator(during=bob_takes_over)

    with pytest.raises(sn_service.SessionLockedByOther):
        await sn_service.retranslate_answer(
            db_session,
            session_id,
            ANSWER,
            transcript_source=CONFIRMED_PT,
            expected_generation=0,
            actor_user_id=user.id,
            translator=translator,
        )

    assert translator.calls == [(CONFIRMED_PT, "pt-BR")]
    row = await stored(db_session, session_id)
    assert (row.transcript_source, row.translation_en) == (DRAFT_PT, DRAFT_EN)
    assert row.generation == 0


def lease_lapses_before_the_diagnosis(monkeypatch) -> None:
    """Let the pre-check run for real, then make the diagnosis read find nobody.

    Nobody is what it finds when the lease expires between the write it refused and the
    read that asks who refused it — a window microseconds wide that no test can hit by
    timing. Only the second call is stubbed, so the pre-check still has to pass on its
    own and the guard inside the statement stays the only thing that can refuse.
    """
    diagnose = retranslate_answer_service.raise_if_locked_by_other
    calls = 0

    async def lapsed(*args, **kwargs) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            await diagnose(*args, **kwargs)

    monkeypatch.setattr(retranslate_answer_service, "raise_if_locked_by_other", lapsed)


async def test_a_confirm_refused_by_a_lease_that_then_lapsed_is_not_a_stale_draft(
    db_session, drafted, bob, monkeypatch
) -> None:
    session_id, user, _headers = drafted
    bob_user, _bob_headers = bob
    lease_lapses_before_the_diagnosis(monkeypatch)

    async def bob_takes_over() -> None:
        await hand_lease_to(db_session, session_id, bob_user.id)

    translator = FakeTranslator(during=bob_takes_over)

    with pytest.raises(SessionLockChanged):
        await sn_service.retranslate_answer(
            db_session,
            session_id,
            ANSWER,
            transcript_source=CONFIRMED_PT,
            expected_generation=0,
            actor_user_id=user.id,
            translator=translator,
        )

    assert translator.calls == [(CONFIRMED_PT, "pt-BR")]
    row = await stored(db_session, session_id)
    assert (row.transcript_source, row.translation_en) == (DRAFT_PT, DRAFT_EN)
    assert row.generation == 0


async def test_a_draft_that_moved_under_a_lapsed_lease_is_still_a_stale_draft(
    db_session, drafted, bob, monkeypatch
) -> None:
    session_id, user, _headers = drafted
    bob_user, _bob_headers = bob
    lease_lapses_before_the_diagnosis(monkeypatch)

    async def bob_takes_over_and_confirms() -> None:
        await hand_lease_to(db_session, session_id, bob_user.id)
        await win_the_race(db_session, session_id, generation=1)

    translator = FakeTranslator(during=bob_takes_over_and_confirms)

    with pytest.raises(sn_service.TranscriptConfirmConflict):
        await sn_service.retranslate_answer(
            db_session,
            session_id,
            ANSWER,
            transcript_source=CONFIRMED_PT,
            expected_generation=0,
            actor_user_id=user.id,
            translator=translator,
        )

    row = await stored(db_session, session_id)
    assert row.transcript_source == "o outro facilitador digitou isto"


async def test_a_translator_failure_leaves_the_stored_draft_consistent(db_session, drafted) -> None:
    session_id, user, _headers = drafted
    translator = FakeTranslator(raises=UpstreamServiceError("Gemini is down"))

    with pytest.raises(UpstreamServiceError):
        await sn_service.retranslate_answer(
            db_session,
            session_id,
            ANSWER,
            transcript_source=CONFIRMED_PT,
            expected_generation=0,
            actor_user_id=user.id,
            translator=translator,
        )

    row = await stored(db_session, session_id)
    assert (row.transcript_source, row.translation_en) == (DRAFT_PT, DRAFT_EN)
    assert row.generation == 0


async def test_the_route_answers_the_confirmed_draft(
    client, db_session, alice, project, storage
) -> None:
    _user, headers = alice
    session_id = await new_session(client, headers, project.id)
    await record_answer(client, headers, session_id)
    await give_draft(
        db_session,
        session_id,
        language="en-US",
        transcript_source="i saw the dolphin",
        translation_en="i saw the dolphin",
    )

    res = await confirm_over_http(
        client,
        headers,
        session_id,
        ANSWER,
        transcript_source="i saw the pink river dolphin",
        generation=0,
    )

    assert res.status_code == 200, res.text
    assert res.json() == {
        "path": ANSWER,
        "status": "ready",
        "transcript_verbatim": None,
        "transcript_source": "i saw the pink river dolphin",
        "translation_en": "i saw the pink river dolphin",
        "error": None,
        "generation": 1,
    }


async def test_a_corrected_portuguese_confirm_reaches_the_report_in_english(
    client, db_session, drafted, monkeypatch
) -> None:
    session_id, _user, headers = drafted
    translator = FakeTranslator()
    monkeypatch.setattr(retranslate_answer_service, "translate_to_english", translator)

    res = await confirm_over_http(
        client, headers, session_id, ANSWER, transcript_source=CONFIRMED_PT, generation=0
    )

    assert res.status_code == 200, res.text
    assert translator.calls == [(CONFIRMED_PT, "pt-BR")]
    body = res.json()
    assert body["transcript_source"] == CONFIRMED_PT
    assert body["translation_en"] == CONFIRMED_EN
    assert body["generation"] == 1

    row = await stored(db_session, session_id)
    assert (row.transcript_source, row.translation_en) == (CONFIRMED_PT, CONFIRMED_EN)


async def test_confirming_a_transcript_that_was_never_drafted_is_a_404(
    client, alice, project, storage
) -> None:
    _user, headers = alice
    session_id = await new_session(client, headers, project.id)
    await record_answer(client, headers, session_id)

    res = await confirm_over_http(
        client, headers, session_id, ANSWER, transcript_source=CONFIRMED_PT, generation=0
    )

    assert res.status_code == 404, res.text
    assert res.json()["detail"] == "This answer has no transcript to confirm"


async def test_confirming_on_a_session_someone_else_holds_is_refused(
    client, db_session, alice, bob, project, storage
) -> None:
    _alice, alice_headers = alice
    _bob, bob_headers = bob
    session_id = await new_session(client, alice_headers, project.id)
    await record_answer(client, alice_headers, session_id)
    await give_draft(db_session, session_id)
    await client.put(f"{SN}/sessions/{session_id}/lock", headers=bob_headers)

    res = await confirm_over_http(
        client, alice_headers, session_id, ANSWER, transcript_source=CONFIRMED_PT, generation=0
    )

    assert res.status_code == 409, res.text
    assert res.json()["code"] == "SESSION_LOCKED"
    assert res.json()["holder_name"] == "Bob"

    row = await stored(db_session, session_id)
    assert (row.transcript_source, row.translation_en) == (DRAFT_PT, DRAFT_EN)


async def test_a_stale_confirm_is_a_409_the_client_can_tell_from_a_locked_one(
    client, db_session, alice, project, storage
) -> None:
    _user, headers = alice
    session_id = await new_session(client, headers, project.id)
    await record_answer(client, headers, session_id)
    await give_draft(db_session, session_id, generation=3)

    res = await confirm_over_http(
        client, headers, session_id, ANSWER, transcript_source=CONFIRMED_PT, generation=1
    )

    assert res.status_code == 409, res.text
    assert res.json()["code"] == "CONFLICT"
    assert "holder_name" not in res.json()


async def test_a_confirm_the_lease_lost_and_then_lapsed_on_is_a_409_that_says_retry(
    client, db_session, drafted, bob, monkeypatch
) -> None:
    session_id, _user, headers = drafted
    bob_user, _bob_headers = bob
    lease_lapses_before_the_diagnosis(monkeypatch)

    async def bob_takes_over() -> None:
        await hand_lease_to(db_session, session_id, bob_user.id)

    translator = FakeTranslator(during=bob_takes_over)
    monkeypatch.setattr(retranslate_answer_service, "translate_to_english", translator)

    res = await confirm_over_http(
        client, headers, session_id, ANSWER, transcript_source=CONFIRMED_PT, generation=0
    )

    assert res.status_code == 409, res.text
    assert res.json()["code"] == "SESSION_LOCK_CHANGED"
    assert "holder_name" not in res.json()

    row = await stored(db_session, session_id)
    assert (row.transcript_source, row.translation_en) == (DRAFT_PT, DRAFT_EN)


@pytest.mark.parametrize("blank", ["", "   ", "\n\t "])
async def test_a_blank_confirm_is_refused_before_it_can_blank_the_draft(
    client, db_session, drafted, blank
) -> None:
    session_id, _user, headers = drafted

    res = await confirm_over_http(
        client, headers, session_id, ANSWER, transcript_source=blank, generation=0
    )

    assert res.status_code == 422, res.text
    row = await stored(db_session, session_id)
    assert (row.transcript_source, row.translation_en) == (DRAFT_PT, DRAFT_EN)


async def test_a_confirm_is_stored_with_its_spacing_as_the_human_left_it(
    client, db_session, drafted, monkeypatch
) -> None:
    session_id, _user, headers = drafted
    spaced = f"  {CONFIRMED_PT}\n"
    translator = FakeTranslator()
    monkeypatch.setattr(retranslate_answer_service, "translate_to_english", translator)

    res = await confirm_over_http(
        client, headers, session_id, ANSWER, transcript_source=spaced, generation=0
    )

    assert res.status_code == 200, res.text
    assert translator.calls == [(spaced, "pt-BR")]
    row = await stored(db_session, session_id)
    assert row.transcript_source == spaced
