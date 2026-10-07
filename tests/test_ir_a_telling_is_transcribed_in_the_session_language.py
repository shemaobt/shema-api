"""ENG-1226 — a telling is transcribed in the session's bridge language, within 15 s.

Both telling doors (the chunk door and the replace door) used to let the transcriber guess the
language, so a Portuguese telling came back as phonetic Spanish, and let it take two minutes. A
telling now carries the session's language and is bound to fifteen seconds; one that comes back
with no words, fails, or runs past the bound is refused with `WORDLESS_TELLING` and no spoken
line. Scribe is played at the provider boundary, so the real `transcribe_audio` and `heard` run.
"""

from __future__ import annotations

import asyncio
import re
import sys
import time
from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSessionStatus
from app.services.internalization_room.sessions import RETELLS_BEFORE_A_WARNING
from tests.hard_stretch_harness import (
    a_session,
    correct,
    current,
    marks,
    rehearse,
    retro_takes,
    row,
    tell,
)
from tests.room_harness import nothing_is_read_ahead, room_client, the_bucket_is_in_memory

PORTUGUESE = "Noemi ouve que o Senhor visitou o seu povo"
ENGLISH = "Naomi hears that the Lord visited his people"
SPANISH = "Noemí oye que el Señor visitó"


class Scribe:
    """The provider as the telling doors meet it: honours `language_code`, else guesses Spanish."""

    def __init__(self) -> None:
        self.mode = "words"

    async def handle(self, request: httpx.Request) -> httpx.Response:
        if self.mode == "down":
            return httpx.Response(503, text="unavailable")
        if self.mode == "hang":
            await asyncio.Event().wait()
        if self.mode == "empty":
            return httpx.Response(200, json={"text": ""})
        if self.mode == "annotation":
            return httpx.Response(200, json={"text": "[silêncio]"})
        hint = re.search(rb'name="language_code"\r\n\r\n(\w+)', request.content)
        said = {b"pt": PORTUGUESE, b"en": ENGLISH}.get(hint.group(1) if hint else b"", SPANISH)
        return httpx.Response(200, json={"text": said})


@pytest.fixture()
def scribe() -> Scribe:
    return Scribe()


@pytest.fixture()
async def client(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, scribe: Scribe
) -> AsyncIterator[httpx.AsyncClient]:
    import app.services.translation_helper.transcribe_audio  # noqa: F401
    from app.core.config import get_settings

    transcriber = sys.modules["app.services.translation_helper.transcribe_audio"]
    monkeypatch.setattr(get_settings(), "elevenlabs_api_key", "chave-de-teste", raising=False)
    provider = httpx.AsyncClient(transport=httpx.MockTransport(scribe.handle))
    monkeypatch.setattr(transcriber, "_make_client", lambda: provider)
    the_bucket_is_in_memory(monkeypatch)
    nothing_is_read_ahead(monkeypatch)
    async with room_client(db_session, monkeypatch) as door:
        yield door
    await provider.aclose()


def a_short_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.internalization_room import hearing

    monkeypatch.setattr(hearing, "TRANSCRIBER_BOUND_SECONDS", 0.2)


async def _one_told_stretch(client: httpx.AsyncClient, db: AsyncSession) -> tuple[str, str]:
    session_id = await a_session(db, language="pt")
    take_id = await rehearse(client, session_id)
    told = await tell(client, session_id, take_id, 1, queued=False)
    assert told.status_code == 200, told.text
    return session_id, take_id


async def test_a_telling_in_a_portuguese_session_is_stored_in_portuguese_words(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session, language="pt")
    take_id = await rehearse(client, session_id)

    answered = await tell(client, session_id, take_id, 1, queued=False)

    assert answered.status_code == 200, answered.text
    (stretch,) = await current(db_session, session_id)
    assert stretch.transcript == PORTUGUESE


async def test_a_telling_in_an_english_session_is_transcribed_in_english(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session, language="en")
    take_id = await rehearse(client, session_id)

    answered = await tell(client, session_id, take_id, 1, queued=False)

    assert answered.status_code == 200, answered.text
    (stretch,) = await current(db_session, session_id)
    assert stretch.transcript == ENGLISH


