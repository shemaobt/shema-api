"""ENG-1261 — Zerar archives a passage's work and the team returns calmly to the passage choice.

A facilitator's Zerar stamps every live session of one team's pericope, in every language, and
the work hanging off them with one new **Archive**, and deletes the team's open-door pointers
for that pericope. Nothing else is deleted or moved. The cases go through the real routers with
a real tablet credential and a real facilitator's bearer, and read what a tablet or the Desk
observes. The cases about "nothing deleted" and "carries the archive's id" read the tables,
because that is what they assert.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.internalization_room import (
    IRCoverageEvent,
    IRQuestion,
    IRQuestionStatus,
    IRRelease,
    IRSegment,
    IRSession,
    IRTake,
    IRTeamSession,
)
from app.db.models.project import Project
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.canon.parse_map import ROOM_BOOK, load_book
from app.services.internalization_room.coverage import CoverageStatus
from app.services.internalization_room.sessions import (
    append_exchange,
    apply_coverage,
    get_session,
)
from tests.baker import (
    having_finished_the_passage,
    make_app,
    make_role,
)
from tests.opening_harness import (
    GUIDE_LINE,
    Script,
    a_scripted_room,
    another_tablet_of,
    desk_routes,
    the_tablet_opens,
    the_team_speaks,
)
from tests.release_harness import (
    PREFIX,
    P,
    a_claimed_device,
    at_the_desk,
    desk_release,
    desk_release_at,
    desk_retro,
    ensaio_take,
    ready_session,
    reported_playback,
    team_headers,
    team_release,
    told_back_with_an_open_finding,
)
from tests.room_harness import room_client, the_bucket_is_in_memory, the_room_speaks
from tests.tablet_turn_harness import the_room_opens

FIRST = load_book(ROOM_BOOK)[0].pericope_num
NOTHING_LIVE = "P05"

#: The five tables a Zerar stamps, each read by the session its rows hang off.
STAMPED = ("ir_sessions", "ir_takes", "ir_segments", "ir_coverage_events", "ir_releases")


@pytest.fixture()
def script(monkeypatch: pytest.MonkeyPatch) -> Script:
    return a_scripted_room(monkeypatch)


@pytest.fixture()
def per_request(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture()
def bucket(monkeypatch: pytest.MonkeyPatch):
    return the_bucket_is_in_memory(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, per_request, bucket, monkeypatch: pytest.MonkeyPatch):
    the_room_speaks(monkeypatch)
    async with room_client(db_session, monkeypatch, per_request=per_request) as c:
        yield c


@pytest.fixture()
async def desk_client(db_session: AsyncSession, per_request):
    async with desk_routes(db_session, per_request=per_request) as c:
        yield c


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key="internalization-room", name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


def zerar_url(team_id: str, pericope: str) -> str:
    return f"{PREFIX}/facilitator/projects/{team_id}/passages/{pericope}/archive"


async def zerar(
    client: httpx.AsyncClient, desk: dict[str, str], team_id: str, pericope: str
) -> dict[str, Any]:
    answered = await client.post(zerar_url(team_id, pericope), headers=desk)
    assert answered.status_code == 200, answered.text[:300]
    return answered.json()


async def a_retro_take_uploaded(
    client: httpx.AsyncClient, credential: str, session_id: str
) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/takes",
        headers=team_headers(credential),
        data={"kind": "retro", "scope": P},
        files={"file": ("retro.m4a", f"retro {uuid.uuid4()}".encode(), "audio/mp4")},
    )


def gone(response: httpx.Response, session_id: str) -> tuple[int, Any]:
    """The answer with the session's own id blanked, so two sessions' answers compare."""
    return response.status_code, json.loads(response.text.replace(session_id, "<id>"))


async def what_an_unknown_session_gets(
    client: httpx.AsyncClient, credential: str
) -> tuple[int, Any]:
    nobody = str(uuid.uuid4())
    read = await client.get(f"{PREFIX}/sessions/{nobody}", headers=team_headers(credential))
    return gone(read, nobody)


async def guide_lines(per_request: async_sessionmaker[AsyncSession], session_id: str) -> list[str]:
    async with per_request() as fresh:
        session = await get_session(fresh, session_id)
        return [line["text"] for line in session.messages or [] if line["role"] == "guide"]


async def stamps(
    per_request: async_sessionmaker[AsyncSession], table: str, session_ids: list[str]
) -> set[str | None]:
    column = "id" if table == "ir_sessions" else "session_id"
    placeholders = ", ".join(f":s{i}" for i in range(len(session_ids)))
    async with per_request() as fresh:
        rows = await fresh.execute(
            text(f"SELECT archive_id FROM {table} WHERE {column} IN ({placeholders})"),
            {f"s{i}": sid for i, sid in enumerate(session_ids)},
        )
        return {row[0] for row in rows.all()}


async def row_counts(per_request: async_sessionmaker[AsyncSession]) -> dict[str, int]:
    async with per_request() as fresh:
        return {
            model.__tablename__: await fresh.scalar(select(func.count()).select_from(model))
            for model in (IRSession, IRTake, IRSegment, IRCoverageEvent, IRRelease)
        }


async def archives_stored(per_request: async_sessionmaker[AsyncSession]) -> int:
    async with per_request() as fresh:
        return await fresh.scalar(text("SELECT count(*) FROM ir_archives"))


async def a_worked_and_approved_passage(
    client: httpx.AsyncClient,
    db: AsyncSession,
    per_request: async_sessionmaker[AsyncSession],
    team: Project,
    tablet: str,
) -> IRSession:
    """Turns, a kept rehearsal, a stretch told back, an approved release, a bead's event, and
    one recording kept in the bucket through the tablet's own upload."""
    session = await ready_session(db, project_id=team.id)
    approved = await client.post(team_release(session.id), headers=team_headers(tablet))
    assert approved.status_code == 200, approved.text[:300]
    async with per_request() as fresh:
        stored = await get_session(fresh, session.id)
        await append_exchange(
            fresh, stored, team_utterance="Noemi voltou com Rute", guide_response=GUIDE_LINE
        )
        fresh.add(
            IRCoverageEvent(
                session_id=session.id,
                project_id=team.id,
                pericope=P,
                element_key=element_keys(P)[0],
                status=CoverageStatus.ENGAGED.value,
            )
        )
        await fresh.commit()
    uploaded = await a_retro_take_uploaded(client, tablet, session.id)
    assert uploaded.status_code == 200, uploaded.text[:300]
    return session


