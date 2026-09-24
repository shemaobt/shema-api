"""What a case about a hard stretch, or about a take's number, needs before it can ask.

The team's own gestures through the room's routes — the rehearsal recorded, a stretch told
back, one told again — plus the reads that go behind the routes to the rows they wrote, and
the Desk side that answers the facilitator the room asked for.

Shared by the cases about the count and the mark, the cases about the migration that carries
them, and the cases about which take the packet numbers, which is why it is here and not in
any one of them. Builders and constants only: a fixture cannot travel by import, so each
module keeps its own three-line fixtures and calls what is here.
"""

from __future__ import annotations

import base64
from typing import Any

import httpx
from google_crc32c import Checksum
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import (
    IRHardStretch,
    IRSegment,
    IRSession,
    IRTakeKind,
)
from app.models.internalization_room import PlayedTake
from app.services import internalization_room as full_room
from app.services.internalization_room import sessions as room
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.coverage import initial_state, merge
from app.services.internalization_room.release import build_internalization_release
from app.services.platform.storage import StoredObject
from app.services.platform.tts import SynthesizedSpeech

IR = "/api/internalization-room"
DESK = "/api/facilitator/teams"
ROOM_KEY = "sala-de-teste"
DEVICE = "tablet-da-equipe-1"
P = "P01"
AUDIO = b"a equipe explicou este trecho em portugues"

#: The stretches the helpers below tell, as slices of the one rehearsal recording.
SLICES = [(0, 9000), (9000, 18000), (18000, 27000)]

#: The routes wrote through this same session, so an instance left unexpired would answer from
#: the identity map and an assertion could pass without anything having reached the column.
#: `populate_existing` refreshes the rows this read returns and leaves every other one alone,
#: which `expire_all` does not: expiring the session object mid-test makes the next read of its
#: id a query from outside the async context.
FROM_THE_DATABASE = {"populate_existing": True}


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


async def voice(text: str, **_: Any) -> tuple[SynthesizedSpeech, bool]:
    entry = SynthesizedSpeech(
        audio=b"audio",
        mime_type="audio/mpeg",
        etag="e",
        cached=False,
        key=f"tts/voice/m/f/{abs(hash(text))}.mp3",
    )
    return entry, False


class Facilitator:
    def __init__(self, user_id: str, team_id: str, headers: dict[str, str]) -> None:
        self.id = user_id
        self.team_id = team_id
        self.headers = headers


async def a_session(db: AsyncSession, *, team_id: str | None = None) -> str:
    """A session, named by its id: the reads below expire the identity map."""
    session = await room.create_session(db, pericope=P, project_id=team_id)
    return str(session.id)


async def rehearse(client: httpx.AsyncClient, session_id: str, *, part: int | None = None) -> str:
    """Send the rehearsal up the way the tablet sends it, whole or as the part numbered `part`.

    None is the passage recorded in one go, which is what these cases want unless they go on to
    record that part again: the verb for *this part again* reads the number and nothing else
    (ADR 0023).
    """
    data: dict[str, str] = {"kind": IRTakeKind.ENSAIO.value, "scope": P}
    if part is not None:
        data["scope"] = f"parte-{part}"
        data["chunk_index"] = str(part)
    kept = await client.post(
        f"{IR}/sessions/{session_id}/takes",
        headers={"X-Room-Key": ROOM_KEY, "X-Room-Device": DEVICE},
        data=data,
        files={"file": ("ensaio.m4a", b"a equipe ensaiou a passagem inteira", "audio/mp4")},
    )
    assert kept.status_code == 200, kept.text
    return str(kept.json()["take_id"])


async def tell(
    client: httpx.AsyncClient,
    session_id: str,
    take_id: str,
    stretch: int,
    *,
    again: bool = False,
    saying: str | None = None,
) -> httpx.Response:
    """Tell stretch `stretch` (1-based) back, as a first telling or as one more.

    `saying=None` is the transcriber coming back with nothing, which is the shape of an
    outage and the case Marcia named by name.
    """
    starts, ends = SLICES[stretch - 1]
    client.said.append(saying if saying is not None else "")  # type: ignore[attr-defined]
    data = {"take_id": take_id, "starts_ms": str(starts), "ends_ms": str(ends)}
    if again:
        data["retelling"] = "true"
    return await client.post(
        f"{IR}/sessions/{session_id}/back-translation/chunks",
        headers={"X-Room-Key": ROOM_KEY, "X-Room-Device": DEVICE},
        data=data,
        files={"file": ("trecho.m4a", AUDIO, "audio/mp4")},
    )


async def told(client: httpx.AsyncClient, session_id: str, take_id: str, how_many: int) -> None:
    """A first telling of the first `how_many` stretches, each with words in it."""
    for stretch in range(1, how_many + 1):
        answered = await tell(client, session_id, take_id, stretch, saying=f"o trecho {stretch}")
        assert answered.status_code == 200, answered.text


async def row(db: AsyncSession, session_id: str) -> IRSession:
    result = await db.execute(
        select(IRSession).where(IRSession.id == session_id).execution_options(**FROM_THE_DATABASE)
    )
    return result.scalar_one()


async def current(db: AsyncSession, session_id: str) -> list[IRSegment]:
    result = await db.execute(
        select(IRSegment)
        .where(IRSegment.session_id == session_id, IRSegment.superseded_at.is_(None))
        .order_by(IRSegment.ordinal)
        .execution_options(**FROM_THE_DATABASE)
    )
    return list(result.scalars().all())


async def marks(db: AsyncSession, session_id: str) -> list[IRHardStretch]:
    result = await db.execute(
        select(IRHardStretch)
        .where(IRHardStretch.session_id == session_id)
        .order_by(IRHardStretch.crossed_at, IRHardStretch.segment_id)
        .execution_options(**FROM_THE_DATABASE)
    )
    return list(result.scalars().all())


async def attend(client: httpx.AsyncClient, session_id: str, who: Facilitator) -> httpx.Response:
    return await client.post(
        f"{IR}/facilitator/sessions/{session_id}/attended", headers=who.headers
    )


async def ready_for_release(db: AsyncSession, session: IRSession) -> dict[str, Any]:
    """Everything `build_internalization_release` asks for besides the telling-back itself.

    What the caller told back is left exactly as they told it: only coverage and the
    playback report are added here, and none of them is what these cases are about —
    they are about which takes the packet lists, and under which numbers.

    The analyst is stood in for rather than run, which is what `analysed_segment_ids` below has
    always done: these sessions tell back through the room's own routes and never press
    `terminei`, so nothing here ever asked the analyst anything. `checked` is the other half of
    that same stand-in and is set for the same reason — the session these cases mean is one
    that came out clean, and a release refused over a finding nobody ever raised would fail
    them on a gate they are not watching (ENG-882).
    """
    session.coverage_state = merge(initial_state(P), pericope_num=P, engaged=element_keys(P))

    told_back = await full_room.final_segments(db, session.id)
    state = full_room.back_translation_of(session)
    state.analysed_segment_ids = [segment.id for segment in told_back]
    state.checked = True
    clip_end = max((segment.ends_ms for segment in told_back), default=0)
    await full_room.report_playback(
        db,
        session,
        state,
        played_by_take=[
            PlayedTake(take_id=take_id, played_ranges=[[0, clip_end]], clip_duration_ms=clip_end)
            for take_id in sorted({segment.take_id for segment in told_back})
        ],
        played_ranges=[[0, clip_end]],
        clip_duration_ms=clip_end,
    )

    return await build_internalization_release(db, session)
