"""ENG-1799 — a silent check runs after each approval and its result is stored with the version."""

from __future__ import annotations

import hashlib
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import delete, null
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSceneRehearsal, IRSegment, IRSession, IRTake
from app.services.internalization_room import release_check
from app.services.internalization_room.back_translation import BackTranslationState
from app.services.internalization_room.release import approve_release
from app.services.internalization_room.segments import capture_segment, final_segments
from app.services.internalization_room.sessions import back_translation_of
from app.services.internalization_room.takes import TEXT_SEAM_PREFIX, takes_of
from tests.baker import make_app, make_role
from tests.release_harness import (
    CLIP_MS,
    PREFIX,
    a_claimed_device,
    a_p02_telling_with_the_swapped_cause,
    at_the_desk,
    checked_heard_and_approved,
    desk_passage_release,
    desk_release,
    ensaio_take,
    ready_session,
    releases_of,
    reported_playback,
    team_headers,
    the_one_part_of,
    the_part_recorded_again,
)
from tests.room_harness import room_client, the_bucket_is_in_memory
from tests.sentence_harness import re_record, rehearsed_in_wav, spoken

BYTES = b"the team's rehearsal"
NAMES = ["bytes_match_sha256", "frases_fit_their_takes", "nothing_awaiting_translation"]
NAMES += ["splices_intact", "every_origin_resolves", "everything_heard"]
NAMES += ["approval_matches_live_state", "manifest_names_the_same_takes"]


bucket = pytest.fixture(the_bucket_is_in_memory)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    from fastapi import FastAPI

    from app.api.internalization_room import router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    @asynccontextmanager
    async def handed():
        yield db_session

    monkeypatch.setattr(release_check, "AsyncSessionLocal", handed)
    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    test_app.dependency_overrides[get_db] = lambda: db_session
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=test_app), base_url="http://t"
    ) as c:
        yield c


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key="internalization-room", name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


async def _live(db: AsyncSession, session_id: str) -> IRSession:
    db.expire_all()
    return await db.get_one(IRSession, session_id)


async def _result(db: AsyncSession, session_id: str) -> dict[str, Any] | None:
    db.expire_all()
    (release,) = await releases_of(db, session_id)
    return release.release_check


async def _stored(db: AsyncSession, session_id: str) -> dict[str, bool] | None:
    result = await _result(db, session_id)
    return None if result is None else {c["name"]: c["passed"] for c in result["checks"]}


async def _rehearsed(db: AsyncSession, bucket) -> tuple[str, str]:
    project, credential = await a_claimed_device(db)
    session = await ready_session(db, project_id=project.id)
    session_id = session.id
    part = await the_one_part_of(db, session)
    part.sha256 = hashlib.sha256(BYTES).hexdigest()
    await db.commit()
    bucket.objects[part.storage_key] = BYTES
    return session_id, credential


async def _approved(client, db: AsyncSession, bucket) -> str:
    session_id, credential = await _rehearsed(db, bucket)
    await checked_heard_and_approved(client, db, session_id, headers=team_headers(credential))
    return session_id


async def _check_again(db: AsyncSession, session_id: str) -> dict[str, bool]:
    (release,) = await releases_of(db, session_id)
    release_id = release.id
    release.release_check = null()
    await db.commit()
    await release_check.check_release(release_id)
    return await _stored(db, session_id) or {}


async def test_an_approval_with_every_take_intact_stores_a_whole_result_once(
    client, db_session, bucket, monkeypatch, caplog
):
    session_id, credential = await _rehearsed(db_session, bucket)
    headers = team_headers(credential)
    await checked_heard_and_approved(client, db_session, session_id, headers=headers)
    first = await _result(db_session, session_id)
    bucket.objects.clear()
    (release,) = await releases_of(db_session, session_id)
    await release_check.check_release(release.id)
    monkeypatch.setattr(release_check, "take_store", lambda: 1 / 0)

    again = await client.post(f"{PREFIX}/sessions/{session_id}/release", headers=headers)

    assert again.status_code == 200, again.text
    assert not [record for record in caplog.records if record.levelname == "ERROR"]
    assert first["whole"] is True
    assert datetime.fromisoformat(first["ran_at"])
    assert await _result(db_session, session_id) == first
    assert await _stored(db_session, session_id) == dict.fromkeys(NAMES, True)


