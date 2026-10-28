"""ENG-1801 — the passage's retroverificação file is one, in her fields, under its release's name.

What the route answers is the record of the passage's draft: the team's latest session in the live
draft or in the archive named, under the name of the release it stands on (ADR 0081), and the
room's note on whether that draft is approved. Served only to a reader of that team: a stranger is
told the team does not exist.

Every case reads the route's JSON and the rows the room wrote, through its own write paths.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRRelease, IRSession, IRTake
from app.services.internalization_room.back_translation import (
    BackTranslationState,
)
from app.services.internalization_room.segments import (
    capture_segment,
    final_segments,
)
from tests.baker import make_app, make_role
from tests.release_harness import (
    APP_KEY,
    CLIP_MS,
    PREFIX,
    P,
    a_claimed_device,
    at_the_desk,
    desk_retro,
    ready_session,
    releases_of,
    retro_take,
    team_headers,
    team_release,
    the_one_part_of,
)
from tests.room_harness import (
    record_the_part_again,
    room_client,
    the_bucket_is_in_memory,
    the_room_speaks,
    the_transcriber_says,
)

#: One rehearsal told back in two stretches, so an approval can freeze two numbers and a third
#: stretch told afterwards can have none.
TWO_STRETCHES = (
    ("Noemi ouviu que o Senhor tinha visitado o seu povo", 0, 30000),
    ("ela saiu do lugar onde estava com as duas noras", 30000, CLIP_MS),
)


FIRST_TELLING = "Noemi voltou para Juda"


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    """The room's routes, with the transcriber, the bucket and the Speaker stood in for.

    The cases that tell a stretch again do it through the tablet's own route, which stores
    audio and speaks back; the cases that write rows directly need none of it and are not
    harmed by it.

    `listen_url` is stood in for because a signed address needs a bucket this suite has none
    of. What the case following a link is about is that the path the file served reaches the
    route and the route redirects — never what storage puts on the other side of it.
    """
    from app.api.internalization_room import takes as take_routes

    async def _signed(take, **_: object) -> str:
        return f"https://bucket.example/{take.storage_key}"

    monkeypatch.setattr(take_routes, "listen_url", _signed)
    said: list[str] = []
    the_transcriber_says(monkeypatch, said)
    the_bucket_is_in_memory(monkeypatch)
    the_room_speaks(monkeypatch)
    async with room_client(db_session, monkeypatch) as room:
        room.said = said  # type: ignore[attr-defined]
        yield room


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


async def _a_retro_take(db: AsyncSession, session: IRSession, name: str) -> IRTake:
    """One recording of the team explaining a stretch, as a row of its own.

    A row rather than a bare id, because the file lists a link per take and a name nothing
    wrote would prove nothing about which recordings are reachable.
    """
    take = retro_take(session.id, sha256=sha256(name.encode()).hexdigest())
    db.add(take)
    await db.commit()
    return take


async def _read(db: AsyncSession, session: IRSession) -> BackTranslationState:
    """The state one whole clean reading of every stretch that counts leaves behind."""
    told = await final_segments(db, session.id)
    return BackTranslationState(
        scope=P, checked=True, analysed_segment_ids=[stretch.id for stretch in told]
    )


async def _told_once(db: AsyncSession, session: IRSession) -> BackTranslationState:
    """One stretch, explained on a retro take the file can point at."""
    part = await the_one_part_of(db, session)
    retro = await _a_retro_take(db, session, "primeira")
    await capture_segment(
        db,
        session,
        take_id=part.id,
        starts_ms=0,
        ends_ms=CLIP_MS,
        bridge_take_id=retro.id,
        transcript=FIRST_TELLING,
    )
    return await _read(db, session)


async def _told_in_two_stretches(db: AsyncSession, session: IRSession) -> BackTranslationState:
    part = await the_one_part_of(db, session)
    for text, starts_ms, ends_ms in TWO_STRETCHES:
        retro = await _a_retro_take(db, session, f"retro-{starts_ms}")
        await capture_segment(
            db,
            session,
            take_id=part.id,
            starts_ms=starts_ms,
            ends_ms=ends_ms,
            bridge_take_id=retro.id,
            transcript=text,
        )
    return await _read(db, session)


async def _approved_by_the_team(
    client: httpx.AsyncClient, session_id: str, credential: str
) -> None:
    approved = await client.post(team_release(session_id), headers=team_headers(credential))
    assert approved.status_code == 200, approved.text


NOT_APPROVED_YET = (
    "rascunho ainda não aprovado — as frases abaixo são a tradução ao vivo, não uma versão fechada"
)
APPROVED_BEFORE_THE_RECORD = (
    "esta versão foi aprovada antes do registro de aprovação existir — "
    "sem estado de conferência gravado; as frases abaixo são a tradução ao vivo"
)


def _passage_file(project_id: str, archive: str | None = None) -> str:
    url = f"{PREFIX}/facilitator/projects/{project_id}/passages/{P}/retroverificacao"
    return f"{url}?archive={archive}" if archive else url


async def test_a_passage_worked_over_two_sessions_is_the_file_of_the_latest_named_after_its_release(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    project, credential = await a_claimed_device(db_session)
    first = await ready_session(db_session, project_id=project.id, tell=_told_once)
    await _approved_by_the_team(client, first.id, credential)
    second = await ready_session(db_session, project_id=project.id, tell=_told_in_two_stretches)
    await _approved_by_the_team(client, second.id, credential)
    second.created_at = second.updated_at = first.created_at + timedelta(minutes=1)
    await db_session.commit()
    desk, _facilitator = await at_the_desk(db_session, room_app, project)
    (row,) = await releases_of(db_session, second.id)
    name = row.packet["release_id"]

    answered = await client.get(_passage_file(project.id), headers=desk)

    assert answered.status_code == 200, answered.text
    assert name.endswith("-v2")
    assert answered.headers["content-disposition"] == (
        f'attachment; filename="{name}-retroverificacao.json"'
    )
    file = answered.json()
    assert file["releaseId"] == name
    assert file["version"] == 2
    assert len(file["frases"]) == 2


async def test_a_passage_not_yet_approved_carries_the_first_note_and_the_live_frases(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    project, _credential = await a_claimed_device(db_session)
    await ready_session(db_session, project_id=project.id, tell=_told_in_two_stretches)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    answered = await client.get(_passage_file(project.id), headers=desk)

    file = answered.json()
    assert file["releaseId"].endswith("-v1")
    assert file["note"] == NOT_APPROVED_YET
    assert [one["n"] for one in file["frases"]] == [1, 2]


async def test_a_version_approved_before_approvals_were_recorded_carries_the_second_note(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    project, credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id, tell=_told_once)
    await _approved_by_the_team(client, session.id, credential)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)
    (row,) = await releases_of(db_session, session.id)
    row.packet = {key: value for key, value in row.packet.items() if key != "check"}
    await db_session.commit()

    file = (await client.get(_passage_file(project.id), headers=desk)).json()

    assert file["note"] == APPROVED_BEFORE_THE_RECORD
    assert file["releaseId"].endswith("-v1")


async def test_a_translation_that_cannot_be_read_answers_try_again_and_no_file(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    project, _credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id, tell=_told_once)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)
    session.back_translation = {"checks": "not a list"}
    await db_session.commit()

    answered = await client.get(_passage_file(project.id), headers=desk)

    assert answered.status_code == 503, answered.text
    assert "frases" not in answered.json()


async def test_the_passage_file_serves_the_live_sessions_unless_an_archive_is_named(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    project, _credential = await a_claimed_device(db_session)
    await ready_session(db_session, project_id=project.id, tell=_told_once)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)
    zerar = await client.post(
        f"{PREFIX}/facilitator/projects/{project.id}/passages/{P}/archive", headers=desk
    )
    await ready_session(db_session, project_id=project.id, tell=_told_in_two_stretches)

    in_force = (await client.get(_passage_file(project.id), headers=desk)).json()
    kept = (
        await client.get(_passage_file(project.id, zerar.json()["archive"]["id"]), headers=desk)
    ).json()

    assert [len(one["frases"]) for one in (in_force, kept)] == [2, 1]
    assert (
        await client.get(f"{_passage_file(project.id)}?archive=", headers=desk)
    ).status_code == 422


async def _zerada(client: httpx.AsyncClient, desk: dict[str, str], project_id: str) -> dict:
    zerar = await client.post(
        f"{PREFIX}/facilitator/projects/{project_id}/passages/{P}/archive", headers=desk
    )
    return zerar.json()["archive"]


async def test_an_archive_that_holds_a_release_is_read_as_that_release(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    project, credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id, tell=_told_once)
    await _approved_by_the_team(client, session.id, credential)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)
    (row,) = await releases_of(db_session, session.id)
    archive = await _zerada(client, desk, project.id)

    file = (await client.get(_passage_file(project.id, archive["id"]), headers=desk)).json()

    assert file["releaseId"] == row.packet["release_id"]
    assert "note" not in file


async def test_an_archive_whose_release_predates_the_approval_record_carries_the_second_note(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    project, credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id, tell=_told_once)
    await _approved_by_the_team(client, session.id, credential)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)
    (row,) = await releases_of(db_session, session.id)
    row.packet = {key: value for key, value in row.packet.items() if key != "check"}
    await db_session.commit()
    archive = await _zerada(client, desk, project.id)

    file = (await client.get(_passage_file(project.id, archive["id"]), headers=desk)).json()

    assert file["note"] == APPROVED_BEFORE_THE_RECORD


async def test_an_archive_whose_takes_were_recorded_again_after_the_approval_is_not_that_release(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    project, credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id, tell=_told_once)
    await _approved_by_the_team(client, session.id, credential)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)
    await record_the_part_again(
        db_session, session, await the_one_part_of(db_session, session), sha256="b" * 64
    )
    archive = await _zerada(client, desk, project.id)

    file = (await client.get(_passage_file(project.id, archive["id"]), headers=desk)).json()

    assert "-zerada-" in file["releaseId"]
    assert not file["releaseId"].endswith("-v1")
    assert file["note"] == NOT_APPROVED_YET


async def test_a_session_stamped_with_an_archive_that_is_gone_is_not_found(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    project, _credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id, tell=_told_once)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)
    session.archive_id = "gone"
    await db_session.commit()

    answered = await client.get(_passage_file(project.id, "gone"), headers=desk)

    assert answered.status_code == 404, answered.text


async def test_an_archive_keeps_its_release_when_the_live_draft_is_approved_after(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    project, credential = await a_claimed_device(db_session)
    archived = await ready_session(db_session, project_id=project.id, tell=_told_once)
    await _approved_by_the_team(client, archived.id, credential)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)
    (row,) = await releases_of(db_session, archived.id)
    archive = await _zerada(client, desk, project.id)
    live = await ready_session(db_session, project_id=project.id, tell=_told_once)
    await _approved_by_the_team(client, live.id, credential)

    file = (await client.get(_passage_file(project.id, archive["id"]), headers=desk)).json()

    assert row.packet["release_id"].endswith("-v1")
    assert file["releaseId"] == row.packet["release_id"]


async def test_an_archive_reads_the_latest_release_its_session_wrote(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    project, credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id, tell=_told_once)
    await _approved_by_the_team(client, session.id, credential)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)
    (first,) = await releases_of(db_session, session.id)
    later = first.packet["release_id"].replace("-v1", "-v2")
    db_session.add(
        IRRelease(
            session_id=session.id,
            project_id=project.id,
            pericope=first.pericope,
            version=2,
            package_sha256=first.package_sha256,
            packet={**first.packet, "release_id": later, "version": 2},
            approved_at=first.approved_at,
        )
    )
    await db_session.commit()
    archive = await _zerada(client, desk, project.id)

    file = (await client.get(_passage_file(project.id, archive["id"]), headers=desk)).json()

    assert file["releaseId"] == later


async def test_an_archive_that_holds_no_release_is_named_with_its_stamp(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    project, _credential = await a_claimed_device(db_session, language_name="Terena")
    await ready_session(db_session, project_id=project.id, tell=_told_once)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)
    archive = await _zerada(client, desk, project.id)
    stamp = datetime.fromisoformat(archive["archived_at"]).astimezone(UTC).strftime("%Y%m%d-%H%M")

    answered = await client.get(_passage_file(project.id, archive["id"]), headers=desk)

    file = answered.json()
    assert file["releaseId"].endswith(f"-{P.lower()}-zerada-{stamp}")
    assert file["releaseId"].startswith("internalize-terena-")
    assert answered.headers["content-disposition"] == (
        f'attachment; filename="{file["releaseId"]}-retroverificacao.json"'
    )
    assert file["note"] == NOT_APPROVED_YET


async def test_the_old_session_route_redirects_to_the_file_of_its_passage(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    project, _credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id, tell=_told_once)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    live = await client.get(desk_retro(session.id), headers=desk)
    zerar = await client.post(
        f"{PREFIX}/facilitator/projects/{project.id}/passages/{P}/archive", headers=desk
    )
    archived = await client.get(desk_retro(session.id), headers=desk)

    assert (live.status_code, live.headers["location"]) == (307, _passage_file(project.id))
    assert archived.status_code == 307
    assert archived.headers["location"] == _passage_file(project.id, zerar.json()["archive"]["id"])
