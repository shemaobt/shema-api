"""The check refuses `terminei` on a part with nothing told over it, and names that part.

A part recorded again arrives carrying nobody's words: the stretches of the recording it
replaced went with that recording (ADR 0023), and no stretch anywhere points at the fresh one.
The untold errand walked the stretch rows only, so it saw a reading that was whole; the
listening errand is fed the takes the stretches name, so it could not see the part either. The
analyst then read the other parts, answered clean, and the passage was struck off the wheel —
and only the approval refused it, as `untold_part`, with no force and a facilitator called for
material the team can supply themselves (ADR 0026).

It is the untold stretch's own errand, asked of the parts: a part no standing stretch is a
slice of is untold ground, the room says the same family of lines over it, and the team is
sent to tell it back. It sits between the stretch and the listening, the order the release
gate already lists the three in — a part nobody told is owed a telling before it is owed a
playing.

These cases describe what the room answers and what it did not spend. They read the stored
state nowhere: a second press is how a case says the ladder advanced and was kept.
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSegment, IRSession, IRTake
from app.services.internalization_room.fail_safe import FailSafe, utterances
from app.services.internalization_room.segments import capture_segment
from tests.release_harness import rehearsed_session, the_one_part_of
from tests.room_harness import (
    Analyst,
    Room,
    a_piece_still_to_be_told,
    played_every_part,
    press_terminei,
    record_the_part_again,
    rehearsed_in_parts,
    room_client,
    stretch_on,
    tell_back_about,
    the_analyst_reads,
    the_room_speaks,
)

LANGUAGE = "pt"

#: The H family, read from the file the room speaks it out of. The case is that the team hears
#: *this family* and not one sentence of it: the lines rotate on the waiting ladder, so pinning
#: one would pin the ladder's position instead of the errand.
H_FAMILY = utterances(FailSafe.UNTOLD_STRETCH, LANGUAGE)

#: New bytes on every re-recording: a take is addressed by the hash of its audio, so the same
#: bytes twice are one row and no re-recording at all.
SECOND_TAKE = "d" * 64
WHOLE_AGAIN = "f" * 64
FIRST_TAKE = "g" * 64
THIRD_TAKE = "h" * 64


@pytest.fixture(autouse=True)
def analyst(monkeypatch: pytest.MonkeyPatch) -> Analyst:
    return the_analyst_reads(monkeypatch)


@pytest.fixture(autouse=True)
def room(monkeypatch: pytest.MonkeyPatch) -> Room:
    return the_room_speaks(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as door:
        yield door


async def _part_two_recorded_again(
    db: AsyncSession,
) -> tuple[IRSession, list[IRTake], IRTake]:
    """Three parts told back, and then the second one recorded again and left untold."""
    session, parts = await rehearsed_in_parts(db, 3)
    fresh = await record_the_part_again(db, session, parts[1], sha256=SECOND_TAKE)
    return session, parts, fresh


async def _tell_the_piece_back(db: AsyncSession, session: IRSession, piece: IRSegment) -> IRSegment:
    """Give a waiting piece its telling-back where it sits, so the first errand is done with."""
    return await capture_segment(
        db,
        session,
        take_id=piece.take_id,
        starts_ms=piece.starts_ms,
        ends_ms=piece.ends_ms,
        bridge_take_id="retro-da-cauda",
        transcript="a segunda metade contada de volta",
        pass_number=piece.pass_number,
        replaces=piece,
    )


async def test_a_part_recorded_again_and_never_told_back_refuses_the_check_and_names_it(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: Analyst,
    room: Room,
) -> None:
    """The rule. The fresh part is named on its own field, the room says so, nothing is read.

    The analyst is not asked, because what it would answer is a list of what is missing from a
    passage one of whose recordings nobody has explained — and a clean reading of the rest is
    what strikes the passage off the wheel for good.
    """
    session, (first, _second, third), fresh = await _part_two_recorded_again(db_session)

    answered = await press_terminei(
        client, session.id, report=played_every_part([first.id, fresh.id, third.id])
    )

    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["untold_take_ids"] == [fresh.id]
    assert body["checked"] is False
    assert body["untold_segment_id"] is None
    assert body["unheard_take_ids"] == []
    assert body["findings_remaining"] == 0
    assert body["audio_url"] != ""
    assert len(room.said) == 1
    assert room.said[0] in H_FAMILY
    assert analyst.readings == 0


async def test_pressed_again_the_room_says_the_next_line_and_still_asks_nobody(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: Analyst,
    room: Room,
) -> None:
    """The waiting ladder is walked and kept, the way it is for a stretch still to be told.

    A team pressing twice over the same hole hears the room stuck on one sentence unless the
    turn advanced and survived the request that spent it.
    """
    session, (first, _second, third), fresh = await _part_two_recorded_again(db_session)
    report = played_every_part([first.id, fresh.id, third.id])

    await press_terminei(client, session.id, report=report)
    again = await press_terminei(client, session.id, report=report)

    assert again.status_code == 200, again.text
    assert again.json()["untold_take_ids"] == [fresh.id]
    assert room.said == H_FAMILY[:2]
    assert analyst.readings == 0


async def test_an_untold_stretch_is_still_the_first_errand_and_the_part_the_next(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: Analyst,
) -> None:
    """A team owing both is sent on the older errand first, and on the part once it is done.

    One errand per press: the room answers the question the team is standing closest to, and
    the release lists the two codes independently because they are two different holes.
    """
    session, (first, second, third) = await rehearsed_in_parts(db_session, 3)
    piece = await a_piece_still_to_be_told(
        db_session, session, await stretch_on(db_session, session, first)
    )
    fresh = await record_the_part_again(db_session, session, second, sha256=SECOND_TAKE)
    report = played_every_part([first.id, fresh.id, third.id])

    on_the_stretch = await press_terminei(client, session.id, report=report)
    await _tell_the_piece_back(db_session, session, piece)
    on_the_part = await press_terminei(client, session.id, report=report)

    assert on_the_stretch.status_code == 200, on_the_stretch.text
    assert on_the_stretch.json()["untold_segment_id"] == piece.id
    assert on_the_stretch.json()["untold_take_ids"] == []
    assert on_the_part.status_code == 200, on_the_part.text
    assert on_the_part.json()["untold_take_ids"] == [fresh.id]
    assert on_the_part.json()["untold_segment_id"] is None
    assert analyst.readings == 0


async def test_the_untold_part_is_named_before_the_unheard_one(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: Analyst,
) -> None:
    """A part nobody told and nobody played is owed the telling first, as at the release.

    The listening errand would send the team to press play on a recording they still owe an
    explanation of, and answer the whole question about the wrong part.
    """
    session, (first, _second, _third), fresh = await _part_two_recorded_again(db_session)

    answered = await press_terminei(
        client, session.id, report=played_every_part([first.id, fresh.id])
    )

    assert answered.status_code == 200, answered.text
    assert answered.json()["untold_take_ids"] == [fresh.id]
    assert answered.json()["unheard_take_ids"] == []
    assert analyst.readings == 0


async def test_two_parts_recorded_again_are_both_named_in_the_order_they_read(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: Analyst,
) -> None:
    """Every part that owes a telling is named, and in the order the team tells them in.

    The later part is recorded again first on purpose: the order the rows were written in is
    the reverse of the order the passage reads, so an answer carrying the newest, or one of
    them, or any order at all, is not the same as an answer that reads the rehearsal.
    """
    session, (first, second, third) = await rehearsed_in_parts(db_session, 3)
    fresh_third = await record_the_part_again(db_session, session, third, sha256=THIRD_TAKE)
    fresh_first = await record_the_part_again(db_session, session, first, sha256=FIRST_TAKE)

    answered = await press_terminei(
        client,
        session.id,
        report=played_every_part([fresh_first.id, second.id, fresh_third.id]),
    )

    assert answered.status_code == 200, answered.text
    assert answered.json()["untold_take_ids"] == [fresh_first.id, fresh_third.id]
    assert analyst.readings == 0


async def test_a_rehearsal_nobody_told_back_yet_is_an_untold_part_and_not_a_room_that_did_not_hear(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: Analyst,
    room: Room,
) -> None:
    """The team recorded and pressed `terminei` before telling anything: the part owes a telling.

    That press used to answer the D family, *"I could not make anything out, can you tell me
    again?"*, which asks them to say again what they never said and puts a failure of the room
    where there was none — nothing was told for it to fail to hear. The recording standing with
    nothing over it is exactly this refusal, and it is the sentence that is true (ADR 0027).
    """
    session, _ = await rehearsed_session(db_session, language=LANGUAGE)
    part = await the_one_part_of(db_session, session)

    answered = await press_terminei(client, session.id, report=played_every_part([part.id]))

    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["untold_take_ids"] == [part.id]
    assert body["checked"] is False
    assert body["fixed_line"] == "", "the D family answers with a line and no clip; this is not it"
    assert body["audio_url"] != ""
    assert room.said[0] in H_FAMILY
    assert analyst.readings == 0


async def test_telling_the_fresh_part_back_reopens_the_path_to_the_verdict(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: Analyst,
) -> None:
    """The refusal is a door and not a wall: the errand done, the check runs and confers.

    Without this the refusal would be indistinguishable from a passage the room can no longer
    finish at all, which is the state the team cannot get out of by working.
    """
    session, (first, _second, third), fresh = await _part_two_recorded_again(db_session)
    await tell_back_about(db_session, session, fresh, bridge_take_id="retro-da-parte-regravada")

    answered = await press_terminei(
        client, session.id, report=played_every_part([first.id, fresh.id, third.id])
    )

    assert answered.status_code == 200, answered.text
    assert answered.json()["untold_take_ids"] == []
    assert answered.json()["checked"] is True
    assert analyst.readings == 1


async def test_a_rehearsal_told_whole_and_recorded_again_is_named_too(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: Analyst,
) -> None:
    """A passage recorded in one go is one part, and recording it again leaves it untold too.

    Nothing is retired here — an upload carrying no number says nothing about which part it
    replaces — so the telling the team already gave stands, on a recording that is no longer
    the part. The rule is about the part having nothing told over it and not about anything
    being taken away, so the answer is the same one.
    """
    session, _ = await rehearsed_session(db_session)
    told_whole = await the_one_part_of(db_session, session)
    await tell_back_about(db_session, session, told_whole, bridge_take_id="retro-do-inteiro")
    fresh = await record_the_part_again(db_session, session, told_whole, sha256=WHOLE_AGAIN)

    answered = await press_terminei(
        client, session.id, report=played_every_part([told_whole.id, fresh.id])
    )

    assert answered.status_code == 200, answered.text
    assert answered.json()["untold_take_ids"] == [fresh.id]
    assert answered.json()["checked"] is False
    assert analyst.readings == 0
