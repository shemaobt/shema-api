"""ENG-954 — a refused team approval names its blockers, on the finish route's own fields.

A refused team approval used to be a 409 with a sentence: the tablet's client throws on it and
learns nothing about which door is shut. It is a 200 now, the way the check's own refusals
already are (ENG-889's rule: the app infers nothing from absence), and for the three blockers
that have a door on the tablet — `untold_part`, `playback_did_not_cover_the_clip`,
`untold_stretch` — the answer also names the ground, on the same fields *terminei* already
uses: `untold_take_ids`, `unheard_take_ids`, `untold_segment_id` (ADR 0027).

The route-level cases that only change status live beside the ten refusal tests they replace
(`test_ir_a_release_is_refused_while_a_finding_is_open.py`,
`test_ir_a_release_is_a_numbered_row.py`). What is new here is the ground: a case has to record
audio or divide a stretch to reach `untold_part` or `untold_stretch`, which those two files have
no builder for.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.back_translation import BackTranslationState
from app.services.internalization_room.segments import final_segments
from tests.release_harness import (
    P,
    a_claimed_device,
    ready_session,
    releases_of,
    reported_playback,
    team_headers,
    team_release,
)
from tests.room_harness import (
    PART_MS,
    a_piece_still_to_be_told,
    heard_every_part,
    press_terminei,
    record_the_part_again,
    rehearsed_in_parts,
    room_client,
    the_analyst_reads,
    the_bucket_is_in_memory,
    the_room_speaks,
    upload_a_part,
)

UNTOLD_PART = "untold_part"
PLAYBACK_BLOCKER = "playback_did_not_cover_the_clip"
UNTOLD_STRETCH = "untold_stretch"

#: New bytes on every upload, because a take is addressed by the hash of its audio: the same
#: bytes twice are one row and no re-recording at all.
NEW_AUDIO = b"a equipe gravou a cena dois outra vez, para o teste da recusa da equipe"


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


async def test_a_part_recorded_again_and_not_told_back_refuses_the_team_by_its_take(
    client, db_session: AsyncSession
) -> None:
    """Path 1: a checked passage whose part two was recorded again and never told back.

    The check confers the other two parts clean, and then recording a part again starts the
    check over on its own — the passage the team is standing on has changed — so the room's
    answer carries `telling_back_not_checked` beside `untold_part`; only the second of the two
    has a door on the tablet, and only it names ground. Measured with the probe in ENG-954's
    report: the acceptance path names `untold_part` alone, and the sibling is real product
    behaviour the path left out.
    """
    project, credential = await a_claimed_device(db_session)
    session, _parts = await rehearsed_in_parts(db_session, 3, project_id=project.id)
    report = await heard_every_part(db_session, session.id)
    conferred = await press_terminei(client, session.id, report=report)
    assert conferred.status_code == 200, conferred.text

    recorded = await upload_a_part(client, session.id, part=2, audio=NEW_AUDIO)
    assert recorded.status_code == 200, recorded.text
    fresh_take_id = str(recorded.json()["take_id"])

    refused = await client.post(team_release(session.id), headers=team_headers(credential))

    assert refused.status_code == 200, refused.text
    body = refused.json()
    assert body["blockers"] == ["telling_back_not_checked", UNTOLD_PART]
    assert body["untold_take_ids"] == [fresh_take_id]
    assert body["unheard_take_ids"] == []
    assert body["untold_segment_id"] is None
    assert body["version"] is None
    assert body["release_id"] is None
    assert await releases_of(db_session, session.id) == []


async def test_an_untold_stretch_refuses_the_team_by_its_stretch(
    client, db_session: AsyncSession
) -> None:
    """Path 5: a stretch cut in two, its second half never told back.

    Nothing else about the session is wrong — comprehension supported, the floor met, the
    rehearsal heard through, the first half told and read — so this is the one door the
    `untold_stretch` blocker answers alone, on `untold_segment_id`.
    """
    project, credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id)
    (whole,) = await final_segments(db_session, session.id)

    tail = await a_piece_still_to_be_told(db_session, session, whole)

    refused = await client.post(team_release(session.id), headers=team_headers(credential))

    assert refused.status_code == 200, refused.text
    body = refused.json()
    assert body["blockers"] == [UNTOLD_STRETCH]
    assert body["untold_segment_id"] == tail.id
    assert body["untold_take_ids"] == []
    assert body["unheard_take_ids"] == []
    assert body["version"] is None
    assert await releases_of(db_session, session.id) == []


async def test_two_blockers_at_once_both_name_their_own_ground(
    client, db_session: AsyncSession
) -> None:
    """Path 11: a part recorded again beside a rehearsal only half heard.

    Both are missing material and neither yields to a force; the team's own answer names both
    codes, in the gate's order, each on its own field — never one field standing in for two
    errands (ADR 0027's rule, asked here of the release).

    The state is built by hand with `checked=True` after `record_the_part_again`, which no
    live session reaches: recording a part again resets `checked` on its own (ADR 0027), so a
    real session here would also carry `telling_back_not_checked`. This case is kept anyway
    because it is the one place two *grounded* blockers fire together, and what it proves —
    that each field lands on its own key and neither shadows the other — does not depend on
    the third, ungrounded code being absent.
    """
    project, credential = await a_claimed_device(db_session)
    session, (one, two) = await rehearsed_in_parts(db_session, 2, project_id=project.id)

    fresh = await record_the_part_again(db_session, session, two, sha256="f" * 64)
    (standing,) = await final_segments(db_session, session.id)
    state = BackTranslationState(
        scope=P, checked=True, findings=[], analysed_segment_ids=[standing.id]
    )
    await reported_playback(
        db_session, session, state, played_ranges=[[0, 20000]], clip_duration_ms=PART_MS
    )

    refused = await client.post(team_release(session.id), headers=team_headers(credential))

    assert refused.status_code == 200, refused.text
    body = refused.json()
    assert body["blockers"] == [UNTOLD_PART, PLAYBACK_BLOCKER]
    assert body["untold_take_ids"] == [fresh.id]
    assert body["unheard_take_ids"] == [one.id]
    assert body["untold_segment_id"] is None
    assert body["version"] is None
    assert await releases_of(db_session, session.id) == []