async def test_a_take_whose_bytes_no_longer_match_fails_check_one_and_the_approval_stands(
    client, db_session, bucket
):
    session_id, credential = await _rehearsed(db_session, bucket)
    part = await the_one_part_of(db_session, await _live(db_session, session_id))
    bucket.objects[part.storage_key] = b"someone else's bytes"

    approved = await client.post(
        f"{PREFIX}/sessions/{session_id}/release", headers=team_headers(credential)
    )

    assert approved.status_code == 200, approved.text
    assert approved.json()["version"] == 1
    assert await _stored(db_session, session_id) == {**dict.fromkeys(NAMES, True), NAMES[0]: False}
    assert (await _result(db_session, session_id))["whole"] is False


@pytest.mark.parametrize(
    "door",
    [lambda s, p, c: desk_release(s), lambda s, p, c: desk_passage_release(p, c)],
)
async def test_a_forced_approval_gets_its_check_like_any_other(
    client, db_session, room_app, bucket, door
):
    project, _credential = await a_claimed_device(db_session)
    project_id = project.id
    session = await a_p02_telling_with_the_swapped_cause(db_session, project)
    session_id, pericope = session.id, session.pericope
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    forced = await client.post(
        door(session_id, project_id, pericope), headers=desk, json={"force": True}
    )

    assert forced.status_code == 200, forced.text
    assert await _stored(db_session, session_id) == {**dict.fromkeys(NAMES, True), NAMES[0]: False}


async def _a_stretch_without_words(db: AsyncSession, session: IRSession) -> None:
    await capture_segment(
        db,
        session,
        take_id=(await the_one_part_of(db, session)).id,
        starts_ms=CLIP_MS,
        ends_ms=CLIP_MS + 9000,
        transcript=None,
    )


async def _a_listening_that_stops_short(db: AsyncSession, session: IRSession) -> None:
    told = await final_segments(db, session.id)
    state = BackTranslationState(
        scope=session.pericope,
        findings=[],
        checked=True,
        analysed_segment_ids=[one.id for one in told],
    )
    await reported_playback(db, session, state, played_ranges=[[0, 1000]])


def _the_take_runs(ms: int):
    async def run(db: AsyncSession, session: IRSession) -> None:
        (await the_one_part_of(db, session)).duration_ms = ms
        await db.commit()

    return run


async def _the_same_bytes_under_another_take(db: AsyncSession, session: IRSession) -> None:
    part = await the_one_part_of(db, session)
    part.set_aside_at = datetime.now(UTC)
    await db.commit()
    db.add(
        ensaio_take(
            session.id,
            scope=part.scope,
            ordinal=part.ordinal,
            sha256=part.sha256,
            created_at=part.created_at + timedelta(minutes=1),
            project_id=session.project_id,
        )
    )
    await db.commit()


async def _an_origin_nobody_kept(db: AsyncSession, session: IRSession) -> None:
    (await the_one_part_of(db, session)).origin = "no-such-scene-rehearsal"
    await db.commit()


@pytest.mark.parametrize(
    ("name", "after_the_approval"),
    [
        ("nothing_awaiting_translation", _a_stretch_without_words),
        ("everything_heard", _a_listening_that_stops_short),
        ("approval_matches_live_state", the_part_recorded_again),
        ("manifest_names_the_same_takes", _the_same_bytes_under_another_take),
        ("frases_fit_their_takes", _the_take_runs(1000)),
        ("every_origin_resolves", _an_origin_nobody_kept),
    ],
)
async def test_what_changes_after_the_approval_fails_its_check(
    client, db_session, bucket, name, after_the_approval
):
    session_id = await _approved(client, db_session, bucket)
    await after_the_approval(db_session, await _live(db_session, session_id))

    assert (await _check_again(db_session, session_id))[name] is False


async def _joined_from_a_scene_rehearsal(db: AsyncSession, session: IRSession) -> None:
    rehearsal = IRSceneRehearsal(
        session_id=session.id,
        pericope=session.pericope,
        n=1,
        device_id="tablet-1",
        storage_key="k",
        size_bytes=1,
        sha256="b" * 64,
        crc32c="c",
        content_type="audio/wav",
    )
    db.add(rehearsal)
    await db.commit()
    (await the_one_part_of(db, session)).origin = rehearsal.id
    await db.commit()


