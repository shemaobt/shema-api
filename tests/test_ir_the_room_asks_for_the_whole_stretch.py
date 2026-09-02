"""When the verdict points at a stretch, the room asks for the whole stretch back.

The correction the screen offers **replaces** one stretch: the new telling-back takes the
position of the old one and the old one stops counting. So a team that records only the
amendment — which is what anybody would do — loses everything they had already told about
that stretch, and nothing anywhere says so. Measured in a real session: the same stretch was
corrected three times, and each round took the round before it out of circulation.

The room is almost wordless; what it has to say, it says out loud. So the fix is a sentence,
said in the same breath as the finding, and it fires exactly where the screen puts the two
microphones in front of the team — because that is the gesture that replaces.

These cases describe what the team hears, never how it is stored: none of them names a table
or a column, and none of them copies the sentence into a literal.
"""

from __future__ import annotations

import base64
import importlib
import json
from typing import Any

import httpx
import pytest
from google_crc32c import Checksum
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

import scripts.render_fixed_voice_lines as render
from app.db.models.internalization_room import IRSegment, IRTakeKind
from app.services.internalization_room import segments as service
from app.services.internalization_room.fail_safe import FailSafe, first, localized
from app.services.internalization_room.languages import ROOM_LANGUAGES
from app.services.internalization_room.sessions import get_session
from app.services.platform.storage import StoredObject

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"
DEVICE = "tablet-da-equipe-1"
PASSAGE = "P01"
LANGUAGE = "pt"

ASKED = FailSafe.STRETCH_TO_CORRECT

#: How many lines each family has written for it, per language the room claims to speak.
#: Enumerated rather than derived: a slice that changes how lines are dispatched is exactly
#: the kind that drops or duplicates a block on its way past, and a table derived from the
#: same files it is checking would move with them in silence.
FAMILIES: dict[str, dict[FailSafe, int]] = {
    "en": {
        FailSafe.UNREPAIRABLE: 4,
        FailSafe.OUTSIDE_MAP: 2,
        FailSafe.HANDOFF: 2,
        FailSafe.INAUDIBLE: 3,
        FailSafe.HARD_STOP: 1,
        FailSafe.INSTANT_ACK: 4,
        FailSafe.OFF_BRIDGE_LANGUAGE: 1,
        FailSafe.UNTOLD_STRETCH: 3,
        ASKED: 1,
    },
    "pt": {
        FailSafe.UNREPAIRABLE: 4,
        FailSafe.OUTSIDE_MAP: 2,
        FailSafe.HANDOFF: 2,
        FailSafe.INAUDIBLE: 3,
        FailSafe.HARD_STOP: 1,
        FailSafe.INSTANT_ACK: 4,
        FailSafe.OFF_BRIDGE_LANGUAGE: 1,
        FailSafe.UNTOLD_STRETCH: 3,
        ASKED: 1,
    },
    "es": {
        FailSafe.UNREPAIRABLE: 4,
        FailSafe.OUTSIDE_MAP: 2,
        FailSafe.HANDOFF: 2,
        FailSafe.INAUDIBLE: 3,
        FailSafe.HARD_STOP: 1,
        FailSafe.INSTANT_ACK: 4,
        FailSafe.OFF_BRIDGE_LANGUAGE: 1,
        FailSafe.UNTOLD_STRETCH: 3,
        ASKED: 1,
    },
}


class MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data

    async def stat(self, key: str) -> StoredObject | None:
        stored = self.objects.get(key)
        if stored is None:
            return None
        checksum = Checksum()
        checksum.update(stored)
        return StoredObject(
            size=len(stored), crc32c=base64.b64encode(checksum.digest()).decode("ascii")
        )


class Analyst:
    """The analyst, answering whatever this case needs it to have found.

    Set `verdict` to the reply the reading comes back with. The default is a clean one, so
    a case that wants a finding says so and every other case is explicitly the clean path.
    """

    def __init__(self) -> None:
        self.verdict: dict[str, Any] = {"evidence_sufficient": True, "findings": []}
        self.readings = 0

    def found(self, kind: str, *, chunk: int | None = 1) -> None:
        entry: dict[str, Any] = {"kind": kind, "note": "algo não apareceu"}
        if chunk is not None:
            entry["chunk"] = chunk
        self.verdict = {"evidence_sufficient": True, "findings": [entry]}

    async def __call__(self, *, system_prompt: str, user_content: str, **_: Any) -> str:
        self.readings += 1
        return json.dumps(self.verdict)


