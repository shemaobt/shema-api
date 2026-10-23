"""ENG-1753 — the canon-pins read names every pin a live session holds, across every team.

Its answer, saved to a file, is what the prune is told to keep. A pin it left out is a canon
the prune removes while a session still reads it, so the read is not scoped to the reader's
teams and leaves out only the sessions a Zerar archived.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import ProjectRole
from app.db.models.project import Project
from app.services.auth.issue_tokens import issue_tokens
from app.services.internalization_room.canon import kept
from app.services.internalization_room.sessions import create_session
from tests.baker import (
    grant_room_app_role,
    make_language,
    make_project,
    make_project_user_access,
    make_user,
)
from tests.canon_harness import the_canon_moves_on
from tests.release_harness import PREFIX, desk_release, ready_session
from tests.room_harness import room_client

CANON_PINS = f"{PREFIX}/facilitator/canon-pins"
NEW_PIN = "a" * 40


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as door:
        yield door


async def _a_team(db: AsyncSession, tag: str) -> Project:
    language = await make_language(db, name=f"Lang {tag}", code=f"l{tag}")
    return await make_project(db, language.id, name=f"Team {tag}")


async def _a_reader(
    db: AsyncSession, email: str, *, role: str, facilitates: tuple[Project, ...] = ()
) -> dict[str, str]:
    user = await make_user(db, email=email)
    await grant_room_app_role(db, user.id, role)
    for team in facilitates:
        await make_project_user_access(db, team.id, user.id, role=ProjectRole.FACILITATOR)
    access, _refresh = await issue_tokens(db, user)
    return {"Authorization": f"Bearer {access}"}


async def _a_session(db: AsyncSession, team: Project, pericope: str) -> None:
    await create_session(db, pericope=pericope, project_id=team.id)
    await db.commit()


async def _pins(client: httpx.AsyncClient, reader: dict[str, str]) -> dict:
    read = await client.get(CANON_PINS, headers=reader)
    assert read.status_code == 200, read.text[:300]
    return read.json()


async def test_the_read_names_each_pin_a_live_session_holds_once(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    team = await _a_team(db_session, "x")
    reader = await _a_reader(db_session, "x@example.com", role="facilitator", facilitates=(team,))
    deployed = kept.deployed_pin()
    await _a_session(db_session, team, "P01")
    the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN)
    await _a_session(db_session, team, "P02")
    await _a_session(db_session, team, "P03")

    assert (await _pins(client, reader))["pins"] == sorted([deployed, NEW_PIN]), (
        "a leitura repetia um pin ou deixava de fora o de uma sessão viva"
    )


async def test_an_archived_sessions_pin_is_not_named(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    team = await _a_team(db_session, "x")
    reader = await _a_reader(db_session, "x@example.com", role="facilitator", facilitates=(team,))
    await _a_session(db_session, team, "P01")
    the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN)
    await _a_session(db_session, team, "P02")
    zerar = await client.post(
        f"{PREFIX}/facilitator/projects/{team.id}/passages/P01/archive", headers=reader
    )
    assert zerar.status_code == 200, zerar.text[:300]

    assert (await _pins(client, reader))["pins"] == [NEW_PIN], (
        "a leitura guardava o canon de uma sessão que o Zerar arquivou"
    )


async def test_an_approved_drafts_session_is_still_named(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    team = await _a_team(db_session, "x")
    reader = await _a_reader(db_session, "x@example.com", role="facilitator", facilitates=(team,))
    the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN)
    session = await ready_session(db_session, project_id=team.id)
    approved = await client.post(desk_release(session.id), headers=reader, json={"force": True})
    assert approved.status_code == 200, approved.text[:300]

    assert (await _pins(client, reader))["pins"] == [NEW_PIN], (
        "a leitura deixava de fora o pin de um rascunho aprovado, que segue vivo"
    )


async def test_the_read_names_the_pins_of_a_team_the_reader_does_not_facilitate(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    team_a = await _a_team(db_session, "a")
    team_b = await _a_team(db_session, "b")
    reader = await _a_reader(db_session, "a@example.com", role="facilitator", facilitates=(team_a,))
    the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN)
    await _a_session(db_session, team_b, "P01")

    assert NEW_PIN in (await _pins(client, reader))["pins"], (
        "a leitura de um facilitador deixava de fora os pins de outra equipe, e o prune os apagava"
    )


async def test_a_consultant_with_no_team_reads_the_same_answer_as_a_facilitator(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    team_a = await _a_team(db_session, "a")
    team_b = await _a_team(db_session, "b")
    facilitator = await _a_reader(
        db_session, "a@example.com", role="facilitator", facilitates=(team_a,)
    )
    consultant = await _a_reader(db_session, "con@example.com", role="consultant")
    deployed = kept.deployed_pin()
    await _a_session(db_session, team_a, "P01")
    the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN)
    await _a_session(db_session, team_b, "P01")
    every_pin = sorted([deployed, NEW_PIN])

    assert (await _pins(client, facilitator))["pins"] == every_pin
    assert (await _pins(client, consultant))["pins"] == every_pin


async def test_with_no_live_session_the_read_answers_an_empty_list(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    team = await _a_team(db_session, "x")
    reader = await _a_reader(db_session, "x@example.com", role="facilitator", facilitates=(team,))

    assert (await _pins(client, reader))["pins"] == []


async def test_the_read_names_the_environment_that_served_it_and_its_deployed_pin(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    team = await _a_team(db_session, "x")
    reader = await _a_reader(db_session, "x@example.com", role="facilitator", facilitates=(team,))
    monkeypatch.setattr(get_settings(), "cloud_run_service", "tripod-backend")
    the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN)

    answer = await _pins(client, reader)

    assert (answer["environment"], answer["deployed_pin"]) == ("tripod-backend", NEW_PIN), (
        "o arquivo não dizia de que ambiente veio nem que pin ele serve, e o prune não tinha "
        "como recusar um arquivo do staging ou guardar o canon que produção serve"
    )


async def test_the_read_names_the_moment_it_answered(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    team = await _a_team(db_session, "x")
    reader = await _a_reader(db_session, "x@example.com", role="facilitator", facilitates=(team,))
    before = datetime.now(UTC)

    answer = await _pins(client, reader)

    assert before <= datetime.fromisoformat(answer["answered_at"]) <= datetime.now(UTC), (
        "o arquivo não dizia quando foi respondido, e o prune não tinha como recusar um velho"
    )