async def _declared(db: AsyncSession, session: IRSession) -> None:
    (await the_one_part_of(db, session)).storage_key = f"{TEXT_SEAM_PREFIX}/{session.id}/whole"
    await db.commit()


@pytest.mark.parametrize(
    ("name", "after_the_approval", "notes"),
    [
        ("every_origin_resolves", _joined_from_a_scene_rehearsal, 0),
        ("manifest_names_the_same_takes", _declared, 0),
        ("manifest_names_the_same_takes", the_part_recorded_again, 1),
        ("frases_fit_their_takes", _the_take_runs(CLIP_MS + 600), 1),
    ],
)
async def test_a_check_that_still_passes_after_the_approval_stores_its_notes(
    client, db_session, bucket, name, after_the_approval, notes
):
    session_id = await _approved(client, db_session, bucket)
    await after_the_approval(db_session, await _live(db_session, session_id))
    await _check_again(db_session, session_id)

    (check,) = [c for c in (await _result(db_session, session_id))["checks"] if c["name"] == name]

    assert check["passed"] is True
    assert len(check.get("notes", [])) == notes


async def _the_sentence_object_is_lost(db: AsyncSession, bucket, session_id: str) -> None:
    kept = {take.storage_key for take in await takes_of(db, session_id)}
    bucket.objects = {key: audio for key, audio in bucket.objects.items() if key in kept}


async def _the_parent_take_is_gone(db: AsyncSession, bucket, session_id: str) -> None:
    sentences = back_translation_of(await db.get_one(IRSession, session_id)).sentences
    await db.execute(delete(IRTake).where(IRTake.id == sentences[0].previous_take_id))
    await db.commit()


@pytest.mark.parametrize("loss", [_the_sentence_object_is_lost, _the_parent_take_is_gone])
async def test_a_splice_through_the_sentence_door_is_intact_until_something_of_it_is_lost(
    db_session, bucket, monkeypatch, loss
):
    async with room_client(db_session, monkeypatch) as door:
        session, _parts, (told,) = await rehearsed_in_wav(
            db_session, bucket, [[(0, 1000), (1000, 2000), (2000, 3000)]]
        )
        session_id = session.id
        assert (await re_record(door, session_id, told[1].id, spoken(1.0))).status_code == 200
    await approve_release(db_session, await _live(db_session, session_id), forced_by="desk")

    assert (await _check_again(db_session, session_id))["splices_intact"] is True

    await loss(db_session, bucket, session_id)

    assert (await _check_again(db_session, session_id))["splices_intact"] is False


async def test_a_check_that_breaks_leaves_the_release_without_a_result(
    client, db_session, bucket, monkeypatch
):
    monkeypatch.setattr(release_check, "take_store", lambda: 1 / 0)
    project, credential = await a_claimed_device(db_session)
    session_id = (await ready_session(db_session, project_id=project.id)).id

    approved = await client.post(
        f"{PREFIX}/sessions/{session_id}/release", headers=team_headers(credential)
    )

    assert approved.status_code == 200, approved.text
    assert await _stored(db_session, session_id) is None


@pytest.mark.parametrize(
    ("spans", "passed", "notes"),
    [
        ([("t1", 0, 1000), ("t1", 920, 2000)], False, 0),
        ([("t1", 0, 1000), ("t1", 950, 2000)], True, 0),
        ([("t1", 0, 1000), ("t1", 1600, 2000)], True, 1),
        ([("t1", 0, 2051)], False, 0),
        ([("t1", 0, 2050)], True, 0),
        ([("t1", 0, 2000), ("t2", 0, 500)], False, 0),
        ([("t1", 0, 1500)], True, 1),
        ([("t1", 0, 500), ("t1", 1000, 2000)], True, 1),
        ([("t1", 0, 501), ("t1", 1000, 2000)], True, 0),
        ([], False, 1),
    ],
)
def test_the_frases_fit_their_take_within_fifty_milliseconds(spans, passed, notes):
    part = IRTake(id="t1", duration_ms=2000)
    told = [
        IRSegment(id=f"s{n}", take_id=t, starts_ms=a, ends_ms=b)
        for n, (t, a, b) in enumerate(spans)
    ]

    verdict, noted = release_check.frases_fit_their_takes([part], told)

    assert (verdict, len(noted)) == (passed, notes)