@pytest.fixture()
async def bucket(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    from app.services.internalization_room import takes as takes_service

    store = MemoryStore()
    monkeypatch.setattr(takes_service, "_store", lambda *_, **__: store)
    return store


@pytest.fixture()
def analyst(monkeypatch: pytest.MonkeyPatch) -> Analyst:
    from app.services.internalization_room import back_translation as bt_service

    reader = Analyst()
    monkeypatch.setattr(bt_service, "call_agent", reader)
    return reader


VERDICT_DRAFT = "No que vocês me contaram, uma coisa não apareceu."
VERDICT_DRAFT_ES = "En lo que ustedes me contaron, una cosa no apareció."


class Room:
    """What the room was asked to say, and the language its Speaker drafts in.

    The draft has to be in the session's language: a Portuguese sentence in a Spanish room
    is caught by the bridge-language check, the turn drops to a fail-safe, and every case
    here would then be measuring an outage instead of a verdict.
    """

    def __init__(self) -> None:
        self.said: list[str] = []
        self.draft = VERDICT_DRAFT


@pytest.fixture(autouse=True)
def room(monkeypatch: pytest.MonkeyPatch) -> Room:
    """Every line the room was actually asked to say, in order.

    The response carries an address for a clip and never the words, so what was said is not
    readable from it at all — and the words are the whole of what this slice changes.
    """
    heard = Room()

    from app.api.internalization_room import back_translation as bt_api

    # The package re-exports a `run_turn` function under the submodule's own name, so the
    # module has to be asked for by path rather than by attribute.
    turn_module = importlib.import_module("app.services.internalization_room.run_turn")

    async def speaker(*, system_prompt: str, user_content: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return heard.draft

    monkeypatch.setattr(turn_module, "call_agent", speaker)

    async def _voice(text: str, *_: Any, **__: Any):
        heard.said.append(text)
        return (type("Voiced", (), {"key": f"clipe-{len(heard.said)}"})(), 0)

    monkeypatch.setattr(bt_api.room, "synthesize_facilitator_speech", _voice)
    return heard


@pytest.fixture()
async def client(db_session: AsyncSession, bucket: MemoryStore, monkeypatch: pytest.MonkeyPatch):
    from fastapi import FastAPI

    from app.api.internalization_room import back_translation as bt_api
    from app.api.internalization_room import router
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)

    told: list[str] = []

    async def _transcribe(*_: Any, **__: Any) -> str:
        return told.pop(0) if told else "algo que a equipe contou"

    monkeypatch.setattr(bt_api, "heard", _transcribe)

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        c.told = told  # type: ignore[attr-defined]
        yield c


async def _open_session(client: httpx.AsyncClient, language: str = LANGUAGE) -> str:
    created = await client.post(
        f"{PREFIX}/sessions",
        headers={"X-Room-Key": KEY},
        json={"pericope": PASSAGE, "language": language},
    )
    assert created.status_code == 200, created.text
    return str(created.json()["session_id"])


async def _record(client: httpx.AsyncClient, session_id: str, audio: bytes) -> str:
    kept = await client.post(
        f"{PREFIX}/sessions/{session_id}/takes",
        headers={"X-Room-Key": KEY, "X-Room-Device": DEVICE},
        data={"kind": IRTakeKind.ENSAIO.value, "scope": PASSAGE},
        files={"file": ("tomada.m4a", audio, "audio/mp4")},
    )
    assert kept.status_code == 200, kept.text
    return str(kept.json()["take_id"])


async def _tell_back(
    client: httpx.AsyncClient,
    session_id: str,
    *,
    take_id: str,
    starts_ms: int,
    ends_ms: int,
    audio: bytes,
) -> None:
    told = await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/chunks",
        headers={"X-Room-Key": KEY, "X-Room-Device": DEVICE},
        data={"take_id": take_id, "starts_ms": str(starts_ms), "ends_ms": str(ends_ms)},
        files={"file": ("trecho.m4a", audio, "audio/mp4")},
    )
    assert told.status_code == 200, told.text


