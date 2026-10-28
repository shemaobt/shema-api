"""ENG-1799 — a silent check runs after each approval and its result is stored with the version."""

from __future__ import annotations

import hashlib
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import httpx
import pytest
from sqlalchemy import null
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSegment, IRSession, IRTake
from app.services.internalization_room import release_check
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    LaidInSentence,
)
from app.services.internalization_room.segments import capture_segment, final_segments
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
    ready_session,
    releases_of,
    reported_playback,
    team_headers,
    the_one_part_of,
    the_part_recorded_again,
)
from tests.room_harness import the_bucket_is_in_memory

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


async def _an_origin_nobody_kept(db: AsyncSession, session: IRSession) -> None:
    (await the_one_part_of(db, session)).origin = "no-such-scene-rehearsal"
    await db.commit()


@pytest.mark.parametrize(
    ("name", "after_the_approval"),
    [
        ("nothing_awaiting_translation", _a_stretch_without_words),
        ("everything_heard", _a_listening_that_stops_short),
        ("approval_matches_live_state", the_part_recorded_again),
        ("manifest_names_the_same_takes", the_part_recorded_again),
        ("every_origin_resolves", _an_origin_nobody_kept),
    ],
)
async def test_what_changes_after_the_approval_fails_its_check(
    client, db_session, bucket, name, after_the_approval
):
    session_id, credential = await _rehearsed(db_session, bucket)
    await checked_heard_and_approved(
        client, db_session, session_id, headers=team_headers(credential)
    )
    await after_the_approval(db_session, await _live(db_session, session_id))

    assert (await _check_again(db_session, session_id))[name] is False


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
        ([("t1", 0, 1000), ("t1", 1000, 2000)], True, 0),
        ([("t1", 0, 1000), ("t1", 920, 2000)], False, 0),
        ([("t1", 0, 1000), ("t1", 950, 2000)], True, 0),
        ([("t1", 0, 1000), ("t1", 1600, 2000)], True, 1),
        ([("t1", 0, 2051)], False, 0),
        ([("t1", 0, 2050)], True, 0),
        ([("t1", 0, 2000), ("t2", 0, 500)], False, 0),
        ([], False, 0),
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


@pytest.mark.parametrize(
    ("sentence_sha", "previous", "intact"),
    [("a", "t0", True), ("b", "t0", False), ("a", "gone", False)],
)
def test_a_splice_is_intact_when_both_its_takes_stand_and_its_digest_is_the_takes(
    sentence_sha, previous, intact
):
    takes = [IRTake(id="t0", sha256="z"), IRTake(id="t1", sha256="a")]
    laid = LaidInSentence(
        sentence_id="x",
        segment_id="s",
        previous_take_id=previous,
        take_id="t1",
        starts_ms=0,
        ends_ms=1,
        sha256=sentence_sha,
        storage_key="k",
        heard_before=False,
    )

    assert release_check.splices_are_intact([laid], takes) is intact