async def what_the_facilitator_reads(
    client: httpx.AsyncClient, desk: dict[str, str], session_id: str
) -> dict[str, Any]:
    read: dict[str, Any] = {}
    for name, url in (
        ("conversation", f"{PREFIX}/facilitator/sessions/{session_id}/conversation"),
        ("takes", f"{PREFIX}/facilitator/sessions/{session_id}/takes"),
        ("release", desk_release_at(session_id, 1)),
        ("file", desk_retro(session_id)),
    ):
        answered = await client.get(url, headers=desk)
        assert answered.status_code == 200, f"{name}: {answered.text[:300]}"
        read[name] = answered.json()
    read["file"].pop("generated_at")
    return read


async def test_a_facilitators_zerar_keeps_all_of_a_pericopes_work_under_one_archive_stamped_with_the_time(  # noqa: E501
    client, db_session, per_request, room_app, bucket
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    session = await a_worked_and_approved_passage(client, db_session, per_request, team, tablet)
    before = await what_the_facilitator_reads(client, desk, session.id)
    counted = await row_counts(per_request)
    kept = set(bucket.objects)
    asked_at = datetime.now(UTC)

    answered = await zerar(client, desk, team.id, P)

    answered_by = datetime.now(UTC)
    assert answered["archived"] is True
    archived_at = datetime.fromisoformat(answered["archive"]["archived_at"])
    assert archived_at.tzinfo is not None
    assert asked_at <= archived_at <= answered_by
    for table in STAMPED:
        assert await stamps(per_request, table, [session.id]) == {answered["archive"]["id"]}, table
    assert await row_counts(per_request) == counted
    assert set(bucket.objects) == kept
    assert await what_the_facilitator_reads(client, desk, session.id) == before


async def test_the_archives_snapshot_holds_each_session_as_it_stood(
    client, db_session, per_request, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    approved = await a_worked_and_approved_passage(client, db_session, per_request, team, tablet)
    recorded_again = ensaio_take(
        approved.id,
        sha256="b" * 64,
        project_id=team.id,
        created_at=datetime.now(UTC) + timedelta(minutes=1),
    )
    db_session.add(recorded_again)
    await db_session.commit()
    spoken = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    assert spoken["session_id"] != approved.id
    kept = {approved.id: [{"part": None, "take_id": recorded_again.id}], spoken["session_id"]: []}
    stood: dict[str, dict[str, Any]] = {}
    async with per_request() as fresh:
        for session_id in (approved.id, spoken["session_id"]):
            session = await get_session(fresh, session_id)
            versions = await fresh.scalars(
                select(IRRelease.version)
                .where(IRRelease.session_id == session_id)
                .order_by(IRRelease.version)
            )
            stood[session_id] = {
                "status": session.status.value,
                "coverage": session.coverage_state,
                "turns": sum(1 for line in session.messages or [] if line["role"] == "guide"),
                "kept_takes": kept[session_id],
                "release_versions": list(versions),
            }

    answered = await zerar(client, desk, team.id, P)

    snapshot = {
        entry["session_id"]: {key: entry[key] for key in stood[approved.id]}
        for entry in answered["archive"]["sessions"]
    }
    assert snapshot == stood
    assert stood[approved.id]["turns"] == 1
    assert stood[approved.id]["release_versions"] == [1]


async def test_a_turn_on_an_archived_session_is_answered_as_the_session_gone(
    client, db_session, per_request, room_app, script
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    opened = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    await the_room_opens(client, tablet, opened["session_id"])
    await zerar(client, desk, team.id, P)
    said_before = await guide_lines(per_request, opened["session_id"])

    spoken = await the_team_speaks(client, script, tablet, opened["session_id"], "E depois?")

    assert gone(spoken, opened["session_id"]) == await what_an_unknown_session_gets(client, tablet)
    assert spoken.status_code == 404
    assert await guide_lines(per_request, opened["session_id"]) == said_before


async def test_a_turn_in_flight_when_the_zerar_lands_is_refused_and_writes_nothing(
    client, db_session, per_request, room_app, script
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    opened = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    await the_room_opens(client, tablet, opened["session_id"])
    said_before = await guide_lines(per_request, opened["session_id"])

    async def the_zerar_lands() -> None:
        await zerar(client, desk, team.id, P)

    script.meanwhile = the_zerar_lands

    spoken = await the_team_speaks(client, script, tablet, opened["session_id"], "E depois?")

    assert script.meanwhile is None, "the Zerar never landed inside the turn"
    assert await stamps(per_request, "ir_sessions", [opened["session_id"]]) != {None}
    assert gone(spoken, opened["session_id"]) == await what_an_unknown_session_gets(client, tablet)
    assert spoken.status_code == 404
    assert await guide_lines(per_request, opened["session_id"]) == said_before


async def test_the_state_read_and_a_take_upload_on_an_archived_session_are_answered_as_the_session_gone(  # noqa: E501
    client, db_session, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    opened = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    await zerar(client, desk, team.id, P)
    unknown = await what_an_unknown_session_gets(client, tablet)

    read = await client.get(
        f"{PREFIX}/sessions/{opened['session_id']}", headers=team_headers(tablet)
    )
    uploaded = await a_retro_take_uploaded(client, tablet, opened["session_id"])

    assert unknown[0] == 404
    assert gone(read, opened["session_id"]) == unknown
    assert gone(uploaded, opened["session_id"]) == unknown


async def test_the_next_open_after_a_zerar_mints_a_new_session_and_the_voice_opens_it(
    client, db_session, per_request, room_app, script
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    opened = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    await the_room_opens(client, tablet, opened["session_id"])
    the_opening = await guide_lines(per_request, opened["session_id"])
    assert len(the_opening) == 1
    await zerar(client, desk, team.id, P)

    reopened = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    await the_room_opens(client, tablet, reopened["session_id"])

    assert reopened["session_id"] != opened["session_id"]
    assert await guide_lines(per_request, reopened["session_id"]) == the_opening


async def test_the_new_session_after_a_zerar_starts_on_a_fresh_necklace(
    client, db_session, per_request, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    opened = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    async with per_request() as fresh:
        worked = await apply_coverage(
            fresh,
            opened["session_id"],
            dict.fromkeys(element_keys(P), CoverageStatus.ENGAGED.value),
        )
        assert worked.coverage_state != {}
    await zerar(client, desk, team.id, P)

    reopened = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})

    assert reopened["session_id"] != opened["session_id"]
    assert reopened["coverage"] == opened["coverage"]


async def test_a_bead_a_late_settle_writes_on_an_archived_session_is_not_carried_into_the_next_session(  # noqa: E501
    client, db_session, per_request, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    opened = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    await zerar(client, desk, team.id, P)
    async with per_request() as fresh:
        fresh.add(
            IRCoverageEvent(
                session_id=opened["session_id"],
                project_id=team.id,
                pericope=P,
                element_key=element_keys(P)[0],
                status=CoverageStatus.ENGAGED.value,
            )
        )
        await fresh.commit()

    reopened = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})

    assert reopened["session_id"] != opened["session_id"]
    assert reopened["coverage"] == opened["coverage"]


async def test_one_zerar_archives_the_pericopes_sessions_in_every_language(
    client, db_session, per_request, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    portuguese = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    english = await the_tablet_opens(client, tablet, {"pericope": P, "language": "en"})

    answered = await zerar(client, desk, team.id, P)

    both = [portuguese["session_id"], english["session_id"]]
    assert await stamps(per_request, "ir_sessions", both) == {answered["archive"]["id"]}
    assert sorted(entry["session_id"] for entry in answered["archive"]["sessions"]) == sorted(both)
    for language in ("pt", "en"):
        reopened = await the_tablet_opens(client, tablet, {"pericope": P, "language": language})
        assert reopened["session_id"] not in both, language
        assert reopened["language"] == language


async def test_reopening_on_another_tablet_after_a_zerar_never_lands_on_the_archived_session(
    client, db_session, room_app
) -> None:
    team, first_tablet = await a_claimed_device(db_session)
    second_tablet = await another_tablet_of(db_session, team)
    desk, _ = await at_the_desk(db_session, room_app, team)
    opened = await the_tablet_opens(client, first_tablet, {"pericope": P, "language": "pt"})
    await zerar(client, desk, team.id, P)

    on_the_second = await the_tablet_opens(client, second_tablet, {"pericope": P, "language": "pt"})
    on_the_first = await the_tablet_opens(client, first_tablet, {"pericope": P, "language": "pt"})

    assert on_the_second["session_id"] != opened["session_id"]
    assert on_the_first["session_id"] == on_the_second["session_id"]


async def test_an_open_that_finds_a_pointer_to_a_session_that_no_longer_exists_mints_a_new_session(
    client, db_session, per_request
) -> None:
    _team, tablet = await a_claimed_device(db_session)
    opened = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    async with per_request() as fresh:
        await fresh.execute(delete(IRSession).where(IRSession.id == opened["session_id"]))
        await fresh.commit()

    reopened = await client.post(
        f"{PREFIX}/sessions",
        headers=team_headers(tablet),
        json={"pericope": P, "language": "pt"},
    )

    assert reopened.status_code == 200, reopened.text[:300]
    assert reopened.json()["session_id"] != opened["session_id"]


async def test_an_open_that_finds_a_pointer_to_an_archived_session_mints_a_new_session(
    client, db_session, per_request, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    opened = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    await zerar(client, desk, team.id, P)
    async with per_request() as fresh:
        fresh.add(
            IRTeamSession(
                project_id=team.id, pericope=P, language="pt", session_id=opened["session_id"]
            )
        )
        await fresh.commit()

    reopened = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})

    assert reopened["session_id"] != opened["session_id"]


async def test_an_open_that_names_an_archived_panorama_as_the_session_before_it_is_answered_as_that_session_gone(  # noqa: E501
    client, db_session, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    panorama = await the_tablet_opens(client, tablet, {"pericope": "OV"})
    await zerar(client, desk, team.id, panorama["pericope"])

    entered = await client.post(
        f"{PREFIX}/sessions",
        headers=team_headers(tablet),
        json={"pericope": FIRST, "after_session": panorama["session_id"]},
    )

    assert gone(entered, panorama["session_id"]) == await what_an_unknown_session_gets(
        client, tablet
    )
    assert entered.status_code == 404


async def test_a_raised_hand_asked_on_the_pericope_before_a_zerar_is_still_in_the_facilitators_inbox(  # noqa: E501
    client, db_session, per_request, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    opened = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    async with per_request() as fresh:
        fresh.add(
            IRQuestion(
                session_id=opened["session_id"],
                device_id="tablet-1",
                project_id=team.id,
                pericope=P,
                status=IRQuestionStatus.OPEN,
                audio_key="internalization-room/questions/mao-levantada.m4a",
            )
        )
        await fresh.commit()
    inbox = f"{PREFIX}/facilitator/questions"
    before = await client.get(inbox, headers=desk, params={"team_id": team.id})
    assert before.status_code == 200, before.text[:300]
    assert len(before.json()["questions"]) == 1

    await zerar(client, desk, team.id, P)

    after = await client.get(inbox, headers=desk, params={"team_id": team.id})
    assert after.json() == before.json()
    assert [question["pericope"] for question in after.json()["questions"]] == [P]


async def test_a_zerar_of_the_panorama_archives_only_the_panoramas_sessions(
    client, db_session, per_request, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    worked = await the_tablet_opens(client, tablet, {"pericope": FIRST, "language": "pt"})
    panorama = await the_tablet_opens(client, tablet, {"pericope": "OV"})
    assert panorama["pericope"] == f"OV-{ROOM_BOOK}"

    answered = await zerar(client, desk, team.id, f"OV-{ROOM_BOOK}")

    assert await stamps(per_request, "ir_sessions", [panorama["session_id"]]) == {
        answered["archive"]["id"]
    }
    assert await stamps(per_request, "ir_sessions", [worked["session_id"]]) == {None}
    reopened = await the_tablet_opens(client, tablet, {"pericope": FIRST, "language": "pt"})
    assert reopened["session_id"] == worked["session_id"]


async def test_a_pericope_with_nothing_live_is_answered_with_no_archive_never_a_conflict(
    client, db_session, per_request, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})

    answered = await client.post(zerar_url(team.id, NOTHING_LIVE), headers=desk)

    assert answered.status_code == 200, answered.text[:300]
    assert answered.json() == {"archived": False, "archive": None}
    assert await archives_stored(per_request) == 0


async def test_a_second_zerar_never_touches_rows_an_earlier_one_stamped(
    client, db_session, per_request, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    first_session = await a_worked_and_approved_passage(
        client, db_session, per_request, team, tablet
    )
    first = await zerar(client, desk, team.id, P)
    second_session = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    uploaded = await a_retro_take_uploaded(client, tablet, second_session["session_id"])
    assert uploaded.status_code == 200, uploaded.text[:300]

    second = await zerar(client, desk, team.id, P)

    assert second["archive"]["id"] != first["archive"]["id"]
    for table in STAMPED:
        assert await stamps(per_request, table, [first_session.id]) == {first["archive"]["id"]}
    assert await stamps(per_request, "ir_sessions", [second_session["session_id"]]) == {
        second["archive"]["id"]
    }
    assert await stamps(per_request, "ir_takes", [second_session["session_id"]]) == {
        second["archive"]["id"]
    }
    assert [entry["session_id"] for entry in second["archive"]["sessions"]] == [
        second_session["session_id"]
    ]


async def test_release_versions_keep_counting_after_a_zerar(client, db_session, room_app) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    archived = await ready_session(db_session, project_id=team.id)
    first = await client.post(team_release(archived.id), headers=team_headers(tablet))
    assert first.status_code == 200, first.text[:300]
    await zerar(client, desk, team.id, P)
    after = await ready_session(db_session, project_id=team.id)

    second = await client.post(team_release(after.id), headers=team_headers(tablet))

    assert second.status_code == 200, second.text[:300]
    assert second.json()["version"] == 2
    v1 = await client.get(desk_release_at(archived.id, 1), headers=desk)
    v2 = await client.get(desk_release_at(after.id, 2), headers=desk)
    assert (v1.status_code, v2.status_code) == (200, 200)
    assert (v1.json()["version"], v2.json()["version"]) == (1, 2)


async def test_the_retroverification_file_of_a_new_session_lists_no_archived_draft(
    client, db_session, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    archived = await ready_session(db_session, project_id=team.id)
    first = await client.post(team_release(archived.id), headers=team_headers(tablet))
    assert first.status_code == 200, first.text[:300]
    await zerar(client, desk, team.id, P)
    after = await ready_session(db_session, project_id=team.id)

    unapproved = await client.get(desk_retro(after.id), headers=desk)
    approved = await client.post(team_release(after.id), headers=team_headers(tablet))
    listed = await client.get(desk_retro(after.id), headers=desk)

    assert unapproved.status_code == 200, unapproved.text[:300]
    assert unapproved.json()["releases"] == []
    assert approved.status_code == 200, approved.text[:300]
    assert [release["version"] for release in listed.json()["releases"]] == [2]


async def test_a_release_forced_on_an_archived_session_stays_in_its_own_archives_file(
    client, db_session, per_request, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    archived = await ready_session(db_session, project_id=team.id)
    first = await client.post(team_release(archived.id), headers=team_headers(tablet))
    assert first.status_code == 200, first.text[:300]
    await zerar(client, desk, team.id, P)
    after = await ready_session(db_session, project_id=team.id)
    async with per_request() as fresh:
        stored = await get_session(fresh, archived.id)
        await reported_playback(fresh, stored, await told_back_with_an_open_finding(fresh, stored))

    forced = await client.post(desk_release(archived.id), headers=desk, json={"force": True})

    assert forced.status_code == 200, forced.text[:300]
    new_file = await client.get(desk_retro(after.id), headers=desk)
    archived_file = await client.get(desk_retro(archived.id), headers=desk)
    assert new_file.json()["releases"] == []
    assert [release["version"] for release in archived_file.json()["releases"]] == [1, 2]


async def test_a_zerard_closed_passage_is_the_teams_passage_again(
    client, desk_client, db_session, per_request, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    opened = await the_tablet_opens(client, tablet, {"pericope": FIRST, "language": "pt"})
    async with per_request() as fresh:
        await having_finished_the_passage(fresh, await get_session(fresh, opened["session_id"]))
    pericopes = f"/api/facilitator/teams/{team.id}/pericopes"
    closed = await desk_client.get(pericopes, headers=desk)
    assert {row["pericope"]: row["position"] for row in closed.json()}[FIRST] == "closed"

    await zerar(client, desk, team.id, FIRST)

    standing = await desk_client.get(pericopes, headers=desk)
    assert {row["pericope"]: row["position"] for row in standing.json()}[FIRST] == "current"
    landed = await the_tablet_opens(client, tablet, {"language": "pt"})
    assert landed["pericope"] == FIRST
    assert landed["session_id"] != opened["session_id"]


async def test_the_facilitators_waiting_list_and_the_teams_history_leave_out_archived_sessions(
    client, desk_client, db_session, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    opened = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    called = await client.post(
        f"{PREFIX}/sessions/{opened['session_id']}/needs-person", headers=team_headers(tablet)
    )
    assert called.status_code == 200, called.text[:300]
    waiting = f"{PREFIX}/facilitator/sessions"
    history = f"/api/facilitator/teams/{team.id}/sessions"
    assert [
        row["session_id"] for row in (await client.get(waiting, headers=desk)).json()["sessions"]
    ] == [opened["session_id"]]
    assert [row["session_id"] for row in (await desk_client.get(history, headers=desk)).json()] == [
        opened["session_id"]
    ]

    await zerar(client, desk, team.id, P)

    assert (await client.get(waiting, headers=desk)).json()["sessions"] == []
    assert (await desk_client.get(history, headers=desk)).json() == []


async def test_the_teams_tablet_credential_cannot_zerar(client, db_session, per_request) -> None:
    team, tablet = await a_claimed_device(db_session)
    opened = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})

    refused = await client.post(zerar_url(team.id, P), headers=team_headers(tablet))

    assert refused.status_code == 401
    assert await stamps(per_request, "ir_sessions", [opened["session_id"]]) == {None}
    assert await archives_stored(per_request) == 0


async def test_a_facilitator_of_another_team_cannot_zerar_this_teams_pericope(
    client, db_session, per_request, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    other, _ = await a_claimed_device(db_session, email="outra@example.com")
    stranger, _ = await at_the_desk(db_session, room_app, other)
    opened = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    nobody = "nao-existe-em-lugar-nenhum"

    theirs = await client.post(zerar_url(team.id, P), headers=stranger)
    nothing = await client.post(zerar_url(nobody, P), headers=stranger)

    assert theirs.status_code == nothing.status_code == 404
    assert theirs.json() == nothing.json()
    assert await stamps(per_request, "ir_sessions", [opened["session_id"]]) == {None}
    assert await archives_stored(per_request) == 0
