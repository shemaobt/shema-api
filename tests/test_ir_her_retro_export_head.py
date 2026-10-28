"""ENG-1801 — the head of the retroverificação file carries her fields in her order.

Her `retroExport.ts` at the pin (18fa7c4) opens with the release, the version and the approval
it stands under. Read off the rows the room
wrote, through its own write paths.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession
from app.services.internalization_room.approved_draft import approved_draft
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    CheckRound,
    Nuance,
)
from app.services.internalization_room.passage_retroverification import (
    APPROVED_BEFORE_THE_RECORD,
    NOT_APPROVED,
)
from app.services.internalization_room.retro_export import retro_export
from app.services.internalization_room.segments import final_segments
from tests.baker import make_app, make_role
from tests.release_harness import (
    APP_KEY,
    CLIP_MS,
    a_claimed_device,
    a_p02_telling_with_the_swapped_cause,
    a_rehearsal_only_half_heard,
    at_the_desk,
    checked_heard_and_approved,
    desk_release,
    one_stretch,
    ready_session,
    team_headers,
    team_release,
    the_one_part_of,
    the_part_recorded_again,
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


async def test_a_draft_reopened_by_a_new_take_is_the_next_version(client, db_session) -> None:
    session, _ = await _approved(client, db_session)
    await the_part_recorded_again(db_session, session)

    file = await _exported(db_session, session.id)

    assert (file["version"], file["finalized"], file["approval"]) == (2, False, None)
    assert file["note"] == NOT_APPROVED


async def test_a_version_approved_before_the_record_has_no_approval_and_says_why(
    client, db_session
) -> None:
    session, _ = await _approved(client, db_session)
    release = await approved_draft(db_session, await db_session.get(IRSession, session.id))
    release.packet = {key: value for key, value in release.packet.items() if key != "check"}
    await db_session.commit()

    file = await _exported(db_session, session.id)

    assert (file["finalized"], file["version"], file["approval"]) == (True, 1, None)
    assert file["note"] == APPROVED_BEFORE_THE_RECORD


async def test_a_packet_minted_before_nuances_and_keys_were_stored_still_exports(
    client, db_session
) -> None:
    session, _ = await _approved(client, db_session)
    release = await approved_draft(db_session, await db_session.get(IRSession, session.id))
    packet = deepcopy(release.packet)
    del packet["check"]["nuances"]
    for one in packet["audio"]["rehearsal_takes"]:
        del one["key"], one["duration_ms"]
    for one in packet["back_translation"]["segments"]:
        del one["scene"]
    release.packet = packet
    release.version = 3
    approved_at = release.approved_at.isoformat()
    await db_session.commit()

    file = await _exported(db_session, session.id)

    approval = file["approval"]
    assert (file["version"], approval["v"], approval["at"]) == (3, 3, approved_at)
    assert "nuances" not in approval
    assert [(one["key"], one["durationMs"]) for one in approval["takes"]] == [("whole", None)]
    assert [one["clipKey"] for one in approval["frases"]] == ["whole"]


async def test_the_approval_pins_its_takes_and_its_nuances_with_what_the_voice_said(
    client, db_session
) -> None:
    project, credential = await a_claimed_device(db_session)

    async def _told(db, session) -> BackTranslationState:
        told = await one_stretch(db, session)
        part = await the_one_part_of(db, session)
        now = datetime.now(UTC)
        said = Nuance(
            note="n", chunk=1, segment_id=told.id, quote="Rute", story="s", take_id=part.id,
            starts_ms=0, ends_ms=CLIP_MS, voiced="now",
        )  # fmt: skip
        unsaid = said.model_copy(update={"quote": "Juda", "voiced": None})
        round_ = CheckRound(
            at=now, spoken="ok", outcome="pass", conferida=True, nuances=[said], heard_at=now
        )
        return BackTranslationState(
            scope=session.pericope, checked=True, checked_at=now, analysed_segment_ids=[told.id],
            nuances=[said, unsaid], checks=[round_],
        )  # fmt: skip

    session = await ready_session(db_session, project_id=project.id, tell=_told)
    answered = await client.post(team_release(session.id), headers=team_headers(credential))
    assert answered.status_code == 200, answered.text
    (stretch,) = await final_segments(db_session, session.id)
    part = await the_one_part_of(db_session, session)
    wanted = (stretch.id, part.id, part.sha256, part.size_bytes, part.duration_ms)

    approval = (await _exported(db_session, session.id))["approval"]

    assert approval["lastCheckAt"] is not None
    assert [one.get("voiced") for one in approval["nuances"]] == [
        "now",
        None,
    ]
    (take,) = approval["takes"]
    assert (take["key"], take["takeId"], take["sha256"], take["bytes"], take["durationMs"]) == (
        "whole", *wanted[1:]
    )  # fmt: skip
    assert approval["nuances"][0]["idx"] == wanted[0]


async def test_a_forced_approval_of_a_clean_check_with_a_part_unheard_says_so(
    client, db_session, room_app
) -> None:
    project, _ = await a_claimed_device(db_session)
    session = await a_rehearsal_only_half_heard(db_session, project)
    desk, _ = await at_the_desk(db_session, room_app, project)
    forced = await client.post(desk_release(session.id), headers=desk, json={"force": True})
    assert forced.status_code == 200, forced.text

    approval = (await _exported(db_session, session.id))["approval"]

    assert (approval["forced"], approval["conferida"], approval["heardComplete"]) == (
        True,
        True,
        False,
    )


async def test_a_packet_that_froze_no_frase_numbers_lists_no_frase_in_the_approval(
    client, db_session
) -> None:
    session, _ = await _approved(client, db_session)
    release = await approved_draft(db_session, await db_session.get(IRSession, session.id))
    packet = deepcopy(release.packet)
    for one in packet["back_translation"]["segments"]:
        del one["frase"]
    release.packet = packet
    await db_session.commit()

    assert (await _exported(db_session, session.id))["approval"]["frases"] == []