async def test_a_correction_in_a_portuguese_session_is_stored_in_portuguese_words(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id, take_id = await _one_told_stretch(client, db_session)
    (standing,) = await current(db_session, session_id)

    answered = await correct(client, session_id, standing.id, take_id)

    assert answered.status_code == 200, answered.text
    (replacement,) = await current(db_session, session_id)
    assert replacement.id != standing.id
    assert replacement.transcript == PORTUGUESE


@pytest.mark.parametrize("mode", ["empty", "annotation"])
async def test_a_telling_the_transcriber_finds_no_words_in_is_refused_with_no_spoken_line(
    client: httpx.AsyncClient, db_session: AsyncSession, scribe: Scribe, mode: str
) -> None:
    session_id = await a_session(db_session, language="pt")
    take_id = await rehearse(client, session_id)
    scribe.mode = mode

    refused = await tell(client, session_id, take_id, 1, queued=False)

    assert refused.status_code == 422, refused.text
    body = refused.json()
    assert body["code"] == "WORDLESS_TELLING"
    assert "fixed_line" not in body
    assert await current(db_session, session_id) == []
    assert len(await retro_takes(db_session, session_id)) == 1


async def test_a_telling_the_transcriber_fails_on_is_refused_with_no_spoken_line(
    client: httpx.AsyncClient, db_session: AsyncSession, scribe: Scribe
) -> None:
    session_id = await a_session(db_session, language="pt")
    take_id = await rehearse(client, session_id)
    scribe.mode = "down"

    refused = await tell(client, session_id, take_id, 1, queued=False)

    assert refused.status_code == 422, refused.text
    body = refused.json()
    assert body["code"] == "WORDLESS_TELLING"
    assert "fixed_line" not in body
    assert await current(db_session, session_id) == []
    assert len(await retro_takes(db_session, session_id)) == 1


async def test_a_telling_the_transcriber_does_not_answer_within_the_bound_is_refused(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    scribe: Scribe,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_short_bound(monkeypatch)
    session_id = await a_session(db_session, language="pt")
    take_id = await rehearse(client, session_id)
    scribe.mode = "hang"

    started = time.monotonic()
    refused = await tell(client, session_id, take_id, 1, queued=False)
    waited = time.monotonic() - started

    assert refused.status_code == 422, refused.text
    body = refused.json()
    assert body["code"] == "WORDLESS_TELLING"
    assert "fixed_line" not in body
    assert await current(db_session, session_id) == []
    assert len(await retro_takes(db_session, session_id)) == 1
    assert waited < 2.0


def test_the_transcribers_bound_is_fifteen_seconds() -> None:
    from app.services.internalization_room import hearing

    assert hearing.TRANSCRIBER_BOUND_SECONDS == 15


async def test_an_empty_correction_leaves_the_earlier_telling_as_it_was(
    client: httpx.AsyncClient, db_session: AsyncSession, scribe: Scribe
) -> None:
    session_id, take_id = await _one_told_stretch(client, db_session)
    (standing,) = await current(db_session, session_id)
    retros = len(await retro_takes(db_session, session_id))
    scribe.mode = "empty"

    refused = await correct(
        client, session_id, standing.id, take_id, audio=b"a correcao sem palavras"
    )

    assert refused.status_code == 422, refused.text
    body = refused.json()
    assert body["code"] == "WORDLESS_TELLING"
    assert "fixed_line" not in body
    (after,) = await current(db_session, session_id)
    assert (after.id, after.transcript, after.tellings) == (
        standing.id,
        standing.transcript,
        standing.tellings,
    )
    assert await marks(db_session, session_id) == []
    assert len(await retro_takes(db_session, session_id)) == retros + 1


@pytest.mark.parametrize("mode", ["down", "hang"])
async def test_a_correction_the_transcriber_fails_on_or_runs_past_the_bound_leaves_the_telling(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    scribe: Scribe,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    a_short_bound(monkeypatch)
    session_id, take_id = await _one_told_stretch(client, db_session)
    (standing,) = await current(db_session, session_id)
    retros = len(await retro_takes(db_session, session_id))
    scribe.mode = mode

    refused = await correct(
        client, session_id, standing.id, take_id, audio=b"a correcao que nao veio"
    )

    assert refused.status_code == 422, refused.text
    body = refused.json()
    assert body["code"] == "WORDLESS_TELLING"
    assert "fixed_line" not in body
    (after,) = await current(db_session, session_id)
    assert (after.id, after.transcript, after.tellings) == (
        standing.id,
        standing.transcript,
        standing.tellings,
    )
    assert await marks(db_session, session_id) == []
    assert len(await retro_takes(db_session, session_id)) == retros + 1


async def test_empty_corrections_never_make_a_hard_stretch(
    client: httpx.AsyncClient, db_session: AsyncSession, scribe: Scribe
) -> None:
    session_id, take_id = await _one_told_stretch(client, db_session)
    (standing,) = await current(db_session, session_id)
    scribe.mode = "empty"

    for _ in range(RETELLS_BEFORE_A_WARNING):
        refused = await correct(client, session_id, standing.id, take_id)
        assert refused.status_code == 422, refused.text

    (after,) = await current(db_session, session_id)
    assert after.tellings == standing.tellings
    assert await marks(db_session, session_id) == []
    assert (await row(db_session, session_id)).status is not IRSessionStatus.NEEDS_PERSON


async def test_a_telling_with_words_is_still_a_stretch_on_both_doors(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session, language="pt")
    take_id = await rehearse(client, session_id)

    told = await tell(client, session_id, take_id, 1, queued=False)
    assert told.status_code == 200, told.text
    assert told.json()["captured"] is True
    (standing,) = await current(db_session, session_id)

    corrected = await correct(client, session_id, standing.id, take_id)

    assert corrected.status_code == 200, corrected.text
    (replacement,) = await current(db_session, session_id)
    assert replacement.id != standing.id
    assert replacement.transcript == PORTUGUESE