async def _finish(client: httpx.AsyncClient, session_id: str) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/finish", headers={"X-Room-Key": KEY}
    )


async def _two_stretches_told(
    client: httpx.AsyncClient, language: str = LANGUAGE
) -> tuple[str, str]:
    session_id = await _open_session(client, language)
    take_id = await _record(client, session_id, b"a equipe ensaiou a passagem inteira")
    client.told.extend(["Noemi mandou Rute voltar.", "Rute disse que ia junto."])  # type: ignore[attr-defined]
    await _tell_back(
        client, session_id, take_id=take_id, starts_ms=0, ends_ms=9000, audio=b"primeiro trecho"
    )
    await _tell_back(
        client, session_id, take_id=take_id, starts_ms=9000, ends_ms=21000, audio=b"segundo trecho"
    )
    return session_id, take_id


async def _re_record_the_native(db: AsyncSession, session_id: str, *, take_id: str) -> IRSegment:
    """Redo one stretch's mother-tongue audio, which leaves it waiting to be told back."""
    session = await get_session(db, session_id)
    standing = await service.final_segments(db, session_id)
    return await service.capture_segment(
        db,
        session,
        take_id=take_id,
        starts_ms=9000,
        ends_ms=24000,
        replaces=standing[-1],
    )


def _asked_for_the_whole_stretch(said: str, language: str = LANGUAGE) -> bool:
    """Whether the room asked, in that language, for the whole stretch to be told again.

    The written line is asserted before it is looked for. Read straight, an unwritten line
    is the empty string, which is inside every sentence there is and inside none of them —
    so every case here would answer the opposite of the truth and no case could fail for
    the reason it exists.
    """
    line = first(ASKED, language)
    assert line, f"a fala não está escrita em {language!r}, e uma fala vazia mede o contrário"
    return line in said


# ---------------------------------------------------------------------------
# The sentence exists, in every language the room claims
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("language", ROOM_LANGUAGES)
def test_the_line_is_written_in_every_language_the_room_speaks(language: str) -> None:
    """A language claimed and unwritten is a room that changes language mid-session.

    Measured with `localized` and not `utterances`: `utterances` falls back to the authored
    English block and so never comes back empty, which makes it safe to speak and useless as
    a measurement.
    """
    assert localized(ASKED, language), (
        f"a sala diz que fala {language!r} e não tem esta fala escrita nesse idioma — a "
        "equipe ouviria o veredito numa língua e o pedido em outra"
    )


def test_no_language_borrows_another_languages_words() -> None:
    written = {language: first(ASKED, language) for language in ROOM_LANGUAGES}

    assert len(set(written.values())) == len(ROOM_LANGUAGES), written


def test_the_line_is_spoken_and_never_shipped() -> None:
    """Like the waiting line, and for the same reason: nothing here has failed.

    It rides on the verdict's own clip, synthesized in that same request, so the app names
    it nowhere. Rendering it would put audio in the bundle that nothing plays and hold
    `--check` red forever.
    """
    for language in ROOM_LANGUAGES:
        assert not any(name.startswith(str(ASKED)) for name in render.catalogue(language))


@pytest.mark.parametrize("language", ROOM_LANGUAGES)
def test_no_other_family_changed(language: str) -> None:
    """Cheap, and where a change to how lines are dispatched usually leaks.

    The table is written out rather than derived. Derived from the same files it is checking,
    it would move with them and never go red — which is the whole of what it is for.
    """
    written = FAMILIES.get(language)
    assert written is not None, (
        f"a sala passou a reivindicar {language!r} e este quadro não foi escrito para ele"
    )
    counted = {kind: len(localized(kind, language)) for kind in FailSafe}

    assert counted == written


