"""The listening report names the part it was played from, and the gate names what failed.

A rehearsal is recorded in parts, and the team listens to one part at a time. The report the
tablet sends says so: one entry per part, spans in that part's own milliseconds, that part's
own length. So a part recorded again loses its own listening and nothing else, and the gate
can say which parts are unheard instead of only that something is.

The flat report the older tablets send is still accepted and still stored, and it is evidence
of nothing: it says a clip was played through without saying which clip, over a passage that
was never one file. Nothing is migrated — a session in flight plays its rehearsal through
again on the new build.

The release is the other side of the same evidence, and its cases live here too: a package
that travels on a report about a clip nobody will hear says downstream that a team listened
when nobody knows whether they did. A session refused for want of a report is refused for want
of a reading as well, and the handoff names both: the check waits while a part is unheard, so
a telling-back nobody played back to is a telling-back the analyst was never asked about.

These cases describe what the room decides. They do not read back how the report is stored,
except where the subject of the case is precisely that the flat numbers survive.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession, IRTake
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    unheard_parts,
)
from app.services.internalization_room.segments import capture_segment
from app.services.internalization_room.sessions import begin_back_translation_again
from tests.room_harness import (
    PART_MS,
    PLAYBACK_BLOCKER,
    P,
    a_rehearsed_session,
    another_rehearsal_take,
    heard_every_part,
    played_every_part,
    press_terminei,
    record_the_part_again,
    rehearsal_take,
    rehearsed_in_parts,
    release_blockers,
    release_packet,
    room_client,
    stored_telling_back,
    tell_back_about,
    the_analyst_reads,
    the_room_speaks,
)

#: The handoff names a telling-back the analyst never read. It stands beside the playback
#: blocker on every session refused for want of a report, because the check itself waits.
NEVER_ANALYSED = "telling_back_never_analysed"


@pytest.fixture(autouse=True)
def analyst(monkeypatch: pytest.MonkeyPatch) -> None:
    """The analyst reads the telling-back and finds nothing to raise."""
    the_analyst_reads(monkeypatch)


@pytest.fixture(autouse=True)
def voice(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Speaker and the synthesizer, so `terminei` answers without a model or a bucket."""
    the_room_speaks(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as room:
        yield room


async def _finish(
    client: httpx.AsyncClient, session_id: str, *, report: dict[str, Any] | None = None
) -> None:
    """Press `terminei`, with or without a report of what the tablet played."""
    answered = await press_terminei(client, session_id, report=report)
    assert answered.status_code == 200, answered.text


def _covering(take: IRTake, *, duration_ms: int = PART_MS) -> dict[str, Any]:
    """What the tablet sends about a part it played through, end to end."""
    return played_every_part([take.id], duration_ms=duration_ms)["played_by_take"][0]


async def _rehearsed_and_told_back(db: AsyncSession) -> IRSession:
    """A session that needs nothing but the report to travel: one part, one stretch told."""
    session, take = await a_rehearsed_session(db)
    await tell_back_about(db, session, take)
    return session


async def _told_back_on_a_new_part(db: AsyncSession, session: IRSession, *, sha256: str) -> IRTake:
    """The team started the telling-back over on a recording they made fresh."""
    take = rehearsal_take(session.id, sha256=sha256)
    db.add(take)
    await db.commit()
    await capture_segment(
        db,
        session,
        take_id=take.id,
        starts_ms=0,
        ends_ms=PART_MS,
        bridge_take_id="retro-do-recomeco",
        transcript="a passagem contada de novo do comeco",
    )
    return take


@pytest.mark.asyncio
async def test_four_parts_heard_confirm_and_a_replaced_part_fails_alone(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """The rule, in one case: listening is kept per part, and only the part that moved is lost.

    Under the flat report the same gesture threw away the team's listening to all four parts,
    because the one number it carried was about a passage that had stopped existing.
    """
    session, (a, b, c, d) = await rehearsed_in_parts(db_session, 4)

    await _finish(
        client,
        session.id,
        report={"played_by_take": [_covering(part) for part in (a, b, c, d)]},
    )
    heard = await release_packet(db_session, session)
    assert heard["readiness"] == "ready_for_refine"

    fresh_a = await record_the_part_again(db_session, session, a, sha256="e" * 64)

    assert await release_blockers(db_session, session) == [PLAYBACK_BLOCKER]
    assert unheard_parts(
        await stored_telling_back(db_session, session), sorted([fresh_a.id, b.id, c.id, d.id])
    ) == [fresh_a.id], "only the part the team recorded again is unheard"


@pytest.mark.asyncio
async def test_a_replaced_part_heard_again_confirms_without_the_others_replayed(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Playing the new part through is enough: the other three were already heard.

    The team is working, not erring, and a rule that made them sit through the whole rehearsal
    again for one retake would be paid for in the parts they start skipping.
    """
    session, (a, b, c, d) = await rehearsed_in_parts(db_session, 4)
    await _finish(
        client,
        session.id,
        report={"played_by_take": [_covering(part) for part in (a, b, c, d)]},
    )

    fresh_a = await record_the_part_again(db_session, session, a, sha256="e" * 64)
    await _finish(
        client,
        session.id,
        report={"played_by_take": [_covering(part) for part in (fresh_a, b, c, d)]},
    )

    assert (await release_packet(db_session, session))["readiness"] == "ready_for_refine"


@pytest.mark.asyncio
async def test_an_entry_for_a_recording_the_stretches_no_longer_name_is_ignored(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """An entry about a part nobody is standing on neither confirms nor denies anything.

    It is the residue of a part that was recorded again, and it is about audio no stretch is a
    slice of any more. Refusing on it would refuse a rehearsal that was in fact heard whole;
    letting it stand in for a part it does not name is the hole this ticket closes.
    """
    session, (a, b, c, d) = await rehearsed_in_parts(db_session, 4)
    await _finish(
        client,
        session.id,
        report={"played_by_take": [_covering(part) for part in (a, b, c, d)]},
    )

    fresh_a = await record_the_part_again(db_session, session, a, sha256="e" * 64)
    stored = await stored_telling_back(db_session, session)

    assert unheard_parts(stored, sorted([fresh_a.id, b.id, c.id, d.id])) == [fresh_a.id], (
        "the stale entry for the old part does not stand in for the new one"
    )
    assert unheard_parts(stored, sorted([b.id, c.id, d.id])) == [], (
        "a rehearsal that no longer names the part is heard on the three that remain"
    )


@pytest.mark.asyncio
async def test_a_flat_report_is_evidence_of_nothing(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """The test that fails if a flat report is ever read as evidence again.

    Both halves of the same rule. A tablet on an older build sends the two numbers over the
    glued passage and the release is refused; and a row written before this change, carrying no
    per-part key at all and a server-stamped subject that names exactly the rehearsal being
    asked about, is refused too. The numbers are kept either way, because they are the record of
    what that build reported.
    """
    session, parts = await rehearsed_in_parts(db_session, 4)
    glued = PART_MS * len(parts)
    ids = sorted(part.id for part in parts)

    await _finish(
        client,
        session.id,
        report={"played_ranges": [[0, glued]], "clip_duration_ms": glued},
    )
    stored = await stored_telling_back(db_session, session)
    in_flight = BackTranslationState.model_validate(
        {
            "scope": P,
            "played_ranges": [[0, glued]],
            "clip_duration_ms": glued,
            "played_take_ids": ids,
        }
    )

    assert await release_blockers(db_session, session) == [NEVER_ANALYSED, PLAYBACK_BLOCKER]
    assert stored.played_ranges == [(0, glued)], "the numbers are kept, as two ints now"
    assert stored.clip_duration_ms == glued
    assert stored.played_take_ids == ids
    assert unheard_parts(in_flight, ids) == ids, (
        "a row written before this change names every part, however the subject was stamped"
    )


def test_coverage_is_measured_per_part_with_the_tolerance() -> None:
    """750 ms of slack at each edge and between spans, per part, and never a percentage.

    The last part is Marcia's case: four minutes with twelve seconds unheard passes her 95 %
    and can hide a whole frase, which is why she argued for our absolute rule over her own.
    """
    entries = {
        "gap-of-750": ([[0, 4000], [4750, 10000]], 10000),
        "gap-of-751": ([[0, 4000], [4751, 10000]], 10000),
        "short-by-750": ([[0, 9250]], 10000),
        "short-by-751": ([[0, 9249]], 10000),
        "nothing-played": ([], 10000),
        "no-length-to-measure": ([[0, 10000]], 0),
        "four-minutes-missing-twelve-seconds": ([[0, 228000]], 240000),
    }
    state = BackTranslationState(
        played_by_take=[
            {"take_id": take_id, "played_ranges": ranges, "clip_duration_ms": duration}
            for take_id, (ranges, duration) in entries.items()
        ]
    )

    assert unheard_parts(state, sorted(entries)) == sorted(
        [
            "gap-of-751",
            "short-by-751",
            "nothing-played",
            "no-length-to-measure",
            "four-minutes-missing-twelve-seconds",
        ]
    )


@pytest.mark.asyncio
async def test_the_packet_carries_the_report_per_take(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """What travels to Refine is the report with a subject, and only that.

    The body carries both shapes, which is what a tablet mid-migration sends. The flat numbers
    stay in the row as the record of what was reported; the packet carries neither, because a
    consumer diffing the two versions must find them gone rather than find them unreliable.
    """
    session, parts = await rehearsed_in_parts(db_session, 4)
    glued = PART_MS * len(parts)
    per_take = [_covering(part) for part in parts]

    await _finish(
        client,
        session.id,
        report={
            "played_by_take": per_take,
            "played_ranges": [[0, glued]],
            "clip_duration_ms": glued,
        },
    )
    packet = await release_packet(db_session, session)

    assert packet["schema_version"] == "tripod.internalization-release.v0.5"
    assert packet["back_translation"]["played_by_take"] == per_take
    assert "played_ranges" not in packet["back_translation"]
    assert "clip_duration_ms" not in packet["back_translation"]


@pytest.mark.asyncio
async def test_terminei_without_a_report_takes_nothing_away(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """A press that carries nothing must not erase what the team already reported.

    `terminei` answers with no body at all, and it is pressed again whenever the first press
    failed after the analyst. A retry that wiped the report would cost the team the release for
    having pressed twice — and the app sends no body precisely when the clip did not run to its
    end, which is the press most likely to be repeated.
    """
    session, parts = await rehearsed_in_parts(db_session, 4)
    per_take = [_covering(part) for part in parts]
    await _finish(client, session.id, report={"played_by_take": per_take})

    await _finish(client, session.id)

    assert (await release_packet(db_session, session))["back_translation"][
        "played_by_take"
    ] == per_take


@pytest.mark.asyncio
async def test_a_flat_report_does_not_erase_the_parts_a_newer_build_named(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """An older build cannot take the subject away from a report that had one.

    The two builds meet on one session when a team changes tablet mid-passage. The older one
    sends the flat pair and nothing else — it cannot say what it did not measure, and silence
    about the parts is not a claim that none of them was played. Overwriting on that press
    erased a report that named every part and re-blocked a session that was ready to travel.
    """
    session, parts = await rehearsed_in_parts(db_session, 4)
    per_take = [_covering(part) for part in parts]
    glued = PART_MS * len(parts)
    await _finish(client, session.id, report={"played_by_take": per_take})

    await _finish(
        client,
        session.id,
        report={"played_ranges": [[0, glued]], "clip_duration_ms": glued},
    )

    packet = await release_packet(db_session, session)
    assert packet["back_translation"]["played_by_take"] == per_take


@pytest.mark.asyncio
async def test_a_replaced_attempt_archives_the_report_per_take(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Starting over keeps what the team reported about the rehearsal they threw away.

    Read where Refine reads it. The archived attempt is the history the packet carries, and a
    report that left no trace there would make the record say the team never listened — on the
    one recording where what they heard is all that is left of it.
    """
    session, parts = await rehearsed_in_parts(db_session, 4)
    glued = PART_MS * len(parts)
    per_take = [_covering(part) for part in parts]

    await _finish(
        client,
        session.id,
        report={
            "played_by_take": per_take,
            "played_ranges": [[0, glued]],
            "clip_duration_ms": glued,
        },
    )
    await begin_back_translation_again(db_session, session)
    started_over = await _told_back_on_a_new_part(db_session, session, sha256="e" * 64)
    await _finish(client, session.id, report={"played_by_take": [_covering(started_over)]})

    packet = await release_packet(db_session, session)
    archived = packet["back_translation"]["superseded_attempts"][-1]

    assert archived["played_by_take"] == per_take
    assert archived["played_ranges"] == [[0, glued]]
    assert archived["clip_duration_ms"] == glued


@pytest.mark.asyncio
async def test_a_release_with_no_report_of_playback_is_refused(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """The tablet says nothing about playback, which is what it says whenever the clip did not
    run to its end. Silence is not a claim that the team heard themselves."""
    session = await _rehearsed_and_told_back(db_session)

    await _finish(client, session.id)

    assert await release_blockers(db_session, session) == [NEVER_ANALYSED, PLAYBACK_BLOCKER]


@pytest.mark.asyncio
async def test_a_report_about_a_rehearsal_the_team_re_recorded_is_refused(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """The report was honest about the clip it was made of, and that clip is gone.

    Starting the telling-back over is what a re-record does, and it takes the report with it,
    so what reaches the gate is a session that told the new clip back and never said anybody
    played it. The package would otherwise travel on a report about audio nobody will hear.
    """
    session = await _rehearsed_and_told_back(db_session)
    await _finish(client, session.id, report=await heard_every_part(db_session, session.id))

    again = await another_rehearsal_take(db_session, session, sha256="b" * 64)
    await begin_back_translation_again(db_session, session)
    await tell_back_about(db_session, session, again)
    await _finish(client, session.id)

    assert await release_blockers(db_session, session) == [NEVER_ANALYSED, PLAYBACK_BLOCKER]


@pytest.mark.asyncio
async def test_a_fresh_report_after_a_re_record_releases(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Re-recording is the team working, not the team erring, and playing the new clip through
    has to be enough to release it."""
    session = await _rehearsed_and_told_back(db_session)
    await _finish(client, session.id, report=await heard_every_part(db_session, session.id))

    again = await another_rehearsal_take(db_session, session, sha256="b" * 64)
    await begin_back_translation_again(db_session, session)
    await tell_back_about(db_session, session, again)
    await _finish(client, session.id, report=await heard_every_part(db_session, session.id))

    assert (await release_packet(db_session, session))["readiness"] == "ready_for_refine"


@pytest.mark.asyncio
async def test_a_report_that_does_not_reach_the_end_of_its_clip_is_refused(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Control against regression: half a clip played is still half a clip played."""
    session = await _rehearsed_and_told_back(db_session)

    await _finish(
        client,
        session.id,
        report=await heard_every_part(db_session, session.id, played_ranges=[[0, 20000]]),
    )

    assert await release_blockers(db_session, session) == [NEVER_ANALYSED, PLAYBACK_BLOCKER]


@pytest.mark.asyncio
async def test_a_report_with_no_clip_to_measure_against_is_refused(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Stretches played, but no length to compare them to, so nothing can be checked.

    An entry carries both numbers, and neither alone is proof: spans with no length cannot be
    measured, and the other half — a length with nothing played — is a report that the team
    played nothing at all. A part whose length is zero is the first of those on the wire.
    """
    session = await _rehearsed_and_told_back(db_session)

    await _finish(
        client, session.id, report=await heard_every_part(db_session, session.id, duration_ms=0)
    )

    assert await release_blockers(db_session, session) == [NEVER_ANALYSED, PLAYBACK_BLOCKER]


@pytest.mark.asyncio
async def test_a_session_with_nothing_told_back_is_not_also_blamed_for_playback(
    db_session: AsyncSession,
) -> None:
    """One thing wrong is told to the team once.

    There is nothing to have played back before a stretch exists, so the room names what is
    actually missing and does not hand the team a second errand that would not help.
    """
    session, _ = await a_rehearsed_session(db_session)

    refused = await release_blockers(db_session, session)

    assert "no_telling_back" in refused
    assert PLAYBACK_BLOCKER not in refused
