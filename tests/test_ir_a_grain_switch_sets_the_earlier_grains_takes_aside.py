"""ENG-1765 — a grain switch sets the earlier grain's takes aside, and the newest grain stands.

The team moves between recording the passage whole and scene by scene through the grain door.
Every rehearsal take the session held is set aside with the switch's time, never deleted, and
the parts are then only the new grain's takes recorded after it, so a whole recorded after a
switch to the whole passage stands beside numbered takes. The telling-back starts over, a switch
to the grain in force changes nothing, and over an approved draft the door wants the armed tap.
Her switch is `src/draft/grainSwitch.ts` at 18fa7c4; the wire values are hers (`whole`, `scene`).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.api.internalization_room import back_translation as bt_api
from app.api.internalization_room import segments as segments_api
from app.core.config import get_settings
from app.db.models.auth import App
from app.db.models.internalization_room import IRSegment, IRSession
from app.db.models.project import Project
from app.services.internalization_room import sessions as sessions_service
from app.services.internalization_room import takes as takes_service
from app.services.internalization_room.back_translation import BackTranslationState
from app.services.internalization_room.release import approve_release
from app.services.internalization_room.segments import capture_segment, final_segments
from app.services.internalization_room.sessions import get_session
from tests.baker import make_app, make_role
from tests.device_harness import TABLET_TEAM
from tests.hard_stretch_harness import MemoryStore
from tests.release_harness import (
    APP_KEY,
    PREFIX,
    TABLET,
    a_claimed_device,
    at_the_desk,
    checked_heard_and_approved,
    desk_retro,
    ready_session,
    reported_playback,
    team_headers,
)
from tests.room_harness import (
    PART_MS,
    Analyst,
    a_scene_rehearsal,
    played_every_part,
    press_terminei,
    rehearsed_in_parts,
    release_packet,
    room_client,
    stored_telling_back,
    the_analyst_reads,
    the_bucket_is_in_memory,
    the_room_speaks,
    upload_a_part,
)

HEADERS = {"X-Room-Device": TABLET}


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
async def desk(db_session: AsyncSession) -> dict[str, str]:
    room_app: App = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(
        db_session, room_app.id, role_key="facilitator", label="Facilitator", is_system=True
    )
    team = await db_session.get(Project, TABLET_TEAM)
    assert team is not None
    headers, _ = await at_the_desk(db_session, room_app, team)
    return headers


async def _switch(
    client: httpx.AsyncClient,
    session_id: str,
    grain: str,
    *,
    headers: dict[str, str] | None = None,
    reopens_the_approved_draft: bool = False,
) -> httpx.Response:
    body: dict[str, Any] = {"grain": grain}
    if reopens_the_approved_draft:
        body["reopens_the_approved_draft"] = True
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/grain", json=body, headers=headers or HEADERS
    )


async def _switched(client: httpx.AsyncClient, session_id: str, grain: str) -> dict[str, Any]:
    answered = await _switch(client, session_id, grain)
    assert answered.status_code == 200, answered.text
    listing: dict[str, Any] = answered.json()
    return listing


async def _listing(client: httpx.AsyncClient, session_id: str) -> dict[str, Any]:
    listed = await client.get(f"{PREFIX}/sessions/{session_id}/takes", headers=HEADERS)
    assert listed.status_code == 200, listed.text
    listing: dict[str, Any] = listed.json()
    return listing


def _rehearsals(listing: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {take["take_id"]: take for take in listing["takes"] if take["kind"] == "ensaio"}


def _moment(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp)


def _kept(response: httpx.Response) -> str:
    assert response.status_code == 200, response.text
    take_id: str = response.json()["take_id"]
    return take_id


async def _joined_upload(
    client: httpx.AsyncClient, session_id: str, *, part: int, origin: str
) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/takes",
        headers=HEADERS,
        data={
            "kind": "ensaio",
            "scope": f"parte-{part}",
            "chunk_index": str(part),
            "origin": origin,
        },
        files={"file": ("cena.wav", f"cena {part}".encode(), "audio/wav")},
    )


async def _joined_parts(
    client: httpx.AsyncClient, db: AsyncSession, session: IRSession
) -> list[str]:
    parts = []
    for part in (1, 2):
        rehearsal = await a_scene_rehearsal(db, session, part)
        parts.append(
            _kept(await _joined_upload(client, session.id, part=part, origin=rehearsal.id))
        )
    return parts


async def _recorded_parts(
    client: httpx.AsyncClient, db: AsyncSession
) -> tuple[IRSession, list[str]]:
    """Two parts kept through the keep door, each told back over its whole length."""
    session, _ = await rehearsed_in_parts(db, 0)
    parts = []
    for part in (1, 2):
        take_id = _kept(
            await upload_a_part(client, session.id, part=part, audio=f"parte {part}".encode())
        )
        await _told_over(db, session, take_id, f"a parte {part} contada de volta")
        parts.append(take_id)
    return session, parts


async def _told_over(db: AsyncSession, session: IRSession, take_id: str, words: str) -> IRSegment:
    return await capture_segment(
        db,
        session,
        take_id=take_id,
        starts_ms=0,
        ends_ms=PART_MS,
        bridge_take_id=f"retro-{take_id}",
        transcript=words,
    )


async def _switched_to_the_whole_over_joined_parts(
    client: httpx.AsyncClient, db: AsyncSession
) -> tuple[IRSession, list[str], str, datetime, datetime]:
    """Two joined scene parts, a switch to the whole passage, and the whole recorded after it.

    Answers the session, the parts, the whole, and the moments just before and after the switch.
    """
    session, _ = await rehearsed_in_parts(db, 0)
    parts = await _joined_parts(client, db, session)
    before = datetime.now(UTC)
    await _switched(client, session.id, "whole")
    after = datetime.now(UTC)
    whole = _kept(await upload_a_part(client, session.id, part=None, audio=b"a passagem inteira"))
    return session, parts, whole, before, after


async def _downloads(
    client: httpx.AsyncClient, desk: dict[str, str], session_id: str
) -> dict[str, Any]:
    read = await client.get(
        f"{PREFIX}/facilitator/sessions/{session_id}/takes/downloads", headers=desk
    )
    assert read.status_code == 200, read.text
    downloads: dict[str, Any] = read.json()
    return downloads


async def _approval(client: httpx.AsyncClient, session_id: str) -> dict[str, Any] | None:
    read = await client.get(f"{PREFIX}/sessions/{session_id}", headers=HEADERS)
    assert read.status_code == 200, read.text
    approval: dict[str, Any] | None = read.json()["approved"]
    return approval


def _one_instant(stamps: list[str | None], before: datetime, after: datetime) -> datetime:
    assert None not in stamps, f"uma tomada da gravação anterior ficou de pé: {stamps}"
    (instant,) = {_moment(stamp) for stamp in stamps if stamp is not None}
    assert before <= instant <= after, "a marca não é a hora da troca"
    return instant


async def test_after_a_switch_to_the_whole_passage_a_whole_take_is_the_one_part_and_the_joined_scene_parts_are_set_aside(  # noqa: E501
    client: httpx.AsyncClient, db_session: AsyncSession, desk: dict[str, str], store: MemoryStore
) -> None:
    session, _ = await rehearsed_in_parts(db_session, 0)
    parts = await _joined_parts(client, db_session, session)
    kept_objects = set(store.objects)

    before = datetime.now(UTC)
    switched = await _switched(client, session.id, "whole")
    after = datetime.now(UTC)

    assert switched["grain"] == "whole"
    answered = _rehearsals(switched)
    instant = _one_instant([answered[part]["set_aside_at"] for part in parts], before, after)

    kept = await upload_a_part(client, session.id, part=None, audio=b"a passagem inteira")

    assert kept.status_code == 200, kept.text
    whole = kept.json()["take_id"]
    assert kept.json()["set_aside_at"] is None, "a passagem inteira gravada depois da troca caiu"
    downloads = await _downloads(client, desk, session.id)
    assert [take["key"] for take in downloads["takes"]] == ["whole"]
    assert downloads["takes"][0]["take_id"] == whole
    aside = downloads["superseded_takes"]
    assert [take["take_id"] for take in aside] == parts
    assert [take["key"] for take in aside] == ["S1", "S2"]
    for take in aside:
        assert _moment(take["set_aside_at"]) == instant
        assert _moment(take["superseded_at"]) == instant
        assert take["filename"].endswith(f"-substituida-{take['take_id']}.wav")
    assert len(_rehearsals(await _listing(client, session.id))) == 3, "a troca apagou uma tomada"
    assert kept_objects <= set(store.objects)


async def test_after_a_switch_to_scene_by_scene_the_parts_stand_and_the_whole_is_set_aside(
    client: httpx.AsyncClient, db_session: AsyncSession, desk: dict[str, str]
) -> None:
    session, _ = await rehearsed_in_parts(db_session, 0)
    whole = _kept(await upload_a_part(client, session.id, part=None, audio=b"inteira"))

    switched = await _switched(client, session.id, "scene")

    assert switched["grain"] == "scene"
    assert _rehearsals(switched)[whole]["set_aside_at"] is not None
    for part in (1, 2):
        _kept(await upload_a_part(client, session.id, part=part, audio=f"cena {part}".encode()))
    downloads = await _downloads(client, desk, session.id)
    assert [take["key"] for take in downloads["takes"]] == ["S1", "S2"]
    (aside,) = downloads["superseded_takes"]
    assert aside["take_id"] == whole
    assert aside["set_aside_at"] is not None, "a inteira deixada de lado não diz que foi a troca"


async def test_a_switch_to_the_grain_in_force_changes_nothing(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, parts = await _recorded_parts(client, db_session)
    checked = await press_terminei(
        client, session.id, report=played_every_part(parts, duration_ms=PART_MS)
    )
    assert checked.json()["checked"] is True, checked.text
    stored_before = await stored_telling_back(db_session, session)

    switched = await _switched(client, session.id, "scene")

    assert switched["grain"] == "scene"
    assert [take["set_aside_at"] for take in _rehearsals(switched).values()] == [None, None]
    stored = await stored_telling_back(db_session, session)
    assert len(stored.superseded) == len(stored_before.superseded)
    assert stored.checks == stored_before.checks
    assert stored.checked is True


async def test_a_second_switch_to_the_grain_just_chosen_changes_nothing(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _ = await rehearsed_in_parts(db_session, 0)
    whole = _kept(await upload_a_part(client, session.id, part=None, audio=b"inteira"))
    first = _rehearsals(await _switched(client, session.id, "scene"))[whole]["set_aside_at"]
    for part in (1, 2):
        _kept(await upload_a_part(client, session.id, part=part, audio=f"cena {part}".encode()))
    stamps_before = {
        take_id: take["set_aside_at"]
        for take_id, take in _rehearsals(await _listing(client, session.id)).items()
    }

    again = await _switched(client, session.id, "scene")

    assert again["grain"] == "scene"
    assert {
        take_id: take["set_aside_at"] for take_id, take in _rehearsals(again).items()
    } == stamps_before
    assert stamps_before[whole] == first


async def test_a_switch_over_an_approved_draft_without_the_armed_tap_is_refused_and_nothing_changes(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _ = await _recorded_parts(client, db_session)
    await checked_heard_and_approved(client, db_session, session.id)
    listing_before = await _listing(client, session.id)
    stored_before = await stored_telling_back(db_session, session)

    refused = await _switch(client, session.id, "whole")

    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "DRAFT_APPROVED"
    assert (await _approval(client, session.id) or {}).get("version") == 1
    listing = await _listing(client, session.id)
    assert listing == listing_before
    assert [take["set_aside_at"] for take in _rehearsals(listing).values()] == [None, None]
    stored = await stored_telling_back(db_session, session)
    assert stored.checked is True
    assert stored.checks == stored_before.checks


async def test_with_the_armed_tap_the_switch_is_recorded_and_the_draft_reopens(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _ = await _recorded_parts(client, db_session)
    await checked_heard_and_approved(client, db_session, session.id)

    switched = await _switch(client, session.id, "whole", reopens_the_approved_draft=True)

    assert switched.status_code == 200, switched.text
    assert switched.json()["grain"] == "whole"
    assert all(take["set_aside_at"] for take in _rehearsals(switched.json()).values())
    assert await _approval(client, session.id) is None


async def test_a_switch_leaves_the_passage_with_no_checks_and_the_old_rounds_are_kept(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, parts = await _recorded_parts(client, db_session)
    checked = await press_terminei(
        client, session.id, report=played_every_part(parts, duration_ms=PART_MS)
    )
    assert checked.json()["checked"] is True, checked.text
    rounds = (await stored_telling_back(db_session, session)).checks
    assert rounds

    await _switched(client, session.id, "whole")

    stored = await stored_telling_back(db_session, session)
    assert stored.checks == []
    assert stored.checked is False
    assert stored.findings == []
    assert [one.at for one in stored.superseded[-1].checks] == [one.at for one in rounds]
    retired = (
        await db_session.scalars(
            select(IRSegment.superseded_at).where(IRSegment.session_id == session.id)
        )
    ).all()
    assert len(retired) == 2, "a troca apagou as frases contadas"
    assert None not in retired


async def test_after_a_switch_the_automatic_check_runs_again(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _ = await rehearsed_in_parts(db_session, 0)
    whole = _kept(await upload_a_part(client, session.id, part=None, audio=b"inteira"))
    await _told_over(db_session, session, whole, "a passagem contada de volta")
    checked = await press_terminei(
        client, session.id, report=played_every_part([whole], duration_ms=PART_MS)
    )
    assert checked.json()["checked"] is True, checked.text

    await _switched(client, session.id, "scene")
    parts = await _joined_parts(client, db_session, session)
    for number, part in enumerate(parts, start=1):
        await _told_over(db_session, session, part, f"a cena {number} contada de volta")

    listened = await client.post(
        f"{PREFIX}/sessions/{session.id}/back-translation/listened-whole",
        headers=HEADERS,
        json=played_every_part(parts, duration_ms=PART_MS),
    )

    assert listened.status_code == 200, listened.text
    assert listened.json()["automatic_check"] is True, (
        "a conferência automática não voltou depois da troca"
    )


async def test_the_whole_recorded_after_a_switch_is_told_back_and_checked_over_its_own_frases_only(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: Analyst
) -> None:
    session, parts, whole, _, _ = await _switched_to_the_whole_over_joined_parts(client, db_session)
    stretch = await _told_over(db_session, session, whole, "a passagem contada de volta")

    checked = await press_terminei(
        client, session.id, report=played_every_part([whole], duration_ms=PART_MS)
    )

    assert checked.status_code == 200, checked.text
    assert checked.json()["refusal"] is None, checked.text
    assert analyst.readings == 1
    assert (await stored_telling_back(db_session, session)).analysed_segment_ids == [stretch.id]

    refused = await client.post(
        f"{PREFIX}/sessions/{session.id}/back-translation/chunks",
        headers=HEADERS,
        data={"take_id": parts[0], "starts_ms": "0", "ends_ms": "2000"},
        files={"file": ("trecho.m4a", b"a cena contada", "audio/mp4")},
    )

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "STRETCH_NO_LONGER_COUNTS"


async def test_the_packet_of_a_passage_switched_to_the_whole_names_one_take_the_whole(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _, whole, _, _ = await _switched_to_the_whole_over_joined_parts(client, db_session)
    await _told_over(db_session, session, whole, "a passagem contada de volta")
    await checked_heard_and_approved(client, db_session, session.id)

    packet = await release_packet(db_session, session)

    (only,) = packet["audio"]["rehearsal_takes"]
    assert only["key"] == "whole"
    assert only["sha256"] != ""
    assert packet["audio"]["recording_grain"] == "whole"


async def test_a_take_of_the_earlier_grain_that_lands_after_the_switch_is_set_aside_at_once(
    client: httpx.AsyncClient, db_session: AsyncSession, desk: dict[str, str]
) -> None:
    session, parts, _, before, after = await _switched_to_the_whole_over_joined_parts(
        client, db_session
    )
    instant = _one_instant(
        [
            take["set_aside_at"]
            for take_id, take in _rehearsals(await _listing(client, session.id)).items()
            if take_id in parts
        ],
        before,
        after,
    )

    late = await upload_a_part(client, session.id, part=3, audio=b"a cena 3 gravada antes")

    assert late.status_code == 200, late.text
    assert late.json()["set_aside_at"] is not None, "a cena atrasada voltou a ser parte"
    assert _moment(late.json()["set_aside_at"]) == instant
    downloads = await _downloads(client, desk, session.id)
    assert [take["key"] for take in downloads["takes"]] == ["whole"]


async def test_the_retroverification_file_lists_the_set_aside_takes_flagged_with_the_switchs_time(
    client: httpx.AsyncClient, db_session: AsyncSession, desk: dict[str, str]
) -> None:
    session, parts, whole, before, after = await _switched_to_the_whole_over_joined_parts(
        client, db_session
    )

    retro = await client.get(desk_retro(session.id), headers=desk)

    assert retro.status_code == 200, retro.text
    rehearsals = {
        take["take_id"]: take for take in retro.json()["takes"] if take["kind"] == "ensaio"
    }
    assert set(rehearsals) == {*parts, whole}
    _one_instant([rehearsals[part]["set_aside_at"] for part in parts], before, after)
    assert rehearsals[whole]["set_aside_at"] is None


async def test_the_desks_takes_listing_names_the_grain_and_flags_the_set_aside_takes(
    client: httpx.AsyncClient, db_session: AsyncSession, desk: dict[str, str]
) -> None:
    session, parts, whole, before, after = await _switched_to_the_whole_over_joined_parts(
        client, db_session
    )

    read = await client.get(f"{PREFIX}/facilitator/sessions/{session.id}/takes", headers=desk)

    assert read.status_code == 200, read.text
    assert read.json()["grain"] == "whole"
    rehearsals = _rehearsals(read.json())
    _one_instant([rehearsals[part]["set_aside_at"] for part in parts], before, after)
    assert rehearsals[whole]["set_aside_at"] is None


async def test_the_retroverification_file_of_a_session_never_switched_flags_no_take(
    client: httpx.AsyncClient, db_session: AsyncSession, desk: dict[str, str]
) -> None:
    session = await ready_session(db_session)

    retro = await client.get(desk_retro(session.id), headers=desk)

    assert retro.status_code == 200, retro.text
    assert retro.json()["takes"]
    assert [take["set_aside_at"] for take in retro.json()["takes"]] == [None] * len(
        retro.json()["takes"]
    )


async def test_a_switch_from_a_tablet_of_another_team_is_refused_before_anything_changes(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _ = await _recorded_parts(client, db_session)
    _stranger, credential = await a_claimed_device(db_session, email="estranho@example.com")

    refused = await _switch(client, session.id, "whole", headers=team_headers(credential))

    assert refused.status_code == 404, refused.text
    assert [
        take["set_aside_at"] for take in _rehearsals(await _listing(client, session.id)).values()
    ] == [
        None,
        None,
    ]


async def test_an_unknown_grain_is_refused_before_anything_changes(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _ = await _recorded_parts(client, db_session)

    refused = await _switch(client, session.id, "cenas")

    assert refused.status_code == 422, refused.text
    assert [
        take["set_aside_at"] for take in _rehearsals(await _listing(client, session.id)).values()
    ] == [
        None,
        None,
    ]


async def test_a_switch_back_never_restores_the_earlier_takes(
    client: httpx.AsyncClient, db_session: AsyncSession, desk: dict[str, str]
) -> None:
    session, _ = await rehearsed_in_parts(db_session, 0)
    first_whole = _kept(
        await upload_a_part(client, session.id, part=None, audio=b"a primeira inteira")
    )
    t1 = _rehearsals(await _switched(client, session.id, "scene"))[first_whole]["set_aside_at"]
    parts = [
        _kept(await upload_a_part(client, session.id, part=part, audio=f"cena {part}".encode()))
        for part in (1, 2)
    ]
    back = _rehearsals(await _switched(client, session.id, "whole"))
    second_whole = _kept(
        await upload_a_part(client, session.id, part=None, audio=b"a segunda inteira")
    )

    downloads = await _downloads(client, desk, session.id)

    assert [(take["key"], take["take_id"]) for take in downloads["takes"]] == [
        ("whole", second_whole)
    ]
    listing = _rehearsals(await _listing(client, session.id))
    assert listing[first_whole]["set_aside_at"] == t1, "a volta mexeu na marca da primeira troca"
    replaced = {take["take_id"]: take for take in downloads["superseded_takes"]}[first_whole]
    assert _moment(replaced["superseded_at"]) == _moment(listing[second_whole]["recorded_at"]), (
        "a hora em que a inteira foi substituída virou a hora da troca"
    )
    assert replaced["set_aside_at"] == t1
    t2 = {listing[part]["set_aside_at"] for part in parts}
    assert t2 == {back[parts[0]]["set_aside_at"]}
    assert t1 is not None and None not in t2 and t2 != {t1}


async def test_a_session_never_switched_reads_its_grain_off_its_parts_and_flags_no_take(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _ = await rehearsed_in_parts(db_session, 0)
    _kept(await upload_a_part(client, session.id, part=None, audio=b"inteira"))
    for part in (1, 2):
        _kept(await upload_a_part(client, session.id, part=part, audio=f"cena {part}".encode()))

    listing = await _listing(client, session.id)

    assert listing["grain"] == "scene"
    assert [take["set_aside_at"] for take in _rehearsals(listing).values()] == [None, None, None]


async def test_a_switch_over_a_passage_with_nothing_told_starts_no_attempt_over(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _ = await rehearsed_in_parts(db_session, 0)
    _kept(await upload_a_part(client, session.id, part=None, audio=b"inteira"))

    await _switched(client, session.id, "scene")

    assert (await stored_telling_back(db_session, session)).superseded == [], (
        "a troca mostrava ao consultor uma tentativa que ninguém fez"
    )


async def test_a_whole_that_stepped_aside_for_scene_parts_does_not_come_back_with_a_switch_to_the_whole(  # noqa: E501
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _ = await rehearsed_in_parts(db_session, 0)
    old_whole = _kept(await upload_a_part(client, session.id, part=None, audio=b"a antiga"))
    for part in (1, 2):
        _kept(await upload_a_part(client, session.id, part=part, audio=f"cena {part}".encode()))

    switched = await _switched(client, session.id, "whole")

    assert switched["grain"] == "whole"
    assert _rehearsals(switched)[old_whole]["set_aside_at"] is not None, (
        "a inteira gravada antes da troca voltou a ser a parte"
    )
    assert all(take["set_aside_at"] for take in _rehearsals(switched).values())


async def test_a_switch_over_frases_told_but_never_checked_starts_the_telling_over(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _ = await _recorded_parts(client, db_session)

    await _switched(client, session.id, "whole")

    assert len((await stored_telling_back(db_session, session)).superseded) == 1, (
        "as frases contadas antes da troca não foram guardadas numa tentativa"
    )
    retired = (
        await db_session.scalars(
            select(IRSegment.superseded_at).where(IRSegment.session_id == session.id)
        )
    ).all()
    assert len(retired) == 2
    assert None not in retired


async def test_a_late_joined_scene_over_a_draft_approved_after_the_switch_is_set_aside_never_refused(  # noqa: E501
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _ = await rehearsed_in_parts(db_session, 0)
    for number, part in enumerate(await _joined_parts(client, db_session, session), start=1):
        await _told_over(db_session, session, part, f"a cena {number} contada de volta")
    assert await checked_heard_and_approved(client, db_session, session.id) == 1
    switched = await _switch(client, session.id, "whole", reopens_the_approved_draft=True)
    assert switched.status_code == 200, switched.text
    whole = _kept(await upload_a_part(client, session.id, part=None, audio=b"a passagem inteira"))
    await _told_over(db_session, session, whole, "a passagem contada de volta")
    assert await checked_heard_and_approved(client, db_session, session.id) == 2
    rehearsal = await a_scene_rehearsal(db_session, session, 3)

    late = await _joined_upload(client, session.id, part=3, origin=rehearsal.id)

    assert late.status_code == 200, late.text
    assert late.json()["set_aside_at"] is not None
    assert (await _approval(client, session.id) or {}).get("version") == 2, (
        "a cena atrasada reabriu o rascunho aprovado depois da troca"
    )


async def test_an_approval_that_lands_while_the_switch_takes_the_session_row_refuses_the_switch(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    test_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, _ = await _recorded_parts(client, db_session)
    told = await final_segments(db_session, session.id)
    await reported_playback(
        db_session,
        session,
        BackTranslationState(
            scope=session.pericope,
            findings=[],
            checked=True,
            analysed_segment_ids=[one.id for one in told],
        ),
    )
    elsewhere = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    holding = sessions_service.hold_the_session_row

    async def the_approval_lands_then_the_row_is_taken(db: AsyncSession, held: IRSession) -> None:
        async with elsewhere() as other:
            await approve_release(other, await get_session(other, session.id))
        await holding(db, held)

    monkeypatch.setattr(
        sessions_service, "hold_the_session_row", the_approval_lands_then_the_row_is_taken
    )

    refused = await _switch(client, session.id, "whole")

    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "DRAFT_APPROVED"
    monkeypatch.undo()
    assert (await _approval(client, session.id) or {}).get("version") == 1, (
        "a troca reabriu sem o toque armado a versão aprovada enquanto esperava a linha"
    )
    assert [
        take["set_aside_at"] for take in _rehearsals(await _listing(client, session.id)).values()
    ] == [
        None,
        None,
    ]


async def test_scenes_joined_again_after_a_switch_back_are_new_takes_that_stand(
    client: httpx.AsyncClient, db_session: AsyncSession, desk: dict[str, str]
) -> None:
    session, _ = await rehearsed_in_parts(db_session, 0)
    rehearsals = [await a_scene_rehearsal(db_session, session, part) for part in (1, 2, 3)]
    first = [
        _kept(await _joined_upload(client, session.id, part=part, origin=rehearsal.id))
        for part, rehearsal in enumerate(rehearsals, start=1)
    ]
    await _switched(client, session.id, "whole")
    resent = await _joined_upload(client, session.id, part=1, origin=rehearsals[0].id)
    assert _kept(resent) == first[0], "o reenvio de uma cena deixada de lado virou outra tomada"
    stamps = {
        take_id: take["set_aside_at"]
        for take_id, take in _rehearsals(await _listing(client, session.id)).items()
    }
    await _switched(client, session.id, "scene")

    again = [
        await _joined_upload(client, session.id, part=part, origin=rehearsal.id)
        for part, rehearsal in enumerate(rehearsals, start=1)
    ]

    for answered in again:
        assert answered.status_code == 200, answered.text
        assert answered.json()["take_id"] not in first, (
            "juntar de novo depois da volta respondeu com a tomada deixada de lado"
        )
        assert answered.json()["set_aside_at"] is None
    downloads = await _downloads(client, desk, session.id)
    assert [(take["key"], take["take_id"]) for take in downloads["takes"]] == [
        (f"S{part}", answered.json()["take_id"]) for part, answered in enumerate(again, start=1)
    ]
    listing = _rehearsals(await _listing(client, session.id))
    assert {take_id: listing[take_id]["set_aside_at"] for take_id in first} == {
        take_id: stamps[take_id] for take_id in first
    }