# ---------------------------------------------------------------------------
# It is said when the verdict points at a stretch to correct
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_room_asks_for_the_whole_stretch_when_the_verdict_points_at_one(
    client: httpx.AsyncClient, analyst: Analyst, room: Room
) -> None:
    """The heart of it: the sentence reaches the team in the breath that names the finding.

    On the same clip as the verdict, not a second one. The answer carries exactly one
    address for audio, so a sentence that needed a second slot would need a new app before
    the team could hear it at all.
    """
    analyst.found("missing", chunk=1)
    session_id, _ = await _two_stretches_told(client)

    answered = await _finish(client, session_id)

    assert answered.status_code == 200, answered.text
    assert answered.json()["finding_segment_id"], "o veredito tem de estar apontando um trecho"
    assert room.said, "e alguma coisa tem de ter sido dita"
    assert _asked_for_the_whole_stretch(room.said[-1]), (
        "a equipe grava só a emenda porque ninguém pediu o trecho inteiro; a rota de "
        "correção substitui, e o que já estava certo sai de circulação em silêncio"
    )


@pytest.mark.asyncio
async def test_the_verdict_is_still_said_first(
    client: httpx.AsyncClient, analyst: Analyst, room: Room
) -> None:
    """The request is added to the verdict, never said instead of it.

    The finding is the reason the team is being asked for anything; a turn that arrived as
    the request alone would be an instruction with nothing behind it.
    """
    analyst.found("missing", chunk=1)
    session_id, _ = await _two_stretches_told(client)

    await _finish(client, session_id)

    assert room.said[-1].startswith(VERDICT_DRAFT)


@pytest.mark.asyncio
async def test_the_room_asks_in_the_language_of_the_session(
    client: httpx.AsyncClient, analyst: Analyst, room: Room
) -> None:
    """A team hearing the finding in one language and the request in another hears two rooms."""
    analyst.found("missing", chunk=1)
    room.draft = VERDICT_DRAFT_ES
    session_id, _ = await _two_stretches_told(client, language="es")

    await _finish(client, session_id)

    assert _asked_for_the_whole_stretch(room.said[-1], "es")
    assert not _asked_for_the_whole_stretch(room.said[-1], "pt")


# ---------------------------------------------------------------------------
# It is not said when there is nothing to correct
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_clean_verdict_asks_for_nothing_to_be_told_over(
    client: httpx.AsyncClient, analyst: Analyst, room: Room
) -> None:
    """Nothing to correct, so a correction instruction is noise on the badge turn."""
    session_id, _ = await _two_stretches_told(client)

    answered = await _finish(client, session_id)

    assert answered.json()["finding_segment_id"] is None
    assert not _asked_for_the_whole_stretch(room.said[-1])


@pytest.mark.asyncio
async def test_a_stretch_still_waiting_is_not_a_stretch_to_tell_over(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: Analyst, room: Room
) -> None:
    """The first-round gate: nothing was read, so nothing was found to correct.

    What that team owes is the stretch they never told, and the family written for it says
    so. Asking them to tell a stretch *again* would name work they have not done once.
    """
    session_id, take_id = await _two_stretches_told(client)
    await _re_record_the_native(db_session, session_id, take_id=take_id)

    await _finish(client, session_id)

    assert analyst.readings == 0
    assert not _asked_for_the_whole_stretch(room.said[-1])


@pytest.mark.asyncio
async def test_a_finding_the_team_cannot_locate_is_not_a_stretch_to_tell_over(
    client: httpx.AsyncClient, analyst: Analyst, room: Room
) -> None:
    """No address, so no stretch on screen, so no microphone that replaces anything.

    The turn asks for a spoken answer instead, and a team told to tell a stretch over would
    be looking for a stretch the screen never offered them.
    """
    analyst.found("missing", chunk=None)
    session_id, _ = await _two_stretches_told(client)

    answered = await _finish(client, session_id)

    assert answered.json()["finding_segment_id"] is None
    assert not _asked_for_the_whole_stretch(room.said[-1])


@pytest.mark.asyncio
async def test_an_evidence_limit_on_a_stretch_is_not_a_stretch_to_tell_over(
    client: httpx.AsyncClient, analyst: Analyst, room: Room
) -> None:
    """`unclear` names a stretch and still hands nothing to the screen.

    It asks for that piece again in words, with no boundary question — and the two
    microphones exist to answer a boundary question. Where none was asked there is no
    replacing to warn about.
    """
    analyst.found("unclear", chunk=1)
    session_id, _ = await _two_stretches_told(client)

    answered = await _finish(client, session_id)

    assert answered.json()["finding_segment_id"], "o achado aponta um trecho"
    assert not _asked_for_the_whole_stretch(room.said[-1])
