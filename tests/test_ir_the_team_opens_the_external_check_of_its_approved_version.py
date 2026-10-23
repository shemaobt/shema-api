"""ENG-1421 — the team opens the Checagem externa of its approved version, one record per version.

The open is the team's door over a draft that stands approved (ADR 0071, ADR 0081): the first
open of a version keeps a copy of its parts and frases out of the release's stored packet, every
later open answers that record, and a new version opens a new one. Nothing closes it; a Zerar
stamps it with the passage's archive (ADR 0082).
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.db.models.internalization_room import IRExternalCheck, IRSession
from app.services.internalization_room import external_check as external_check_module
from app.services.internalization_room.back_translation import BackTranslationState
from app.services.internalization_room.segments import capture_segment
from tests.baker import make_app, make_role
from tests.release_harness import (
    APP_KEY,
    CLIP_MS,
    PREFIX,
    P,
    a_claimed_device,
    at_the_desk,
    checked_telling_back,
    claimed_tablets_of_one_team,
    desk_passage_release,
    ready_session,
    releases_of,
    reported_playback,
    team_headers,
    team_release,
    the_one_part_of,
    the_part_recorded_again,
)

LOGGER = "app.services.internalization_room.external_check"


@pytest.fixture()
async def client(db_session: AsyncSession):
    from fastapi import FastAPI

    from app.api.internalization_room import router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    async with httpx.AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as c:
        yield c


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


def external_check_open(session_id: str) -> str:
    return f"{PREFIX}/sessions/{session_id}/external-check/open"


async def approved(client: httpx.AsyncClient, session_id: str, credential: str) -> int:
    answered = await client.post(team_release(session_id), headers=team_headers(credential))
    assert answered.status_code == 200, answered.text[:300]
    version: int | None = answered.json()["version"]
    assert version is not None, answered.text[:300]
    return version


async def checks_of(db: AsyncSession, session_id: str) -> list[IRExternalCheck]:
    rows = await db.execute(
        select(IRExternalCheck)
        .where(IRExternalCheck.session_id == session_id)
        .order_by(IRExternalCheck.version)
        .execution_options(populate_existing=True)
    )
    return list(rows.scalars().all())


def opened_lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == LOGGER and record.getMessage().startswith("[checagem-externa] opened")
    ]


async def test_an_approved_passage_opens_its_external_check_for_version_one(client, db_session):
    team, credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=team.id)
    await approved(client, session.id, credential)

    opened = await client.post(external_check_open(session.id), headers=team_headers(credential))

    assert opened.status_code == 200, opened.text
    body = opened.json()
    assert body["version"] == 1
    assert body["check_id"]
    packet = (await releases_of(db_session, session.id))[0].packet
    assert body["takes"] == [
        {"take_id": take["take_id"], "key": take["key"]}
        for take in packet["audio"]["rehearsal_takes"]
    ]
    assert body["frases"] == [
        {
            "frase": segment["frase"],
            "segment_id": segment["segment_id"],
            "take_id": segment["take_id"],
            "starts_ms": segment["starts_ms"],
            "ends_ms": segment["ends_ms"],
        }
        for segment in packet["back_translation"]["segments"]
    ]
    assert body["takes"] and body["frases"]
    assert [check.id for check in await checks_of(db_session, session.id)] == [body["check_id"]]


async def test_the_first_open_writes_one_log_line_and_a_second_open_writes_none(
    client, db_session, caplog
):
    team, credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=team.id)
    await approved(client, session.id, credential)

    with caplog.at_level(logging.INFO, logger=LOGGER):
        first = await client.post(external_check_open(session.id), headers=team_headers(credential))
        after_the_first = opened_lines(caplog)
        second = await client.post(
            external_check_open(session.id), headers=team_headers(credential)
        )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert len(after_the_first) == 1, after_the_first
    assert P in after_the_first[0]
    assert " v1 " in after_the_first[0]
    assert session.id in after_the_first[0]
    assert opened_lines(caplog) == after_the_first, "a segunda abertura não avisa ninguém"


async def test_a_second_open_and_an_open_from_another_tablet_of_the_team_answer_the_same_check(
    client, db_session
):
    team, _facilitator, (tablet_a, tablet_b) = await claimed_tablets_of_one_team(
        db_session, email=f"duas-{uuid.uuid4()}@example.com", tablets=2
    )
    session = await ready_session(db_session, project_id=team.id)
    await approved(client, session.id, tablet_a.credential)

    answers = [
        await client.post(external_check_open(session.id), headers=team_headers(credential))
        for credential in (tablet_a.credential, tablet_a.credential, tablet_b.credential)
    ]

    assert [answer.status_code for answer in answers] == [200, 200, 200]
    assert len({answer.json()["check_id"] for answer in answers}) == 1
    assert len(await checks_of(db_session, session.id)) == 1


async def test_a_draft_never_approved_opens_nothing(client, db_session):
    team, credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=team.id)

    refused = await client.post(external_check_open(session.id), headers=team_headers(credential))

    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "DRAFT_NOT_APPROVED"
    assert await checks_of(db_session, session.id) == []


async def test_a_draft_changed_after_its_approval_opens_nothing_until_it_is_approved_again(
    client, db_session
):
    team, credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=team.id)
    await approved(client, session.id, credential)
    await the_part_recorded_again(db_session, session)

    refused = await client.post(external_check_open(session.id), headers=team_headers(credential))

    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "DRAFT_NOT_APPROVED"
    assert await checks_of(db_session, session.id) == []


async def test_a_new_approval_opens_a_new_check_and_the_first_one_stays_as_it_was(
    client, db_session
):
    team, credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=team.id)
    await approved(client, session.id, credential)
    first = await client.post(external_check_open(session.id), headers=team_headers(credential))
    (version_one,) = await checks_of(db_session, session.id)
    as_opened = json.dumps(
        {"version": version_one.version, "takes": version_one.takes, "frases": version_one.frases},
        sort_keys=True,
    )

    await the_part_recorded_again(db_session, session)
    await reported_playback(db_session, session, await checked_telling_back(db_session, session))
    assert await approved(client, session.id, credential) == 2
    second = await client.post(external_check_open(session.id), headers=team_headers(credential))
    again = await client.post(external_check_open(session.id), headers=team_headers(credential))

    assert first.json()["version"] == 1
    assert second.status_code == 200, second.text
    assert second.json()["version"] == 2
    assert second.json()["check_id"] != first.json()["check_id"]
    assert again.json()["check_id"] == second.json()["check_id"]
    assert second.json()["takes"] != first.json()["takes"]
    stored = await checks_of(db_session, session.id)
    assert [check.version for check in stored] == [1, 2]
    assert stored[0].id == first.json()["check_id"]
    assert (
        json.dumps(
            {"version": stored[0].version, "takes": stored[0].takes, "frases": stored[0].frases},
            sort_keys=True,
        )
        == as_opened
    ), "a checagem da versão 1 continua sendo a cópia do que a versão 1 aprovou"


async def test_two_opens_at_once_leave_one_check(client, db_session, monkeypatch):
    """The loser of a race read no record and then meets the winner's row at the index.

    Staged by holding the first lookup still, as it answered before the winner committed; the
    insert and the unique index that refuses it are real.
    """
    team, credential = await a_claimed_device(db_session)
    session_id = (await ready_session(db_session, project_id=team.id)).id
    await approved(client, session_id, credential)
    (release,) = await releases_of(db_session, session_id)
    winner = IRExternalCheck(
        release_id=release.id, session_id=session_id, version=1, takes=[], frases=[]
    )
    db_session.add(winner)
    await db_session.commit()
    winner_id = winner.id

    the_real_lookup = external_check_module.the_check_of
    held = {"still": True}

    async def _as_it_was_before_the_winner(*args, **kwargs):
        if held.pop("still", False):
            return None
        return await the_real_lookup(*args, **kwargs)

    monkeypatch.setattr(external_check_module, "the_check_of", _as_it_was_before_the_winner)
    opened = await client.post(external_check_open(session_id), headers=team_headers(credential))

    assert opened.status_code == 200, opened.text
    assert opened.json()["check_id"] == winner_id
    assert [check.id for check in await checks_of(db_session, session_id)] == [winner_id]


async def test_a_passage_the_desk_forced_opens_its_check(client, db_session, room_app):
    team, credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=team.id)
    desk, _facilitator = await at_the_desk(db_session, room_app, team)
    forced = await client.post(desk_passage_release(team.id, P), headers=desk, json={"force": True})
    assert forced.status_code == 200, forced.text

    opened = await client.post(external_check_open(session.id), headers=team_headers(credential))

    assert opened.status_code == 200, opened.text
    assert opened.json()["version"] == 1


async def test_another_teams_tablet_cannot_open_this_teams_check(client, db_session):
    team, credential = await a_claimed_device(db_session)
    _other_team, other_credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=team.id)
    await approved(client, session.id, credential)

    refused = await client.post(
        external_check_open(session.id), headers=team_headers(other_credential)
    )

    assert refused.status_code == 404, refused.text
    assert await checks_of(db_session, session.id) == []


async def test_a_facilitators_token_alone_opens_nothing(client, db_session, room_app):
    team, credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=team.id)
    await approved(client, session.id, credential)
    desk, _facilitator = await at_the_desk(db_session, room_app, team)

    refused = await client.post(external_check_open(session.id), headers=desk)

    assert refused.status_code == 401, refused.text
    assert await checks_of(db_session, session.id) == []


async def test_a_zerar_keeps_the_check_under_the_passages_archive(client, db_session, room_app):
    team, credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=team.id)
    await approved(client, session.id, credential)
    opened = await client.post(external_check_open(session.id), headers=team_headers(credential))
    desk, _facilitator = await at_the_desk(db_session, room_app, team)

    zeroed = await client.post(
        f"{PREFIX}/facilitator/projects/{team.id}/passages/{P}/archive", headers=desk
    )
    after = await client.post(external_check_open(session.id), headers=team_headers(credential))

    assert zeroed.status_code == 200, zeroed.text
    (kept,) = await checks_of(db_session, session.id)
    assert kept.id == opened.json()["check_id"]
    assert kept.archive_id == zeroed.json()["archive"]["id"]
    assert after.status_code == 404, after.text


async def told_in_two_stretches(db: AsyncSession, session: IRSession) -> BackTranslationState:
    part = await the_one_part_of(db, session)
    told = [
        await capture_segment(
            db,
            session,
            take_id=part.id,
            starts_ms=starts_ms,
            ends_ms=ends_ms,
            bridge_take_id=f"retro-{starts_ms}",
            transcript=transcript,
        )
        for starts_ms, ends_ms, transcript in (
            (0, CLIP_MS // 2, "Noemi voltou com Rute"),
            (CLIP_MS // 2, CLIP_MS, "Rute espigou no campo de Boaz"),
        )
    ]
    return BackTranslationState(
        scope=session.pericope,
        findings=[],
        checked=True,
        analysed_segment_ids=[stretch.id for stretch in told],
    )


async def a_version_stored_as_older_releases_were(
    client: httpx.AsyncClient,
    db: AsyncSession,
    *,
    team_id: str,
    credential: str,
    strip: Callable[[dict[str, Any]], None],
) -> str:
    """An approved version whose stored packet lacks what an older release never wrote."""
    session_id = (await ready_session(db, project_id=team_id, tell=told_in_two_stretches)).id
    await approved(client, session_id, credential)
    (release,) = await releases_of(db, session_id)
    strip(release.packet)
    flag_modified(release, "packet")
    await db.commit()
    return session_id


async def test_a_version_approved_before_frases_were_numbered_opens_with_its_stretches_unnumbered(
    client, db_session
):
    team, credential = await a_claimed_device(db_session)

    def _unnumbered(packet: dict[str, Any]) -> None:
        for segment in packet["back_translation"]["segments"]:
            del segment["frase"]

    session_id = await a_version_stored_as_older_releases_were(
        client, db_session, team_id=team.id, credential=credential, strip=_unnumbered
    )
    (release,) = await releases_of(db_session, session_id)

    opened = await client.post(external_check_open(session_id), headers=team_headers(credential))

    assert opened.status_code == 200, opened.text
    assert [(frase["frase"], frase["segment_id"]) for frase in opened.json()["frases"]] == [
        (None, segment["segment_id"]) for segment in release.packet["back_translation"]["segments"]
    ]
    assert len(opened.json()["frases"]) == 2


async def test_a_version_approved_before_the_telling_was_stored_opens_with_no_frases(
    client, db_session
):
    team, credential = await a_claimed_device(db_session)

    def _untold(packet: dict[str, Any]) -> None:
        del packet["back_translation"]["segments"]

    session_id = await a_version_stored_as_older_releases_were(
        client, db_session, team_id=team.id, credential=credential, strip=_untold
    )

    opened = await client.post(external_check_open(session_id), headers=team_headers(credential))

    assert opened.status_code == 200, opened.text
    assert opened.json()["frases"] == []
    assert opened.json()["takes"]
