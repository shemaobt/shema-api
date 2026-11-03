"""ENG-1801 — a stretch is known by the frase its latest version froze, else by the live reading."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRRelease, IRSession
from app.services.internalization_room.back_translation import BackTranslationState
from app.services.internalization_room.segments import (
    capture_segment,
    divide_segment,
    final_segments,
)
from app.services.internalization_room.stretch_numbers import stretch_numbers
from tests.release_harness import (
    CLIP_MS,
    a_claimed_device,
    ready_session,
    releases_of,
    team_headers,
    team_release,
    the_one_part_of,
)
from tests.room_harness import room_client, the_bucket_is_in_memory


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    the_bucket_is_in_memory(monkeypatch)
    async with room_client(db_session, monkeypatch) as room:
        yield room


async def _two_stretches(db: AsyncSession, session: IRSession) -> BackTranslationState:
    part = await the_one_part_of(db, session)
    told = [
        await capture_segment(
            db,
            session,
            take_id=part.id,
            starts_ms=start,
            ends_ms=end,
            bridge_take_id="retro",
            transcript=words,
        )
        for start, end, words in ((0, 30000, "um"), (30000, CLIP_MS, "dois"))
    ]
    return BackTranslationState(
        scope=session.pericope, checked=True, analysed_segment_ids=[one.id for one in told]
    )


async def test_the_numbers_a_version_froze_outlive_a_division_after_it(client, db_session) -> None:
    project, credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id, tell=_two_stretches)
    first, second = await final_segments(db_session, session.id)
    first_id, second_id = first.id, second.id
    assert await stretch_numbers(db_session, session) == {first_id: 1, second_id: 2}
    approved = await client.post(team_release(session.id), headers=team_headers(credential))
    assert approved.status_code == 200, approved.text
    await divide_segment(db_session, session, first, at_ms=15000)

    assert await stretch_numbers(db_session, session) == {second_id: 2}


async def test_a_version_that_froze_no_numbers_answers_the_live_reading(client, db_session) -> None:
    project, credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id, tell=_two_stretches)
    approved = await client.post(team_release(session.id), headers=team_headers(credential))
    assert approved.status_code == 200, approved.text
    (release,) = await releases_of(db_session, session.id)
    packet = dict(release.packet)
    packet["back_translation"] = {
        **packet["back_translation"],
        "segments": [
            {k: v for k, v in one.items() if k != "frase"}
            for one in packet["back_translation"]["segments"]
        ],
    }
    release.packet = packet
    await db_session.commit()
    first, second = await final_segments(db_session, session.id)
    first_id, second_id = first.id, second.id
    await divide_segment(db_session, session, first, at_ms=15000)

    assert await stretch_numbers(db_session, session) == {second_id: 1}
    assert first_id not in await stretch_numbers(db_session, session)


async def test_the_latest_version_of_the_session_is_the_one_whose_numbers_hold(
    client, db_session
) -> None:
    project, credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id, tell=_two_stretches)
    approved = await client.post(team_release(session.id), headers=team_headers(credential))
    assert approved.status_code == 200, approved.text
    (first_version,) = await releases_of(db_session, session.id)
    later = {c.name: getattr(first_version, c.name) for c in IRRelease.__table__.columns}
    segments = first_version.packet["back_translation"]["segments"]
    later |= {
        "id": "later-version",
        "version": 2,
        "package_sha256": "f" * 64,
        "packet": {
            **first_version.packet,
            "back_translation": {
                **first_version.packet["back_translation"],
                "segments": [{**one, "frase": 3 - one["frase"]} for one in segments],
            },
        },
    }
    db_session.add(IRRelease(**later))
    await db_session.commit()
    first, second = await final_segments(db_session, session.id)

    assert await stretch_numbers(db_session, session) == {first.id: 2, second.id: 1}


async def test_the_numbers_are_the_sessions_own_and_never_another_sessions_version(
    client, db_session
) -> None:
    project, credential = await a_claimed_device(db_session)
    other = await ready_session(db_session, project_id=project.id, tell=_two_stretches)
    approved = await client.post(team_release(other.id), headers=team_headers(credential))
    assert approved.status_code == 200, approved.text
    mine = await ready_session(db_session, project_id=project.id, tell=_two_stretches)
    first, second = await final_segments(db_session, mine.id)
    await divide_segment(db_session, mine, first, at_ms=15000)

    assert await stretch_numbers(db_session, mine) == {second.id: 1}
