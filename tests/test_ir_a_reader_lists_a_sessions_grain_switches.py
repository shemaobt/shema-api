"""ENG-2140 — a reader lists a session's grain switches, and the Desk's takes listing carries the
stamps the Ensaio Final trail reads.

A grain switch stamps every rehearsal take the session held with its time (ADR 0096), so the
switches are read back from those stamps: one per distinct `set_aside_at`, newest first, each
naming the grain it left, the grain it took and the takes it set aside. A switch that set nothing
aside leaves no stamp and is not listed. The facilitator's takes listing gives each take when the
server accepted it, when it stopped being live (ADR 0104) and its **Clock offset**; the team's
own wire keeps none of the three.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.internalization_room import back_translation as bt_api
from app.api.internalization_room import segments as segments_api
from app.core.config import get_settings
from app.db.models.internalization_room import IRSession, IRTake
from app.db.models.project import Project
from app.main import app as the_app
from app.services.auth.issue_tokens import issue_tokens
from app.services.internalization_room import takes as takes_service
from tests.baker import grant_room_app_role, make_app, make_role, make_user
from tests.device_harness import TABLET_TEAM
from tests.hard_stretch_harness import MemoryStore
from tests.release_harness import PREFIX, TABLET, a_claimed_device, at_the_desk
from tests.room_harness import (
    Analyst,
    a_scene_rehearsal,
    rehearsed_in_parts,
    room_client,
    the_analyst_reads,
    the_bucket_is_in_memory,
    the_room_speaks,
    upload_a_part,
)

HEADERS = {"X-Room-Device": TABLET}
ABSENT = "nao-existe-em-lugar-nenhum"
NOTHING_SET_ASIDE = (
    "A switch that set nothing aside, because nothing was recorded before it, leaves no entry."
)


@pytest.fixture(autouse=True)
def analyst(monkeypatch: pytest.MonkeyPatch) -> Analyst:
    the_room_speaks(monkeypatch)

    async def said(*_: Any, **__: Any) -> str:
        return "a equipe contou o trecho de volta"

    monkeypatch.setattr(segments_api, "heard", said)
    monkeypatch.setattr(bt_api, "heard", said)
    return the_analyst_reads(monkeypatch)


@pytest.fixture()
def store(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    return the_bucket_is_in_memory(monkeypatch)


@pytest.fixture()
def per_request(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, store: MemoryStore):
    monkeypatch.setattr(get_settings(), "gcs_platform_bucket", "balde-de-teste", raising=False)

    async def _signed(
        bucket: str,
        key: str,
        *,
        expiry_minutes: int,
        response_content_type: str | None = None,
        response_disposition: str | None = None,
    ) -> str:
        return f"https://storage.test/{bucket}/{key}?d={quote(response_disposition or '')}"

    monkeypatch.setattr(takes_service, "generate_signed_download_url", _signed)
    async with room_client(db_session, monkeypatch) as door:
        yield door


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key="internalization-room", name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    await make_role(db_session, app.id, role_key="consultant", label="Consultant", is_system=True)
    return app


@pytest.fixture()
async def desk(db_session: AsyncSession, room_app) -> dict[str, str]:
    team = await db_session.get(Project, TABLET_TEAM)
    assert team is not None
    headers, _ = await at_the_desk(db_session, room_app, team)
    return headers


@pytest.fixture()
async def consultant(db_session: AsyncSession, room_app) -> dict[str, str]:
    user = await make_user(db_session, email="consultora@example.com")
    await grant_room_app_role(db_session, user.id, "consultant")
    access, _refresh = await issue_tokens(db_session, user)
    return {"Authorization": f"Bearer {access}"}


def _switches_url(session_id: str) -> str:
    return f"{PREFIX}/facilitator/sessions/{session_id}/grain-switches"


async def _switches(
    client: httpx.AsyncClient, headers: dict[str, str], session_id: str
) -> dict[str, Any]:
    read = await client.get(_switches_url(session_id), headers=headers)
    assert read.status_code == 200, read.text
    switches: dict[str, Any] = read.json()
    return switches


async def _switched(client: httpx.AsyncClient, session_id: str, grain: str) -> dict[str, Any]:
    answered = await client.post(
        f"{PREFIX}/sessions/{session_id}/grain", json={"grain": grain}, headers=HEADERS
    )
    assert answered.status_code == 200, answered.text
    listing: dict[str, Any] = answered.json()
    return listing


async def _switched_within(
    client: httpx.AsyncClient, session_id: str, grain: str
) -> tuple[datetime, datetime]:
    before = datetime.now(UTC)
    await _switched(client, session_id, grain)
    return before, datetime.now(UTC)


async def _desk_listing(
    client: httpx.AsyncClient, desk: dict[str, str], session_id: str
) -> dict[str, Any]:
    read = await client.get(f"{PREFIX}/facilitator/sessions/{session_id}/takes", headers=desk)
    assert read.status_code == 200, read.text
    listing: dict[str, Any] = read.json()
    return listing


def _rehearsals(listing: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {take["take_id"]: take for take in listing["takes"] if take["kind"] == "ensaio"}


def _moment(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp)


def _the_second_now() -> datetime:
    """Now, to the second: the server's clock may be the database's, which keeps no less."""
    return datetime.now(UTC).replace(microsecond=0)


def _not_found(session_id: str) -> dict[str, str]:
    return {
        "detail": f"Internalization room session {session_id} not found",
        "code": "NOT_FOUND",
    }


def _kept(response: httpx.Response) -> str:
    assert response.status_code == 200, response.text
    take_id: str = response.json()["take_id"]
    return take_id


async def _parts(client: httpx.AsyncClient, session_id: str, *numbers: int) -> list[str]:
    return [
        _kept(await upload_a_part(client, session_id, part=n, audio=f"parte {n}".encode()))
        for n in numbers
    ]


async def _whole(client: httpx.AsyncClient, session_id: str, audio: bytes) -> str:
    return _kept(await upload_a_part(client, session_id, part=None, audio=audio))


async def _joined_with_the_tablet_at(
    client: httpx.AsyncClient,
    db: AsyncSession,
    session: IRSession,
    *,
    part: int,
    tablet_ahead: timedelta,
) -> str:
    rehearsal = await a_scene_rehearsal(db, session, part)
    return await _sent_with_the_tablet_at(
        client, session.id, part=part, tablet_ahead=tablet_ahead, origin=rehearsal.id
    )


async def _sent_with_the_tablet_at(
    client: httpx.AsyncClient,
    session_id: str,
    *,
    part: int,
    tablet_ahead: timedelta,
    origin: str | None = None,
) -> str:
    data = {
        "kind": "ensaio",
        "scope": f"parte-{part}",
        "chunk_index": str(part),
        "recorded_at": (datetime.now(UTC) + tablet_ahead).isoformat(),
    }
    if origin is not None:
        data["origin"] = origin
    return _kept(
        await client.post(
            f"{PREFIX}/sessions/{session_id}/takes",
            headers=HEADERS,
            data=data,
            files={"file": ("cena.wav", f"cena {part} {tablet_ahead}".encode(), "audio/wav")},
        )
    )


async def _scene_whole_scene(
    client: httpx.AsyncClient, db: AsyncSession
) -> tuple[IRSession, list[str], str, tuple[datetime, datetime], tuple[datetime, datetime]]:
    """Parts 1 and 2, a switch to the whole passage, a whole, then a switch back to scenes."""
    session, _ = await rehearsed_in_parts(db, 0)
    parts = await _parts(client, session.id, 1, 2)
    first = await _switched_within(client, session.id, "whole")
    whole = await _whole(client, session.id, b"a passagem inteira")
    second = await _switched_within(client, session.id, "scene")
    return session, parts, whole, first, second


async def test_a_session_recorded_by_scene_switched_to_whole_and_back_lists_two_switches_the_later_first_each_with_the_takes_it_set_aside(  # noqa: E501
    client: httpx.AsyncClient, db_session: AsyncSession, desk: dict[str, str]
) -> None:
    session, (p1, p2), whole, first, second = await _scene_whole_scene(client, db_session)
    listing = await _desk_listing(client, desk, session.id)
    rehearsals = _rehearsals(listing)
    a1 = rehearsals[p1]["set_aside_at"]
    a2 = rehearsals[whole]["set_aside_at"]

    answered = await _switches(client, desk, session.id)

    assert answered == {
        "switches": [
            {"at": a2, "from": "whole", "to": "scene", "take_ids": [whole]},
            {"at": a1, "from": "scene", "to": "whole", "take_ids": [p1, p2]},
        ]
    }
    assert rehearsals[p2]["set_aside_at"] == a1
    assert first[0] <= _moment(a1) <= first[1]
    assert second[0] <= _moment(a2) <= second[1]
    assert answered["switches"][0]["to"] == listing["grain"] == "scene"


async def test_a_session_never_switched_lists_no_switch(
    client: httpx.AsyncClient, db_session: AsyncSession, desk: dict[str, str]
) -> None:
    session, _ = await rehearsed_in_parts(db_session, 0)
    await _parts(client, session.id, 1)
    _kept(await upload_a_part(client, session.id, part=1, audio=b"parte 1 de novo"))
    await _parts(client, session.id, 2)

    assert await _switches(client, desk, session.id) == {"switches": []}


async def test_a_first_switch_over_nothing_recorded_lists_no_switch_and_the_listing_still_names_the_grain_in_force(  # noqa: E501
    client: httpx.AsyncClient, db_session: AsyncSession, desk: dict[str, str]
) -> None:
    session, _ = await rehearsed_in_parts(db_session, 0)
    await _switched(client, session.id, "whole")
    await _whole(client, session.id, b"a passagem inteira")

    assert await _switches(client, desk, session.id) == {"switches": []}
    assert (await _desk_listing(client, desk, session.id))["grain"] == "whole"


async def test_a_switch_back_over_nothing_recorded_since_lists_only_the_switch_that_set_takes_aside(
    client: httpx.AsyncClient, db_session: AsyncSession, desk: dict[str, str]
) -> None:
    session, _ = await rehearsed_in_parts(db_session, 0)
    p1, p2 = await _parts(client, session.id, 1, 2)
    before, after = await _switched_within(client, session.id, "whole")
    await _switched(client, session.id, "scene")

    answered = await _switches(client, desk, session.id)

    listing = await _desk_listing(client, desk, session.id)
    a1 = _rehearsals(listing)[p1]["set_aside_at"]
    assert answered == {
        "switches": [{"at": a1, "from": "scene", "to": "whole", "take_ids": [p1, p2]}]
    }
    assert before <= _moment(a1) <= after
    assert listing["grain"] == "scene"


async def test_a_take_of_the_grain_left_behind_that_lands_after_the_switch_is_listed_under_that_switch(  # noqa: E501
    client: httpx.AsyncClient, db_session: AsyncSession, desk: dict[str, str]
) -> None:
    session, _ = await rehearsed_in_parts(db_session, 0)
    p1, p2 = await _parts(client, session.id, 1, 2)
    await _switched(client, session.id, "whole")
    (p3,) = await _parts(client, session.id, 3)

    (only,) = (await _switches(client, desk, session.id))["switches"]

    assert only["take_ids"] == [p1, p2, p3]


async def test_a_whole_that_stepped_aside_for_scene_parts_is_listed_with_them_under_a_switch_from_scene(  # noqa: E501
    client: httpx.AsyncClient, db_session: AsyncSession, desk: dict[str, str]
) -> None:
    session, _ = await rehearsed_in_parts(db_session, 0)
    old_whole = await _whole(client, session.id, b"a antiga")
    p1, p2 = await _parts(client, session.id, 1, 2)
    await _switched(client, session.id, "whole")

    (only,) = (await _switches(client, desk, session.id))["switches"]

    assert (only["from"], only["to"]) == ("scene", "whole")
    assert only["take_ids"] == [old_whole, p1, p2]


async def test_a_whole_kept_after_scene_parts_with_no_switch_is_listed_with_them_under_a_switch_from_scene(  # noqa: E501
    client: httpx.AsyncClient, db_session: AsyncSession, desk: dict[str, str]
) -> None:
    session, _ = await rehearsed_in_parts(db_session, 0)
    p1, p2 = await _parts(client, session.id, 1, 2)
    late_whole = await _whole(client, session.id, b"a inteira depois das cenas")
    await _switched(client, session.id, "whole")

    (only,) = (await _switches(client, desk, session.id))["switches"]

    assert (only["from"], only["to"]) == ("scene", "whole")
    assert only["take_ids"] == [late_whole, p1, p2]


async def test_an_archived_session_lists_its_switches_to_the_facilitator(
    client: httpx.AsyncClient, db_session: AsyncSession, desk: dict[str, str]
) -> None:
    session, *_ = await _scene_whole_scene(client, db_session)
    before = await _switches(client, desk, session.id)

    zeroed = await client.post(
        f"{PREFIX}/facilitator/projects/{TABLET_TEAM}/passages/{session.pericope}/archive",
        headers=desk,
    )
    assert zeroed.status_code == 200, zeroed.text
    assert zeroed.json()["archived"] is True

    after = await client.get(_switches_url(session.id), headers=desk)
    assert after.status_code == 200, after.text
    assert after.json() == before
    assert len(before["switches"]) == 2


async def test_the_consultant_reads_the_switches_the_teams_facilitator_reads(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    desk: dict[str, str],
    consultant: dict[str, str],
) -> None:
    session, *_ = await _scene_whole_scene(client, db_session)

    by_facilitator = await _switches(client, desk, session.id)
    by_consultant = await _switches(client, consultant, session.id)

    assert by_consultant == by_facilitator
    assert len(by_consultant["switches"]) == 2


async def test_the_teams_tablet_credential_cannot_list_the_switches(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, *_ = await _scene_whole_scene(client, db_session)

    refused = await client.get(_switches_url(session.id), headers=HEADERS)

    assert refused.status_code == 401


async def test_a_facilitator_of_another_team_is_answered_as_a_session_that_does_not_exist(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    session, *_ = await _scene_whole_scene(client, db_session)
    other, _ = await a_claimed_device(db_session, email="outra@example.com")
    stranger, _ = await at_the_desk(db_session, room_app, other)

    theirs = await client.get(_switches_url(session.id), headers=stranger)
    nothing = await client.get(_switches_url(ABSENT), headers=stranger)

    assert theirs.status_code == nothing.status_code == 404
    assert theirs.json() == _not_found(session.id)
    assert nothing.json() == _not_found(ABSENT)


async def test_listing_the_switches_writes_nothing(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    per_request: async_sessionmaker[AsyncSession],
    desk: dict[str, str],
    consultant: dict[str, str],
) -> None:
    session, *_ = await _scene_whole_scene(client, db_session)

    async def what_is_stored() -> tuple[list[tuple[Any, ...]], tuple[Any, ...]]:
        async with per_request() as fresh:
            takes = await fresh.execute(
                select(IRTake.id, IRTake.set_aside_at, IRTake.superseded_at)
                .where(IRTake.session_id == session.id)
                .order_by(IRTake.id)
            )
            held = await fresh.execute(
                select(
                    IRSession.grain,
                    IRSession.grain_switched_at,
                    IRSession.version,
                    IRSession.updated_at,
                ).where(IRSession.id == session.id)
            )
            return [tuple(row) for row in takes.all()], tuple(held.one())

    before = await what_is_stored()

    for headers in (desk, consultant):
        await _switches(client, headers, session.id)

    assert await what_is_stored() == before


async def test_the_desks_takes_listing_says_when_the_server_accepted_each_take(
    client: httpx.AsyncClient, db_session: AsyncSession, desk: dict[str, str]
) -> None:
    session, _ = await rehearsed_in_parts(db_session, 0)
    before = _the_second_now()
    (part,) = await _parts(client, session.id, 1)
    after = datetime.now(UTC)

    listed = _rehearsals(await _desk_listing(client, desk, session.id))[part]
    accepted = _moment(listed["created_at"])

    assert accepted.tzinfo is not None
    assert before <= accepted <= after


async def test_a_take_recorded_again_under_its_number_carries_on_the_desks_listing_the_time_it_stopped_being_live(  # noqa: E501
    client: httpx.AsyncClient, db_session: AsyncSession, desk: dict[str, str]
) -> None:
    session, _ = await rehearsed_in_parts(db_session, 0)
    (first,) = await _parts(client, session.id, 1)
    before = _the_second_now()
    again = _kept(await upload_a_part(client, session.id, part=1, audio=b"parte 1 de novo"))
    after = datetime.now(UTC)

    rehearsals = _rehearsals(await _desk_listing(client, desk, session.id))

    assert rehearsals[first]["superseded_at"] is not None
    assert before <= _moment(rehearsals[first]["superseded_at"]) <= after
    assert rehearsals[again]["superseded_at"] is None


async def test_a_part_joined_from_a_tablet_six_minutes_ahead_carries_its_clock_offset_on_the_desks_listing(  # noqa: E501
    client: httpx.AsyncClient, db_session: AsyncSession, desk: dict[str, str]
) -> None:
    session, _ = await rehearsed_in_parts(db_session, 0)
    joined = await _joined_with_the_tablet_at(
        client, db_session, session, part=1, tablet_ahead=timedelta(minutes=6)
    )

    offset = _rehearsals(await _desk_listing(client, desk, session.id))[joined][
        "device_clock_offset_ms"
    ]

    assert offset is not None
    assert abs(offset - 360_000) <= 5_000


async def test_a_part_joined_four_minutes_off_or_recorded_on_the_tablet_carries_no_clock_offset(
    client: httpx.AsyncClient, db_session: AsyncSession, desk: dict[str, str]
) -> None:
    session, _ = await rehearsed_in_parts(db_session, 0)
    joined = await _joined_with_the_tablet_at(
        client, db_session, session, part=1, tablet_ahead=timedelta(minutes=4)
    )
    recorded = await _sent_with_the_tablet_at(
        client, session.id, part=2, tablet_ahead=timedelta(minutes=10)
    )

    rehearsals = _rehearsals(await _desk_listing(client, desk, session.id))

    assert rehearsals[joined]["device_clock_offset_ms"] is None
    assert rehearsals[recorded]["device_clock_offset_ms"] is None


def _resolved(spec: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    if "$ref" in schema:
        resolved: dict[str, Any] = spec["components"]["schemas"][schema["$ref"].rsplit("/", 1)[1]]
        return resolved
    return schema


def _answer_schema(spec: dict[str, Any], path: str) -> dict[str, Any]:
    door = spec["paths"][path]["get"]
    return _resolved(spec, door["responses"]["200"]["content"]["application/json"]["schema"])


def test_the_api_reference_documents_the_grain_switches_door_and_the_three_take_fields() -> None:
    spec = the_app.openapi()
    door_path = "/api/internalization-room/facilitator/sessions/{session_id}/grain-switches"

    answer = _answer_schema(spec, door_path)
    entry = _resolved(spec, answer["properties"]["switches"]["items"])
    takes = _answer_schema(spec, door_path.replace("grain-switches", "takes"))
    take = _resolved(spec, takes["properties"]["takes"]["items"])

    assert set(entry["properties"]) == {"at", "from", "to", "take_ids"}
    assert set(entry["properties"]["from"]["enum"]) == {"whole", "scene"}
    assert set(entry["properties"]["to"]["enum"]) == {"whole", "scene"}
    assert NOTHING_SET_ASIDE in " ".join(spec["paths"][door_path]["get"]["description"].split())
    assert {"created_at", "superseded_at", "device_clock_offset_ms"} <= set(take["properties"])
