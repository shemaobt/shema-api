"""ENG-1801 — the head of the retroverificação file carries her fields in her order.

Her `retroExport.ts` at the pin (18fa7c4) opens with the release, the version and the approval
it stands under. Read off the rows the room
wrote, through its own write paths.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession
from app.services.internalization_room.approved_draft import approved_draft
from app.services.internalization_room.passage_retroverification import NOT_APPROVED
from app.services.internalization_room.retro_export import retro_export
from app.services.internalization_room.segments import final_segments
from tests.baker import make_app, make_role
from tests.release_harness import (
    APP_KEY,
    CLIP_MS,
    a_claimed_device,
    a_p02_telling_with_the_swapped_cause,
    at_the_desk,
    checked_heard_and_approved,
    desk_release,
    ready_session,
    team_headers,
)
from tests.room_harness import room_client, the_bucket_is_in_memory


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    the_bucket_is_in_memory(monkeypatch)
    async with room_client(db_session, monkeypatch) as room:
        yield room


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


async def _exported(db: AsyncSession, session_id: str) -> dict:
    db.expire_all()
    session = await db.get(IRSession, session_id)
    assert session is not None
    exported = await retro_export(db, session, await approved_draft(db, session), "release-1")
    return exported.model_dump(mode="json", by_alias=True)


async def _approved(client, db: AsyncSession) -> tuple[IRSession, dict[str, str]]:
    project, credential = await a_claimed_device(db)
    session = await ready_session(db, project_id=project.id)
    headers = team_headers(credential)
    await checked_heard_and_approved(client, db, session.id, headers=headers)
    return session, headers


async def test_an_approved_passage_opens_with_her_keys_in_her_order(client, db_session) -> None:
    session, _ = await _approved(client, db_session)
    (stretch,) = await final_segments(db_session, session.id)
    pericope, stretch_id = session.pericope, stretch.id

    file = await _exported(db_session, session.id)

    assert list(file) == ["releaseId", "pericopeId", "version", "finalized", "approval"]
    assert (file["releaseId"], file["pericopeId"], file["version"], file["finalized"]) == (
        "release-1", pericope, 1, True,
    )  # fmt: skip
    approval = file["approval"]
    assert (approval["v"], approval["forced"], approval["conferida"]) == (1, False, True)
    assert approval["heardComplete"] is True
    assert approval["frases"] == [
        {"n": 1, "idx": stretch_id, "clipKey": "whole", "coversFrom": 0, "coversTo": CLIP_MS / 1000}
    ]


async def test_an_unapproved_passage_has_no_approval_and_says_so(db_session) -> None:
    project, _ = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id)

    file = await _exported(db_session, session.id)

    assert list(file) == ["releaseId", "pericopeId", "version", "finalized", "note", "approval"]
    assert (file["finalized"], file["approval"], file["version"]) == (False, None, 1)
    assert file["note"] == NOT_APPROVED


async def test_a_forced_approval_keeps_its_open_findings_by_address_and_never_the_note(
    client, db_session, room_app
) -> None:
    project, _ = await a_claimed_device(db_session)
    session = await a_p02_telling_with_the_swapped_cause(db_session, project)
    desk, _ = await at_the_desk(db_session, room_app, project)
    forced = await client.post(desk_release(session.id), headers=desk, json={"force": True})
    assert forced.status_code == 200, forced.text
    (stretch,) = await final_segments(db_session, session.id)
    stretch_id = stretch.id

    file = await _exported(db_session, session.id)
    approval = file["approval"]

    assert "note" not in file
    assert (approval["forced"], approval["conferida"]) == (True, False)
    assert approval["findings"] == [
        {"kind": "addition", "frase": 1, "idx": stretch_id, "clipKey": "whole"}
    ]
