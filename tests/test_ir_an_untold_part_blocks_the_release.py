"""ENG-856 — a **Part** the team recorded again and has not told back refuses the **Release**.

The **Packet** carries one recording per part, the newest, and every one of them was performed
by the team (ADR 0025). Which recording is current is a fact of the takes: a rehearsal take
stored under a number an earlier take of the session carries *is* that part again (ADR 0023),
and it arrives carrying nobody's words.

Until now every gate over the words was derived from the stretches — `untold_stretch`,
`first_untold`, the listening — and a part just recorded again has no stretch at all: its own
were retired with the recording they were slices of. So the fresh part was invisible to all
three while it sat in `rehearsal_takes`, and a clean reading of the other parts could mint a
release whose packet carried a recording nobody told back.

The gate reads the current parts beside the stretches for that one question, and answers it
with `untold_part`. It is missing material and not a dispute — there is nothing in a recording
nobody explained for a facilitator to overrule — so no force lifts it.

The listening gate stays where ADR 0023 put it, on the stretches: which recording is current is
a takes fact, and what the team heard of it is a report fact.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import App
from app.services.internalization_room.sessions import get_session
from app.services.internalization_room.takes import take_by_id
from tests.baker import make_app, make_role
from tests.release_harness import (
    APP_KEY,
    a_claimed_device,
    at_the_desk,
    desk_release,
    ensaio_take,
    ready_session,
    releases_of,
    the_one_part_of,
)
from tests.room_harness import (
    after,
    heard_every_part,
    press_terminei,
    rehearsed_in_parts,
    release_blockers,
    release_packet,
    room_client,
    stretch_on,
    tell_back_about,
    the_analyst_reads,
    the_bucket_is_in_memory,
    the_room_speaks,
    the_upload_landed_at,
    upload_a_part,
)

UNTOLD_PART = "untold_part"
NOT_CHECKED = "telling_back_not_checked"

#: New bytes on every upload, because a take is addressed by the hash of its audio: the same
#: bytes twice are one row and no re-recording at all.
NEW_AUDIO = b"a equipe gravou a cena dois outra vez"


@pytest.fixture(autouse=True)
def analyst(monkeypatch: pytest.MonkeyPatch) -> None:
    """The analyst, reading clean, so a press of `terminei` leaves a check nothing is open on."""
    the_analyst_reads(monkeypatch)


@pytest.fixture(autouse=True)
def voice(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Speaker and the synthesizer, so `terminei` answers without a model or a bucket."""
    the_room_speaks(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    """The room's routes, with the bucket in memory so an upload needs no storage."""
    the_bucket_is_in_memory(monkeypatch)
    async with room_client(db_session, monkeypatch) as room:
        yield room


@pytest.fixture()
async def room_app(db_session: AsyncSession) -> App:
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


async def _pressed_terminei(client: httpx.AsyncClient, db: AsyncSession, session_id: str) -> None:
    """Press `terminei` over the parts the session's stretches are standing on right now.

    What the press answers is each case's own subject: it confers where nothing is owed, and it
    refuses where a part stands with nothing told over it.
    """
    report = await heard_every_part(db, session_id)
    answered = await press_terminei(client, session_id, report=report)
    assert answered.status_code == 200, answered.text


async def _recorded_again(
    client: httpx.AsyncClient, session_id: str, *, part: int | None, audio: bytes = NEW_AUDIO
) -> str:
    """Upload a rehearsal part under a number, and answer with the take id the room kept."""
    kept = await upload_a_part(client, session_id, part=part, audio=audio)
    assert kept.status_code == 200, kept.text
    return str(kept.json()["take_id"])


async def _a_session_with_part_two_recorded_again(
    client: httpx.AsyncClient, db: AsyncSession, *, project_id: str | None = None
):
    """Three parts told back, heard and read clean, and then part two recorded again.

    The clean state is asserted on the way through: a case about what the fresh recording adds
    to the refusal proves nothing if the session was already being refused for something else.
    """
    session, parts = await rehearsed_in_parts(db, 3, project_id=project_id)
    await _pressed_terminei(client, db, session.id)
    assert (await release_packet(db, session))["purpose"] == "first_team_rehearsal", (
        "the case starts from a session the gate lets through"
    )

    fresh = await _recorded_again(client, session.id, part=2)
    return session, parts, fresh


async def test_a_part_recorded_again_and_not_told_back_blocks_the_release(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """The team recorded scene two again and said nothing over it yet: the packet cannot travel.

    Its own stretches went with the recording they were slices of, so nothing derived from the
    stretches can see it. What the packet would carry is a recording of the mother tongue with
    no words beside it, which downstream reads as a team who stood in front of that scene and
    said nothing.
    """
    session, _parts, _fresh = await _a_session_with_part_two_recorded_again(client, db_session)

    assert UNTOLD_PART in await release_blockers(db_session, session)


async def test_a_clean_reading_of_the_other_parts_does_not_release_the_untold_part(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """The check refuses the press, and the release goes on naming the part behind it.

    This was the hole: the analyst read the two parts that stand, found nothing, and the passage
    was conferred with a recording nobody had explained in it — the release alone refused it.
    The check refuses that press itself now (ADR 0027), so the passage is not checked, and this
    is where the two answers are read side by side: the gate names the part the check named, and
    a build that stopped doing either would be caught here.
    """
    session, _parts, _fresh = await _a_session_with_part_two_recorded_again(client, db_session)

    await _pressed_terminei(client, db_session, session.id)

    assert await release_blockers(db_session, session) == [NOT_CHECKED, UNTOLD_PART], (
        "the check refused the press, and the part nobody told back is still standing"
    )


async def test_the_facilitator_cannot_force_past_an_untold_part(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app: App
) -> None:
    """The Desk's own code does not open this door, and no release is minted.

    A facilitator forces a dispute: a finding the team answered, a part the room says was not
    heard through. Ground nobody told back is not a dispute — there is nothing to look at and
    disagree with — so it refuses the force the way it refuses the team, with the same 409.

    The table that walks the other unforceable codes breaks a ready session by writing to it;
    this state is only reachable through the upload route, which is why the case is here and not
    a seventh row there.
    """
    project, _credential = await a_claimed_device(db_session)
    session, _parts, _fresh = await _a_session_with_part_two_recorded_again(
        client, db_session, project_id=project.id
    )
    await _pressed_terminei(client, db_session, session.id)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    refused = await client.post(desk_release(session.id), headers=desk, json={"force": True})

    assert refused.status_code == 409, refused.text
    assert UNTOLD_PART in refused.json()["detail"]
    assert await releases_of(db_session, session.id) == []


async def test_telling_the_new_part_back_lifts_the_blocker(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """The team tells scene two back over the new recording, and the packet travels.

    What comes out carries one recording per scene, the fresh one in the second place, because
    the part's identity is its number and the newest under that number is the part (ADR 0023).
    """
    session, (one, _two, three), fresh = await _a_session_with_part_two_recorded_again(
        client, db_session
    )
    await _pressed_terminei(client, db_session, session.id)

    await tell_back_about(
        db_session,
        session,
        await take_by_id(db_session, fresh),
        transcript="a cena dois contada de novo",
        bridge_take_id="retro-de-novo",
    )
    await _pressed_terminei(client, db_session, session.id)

    packet = await release_packet(db_session, await get_session(db_session, session.id))
    audio = packet["audio"]
    assert [take["take_id"] for take in audio["rehearsal_takes"]] == [one.id, fresh, three.id]
    assert audio["recording_grain"] == "parts"


async def test_a_rehearsal_told_whole_and_recorded_again_is_untold(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """A passage recorded in one go is one part, and recording it again leaves it untold too.

    The verb that retires stretches does not fire here — an upload carrying no number says
    nothing about which part it replaces — so the telling the team already gave stands, on a
    recording that is no longer the part. The rule is about the part having nothing told on it
    and not about anything being retired, so this is the same refusal.
    """
    session = await ready_session(db_session)
    told_whole = await the_one_part_of(db_session, session)
    assert (await release_packet(db_session, session))["purpose"] == "first_team_rehearsal", (
        "the case starts from a session the gate lets through"
    )

    fresh = await _recorded_again(client, session.id, part=None)
    await the_upload_landed_at(db_session, fresh, after(told_whole))

    assert await release_blockers(db_session, session) == [UNTOLD_PART]


async def test_an_old_composed_row_still_yields_one_take_per_number(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """A passage the server assembled, stored back when it did that, is a take like any other.

    The fixture is the state the **Rebuild** left behind while the room had one: a recording
    built around a corrected stretch, kept under the number of the recording it was built from,
    with that part's stretches re-pointed at the file that came out. Those rows are history and
    travel through the packet by the same rule as any take (ADR 0025).

    What the case holds is that such a row flows by the same rule as any take: it is the newest
    under two, therefore it is part two, and the packet carries one recording per number. It
    cannot hold that the scope is *read and ignored*, because nothing reads it — which is the
    state this slice leaves behind and the reason the row is unremarkable.
    """
    session, (one, two, three) = await rehearsed_in_parts(db_session, 3)
    assembled = ensaio_take(
        session.id,
        scope="composed",
        ordinal=two.ordinal,
        sha256="r" * 64,
        created_at=after(two),
        project_id=session.project_id,
    )
    db_session.add(assembled)
    await db_session.commit()
    told_on_two = await stretch_on(db_session, session, two)
    told_on_two.take_id = assembled.id
    await db_session.commit()
    await _pressed_terminei(client, db_session, session.id)

    audio = (await release_packet(db_session, session))["audio"]

    assert [take["ordinal"] for take in audio["rehearsal_takes"]] == [1, 2, 3]
    assert [take["take_id"] for take in audio["rehearsal_takes"]] == [
        one.id,
        assembled.id,
        three.id,
    ]


async def test_the_short_way_answers_no_composed_take(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The answer to a correction names no passage the server built, because none is built.

    The key itself is gone rather than answered null: a reader finding it absent knows there is
    nothing of the kind to look for, where a null reads as a rebuilding that could not be done.
    """
    from app.api.internalization_room import segments as segments_api

    async def _heard(*_: Any, **__: Any) -> str:
        return "o trecho contado outra vez"

    monkeypatch.setattr(segments_api, "heard", _heard)
    session, (part,) = await rehearsed_in_parts(db_session, 1)
    told = await stretch_on(db_session, session, part)

    answered = await client.post(
        f"/api/internalization-room/sessions/{session.id}/segments/{told.id}/replace",
        headers={"X-Room-Key": "sala-de-teste", "X-Room-Device": "tablet-da-sala"},
        data={
            "take_id": part.id,
            "starts_ms": str(told.starts_ms),
            "ends_ms": str(told.ends_ms),
        },
        files={"file": ("de-novo.m4a", b"a equipe contou o trecho outra vez", "audio/mp4")},
    )

    assert answered.status_code == 200, answered.text
    assert "composed_take_id" not in answered.json()
