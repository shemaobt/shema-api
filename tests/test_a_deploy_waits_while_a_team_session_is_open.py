from __future__ import annotations

import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.database import Base
from app.db.models.internalization_room import IRSession, IRSessionStatus
from scripts import hold_deploy

NOW = datetime(2026, 10, 8, 14, 0, tzinfo=UTC)
HOUR = timedelta(minutes=60)
ROOT = Path(__file__).resolve().parent.parent
DEPLOY = ROOT / ".github" / "workflows" / "deploy.yml"


def the_steps() -> list[dict[str, Any]]:
    return yaml.safe_load(DEPLOY.read_text())["jobs"]["deploy"]["steps"]


def the_hold() -> dict[str, Any]:
    found = [step for step in the_steps() if "scripts/hold_deploy.py" in step.get("run", "")]
    assert len(found) == 1, f"the hold is in {len(found)} steps"
    return found[0]


def a_runner(tmp_path: Path) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gcloud = bin_dir / "gcloud"
    gcloud.write_text(f"#!/bin/sh\necho '{os.environ['DATABASE_URL']}'\n")
    uv = bin_dir / "uv"
    uv.write_text(f'#!/bin/sh\nshift 2\nexec {sys.executable} "$@"\n')
    gcloud.chmod(0o755)
    uv.chmod(0o755)
    return {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}


def the_hold_runs(runner: dict[str, str], **settings: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-e", "-c", the_hold()["run"]],
        cwd=ROOT,
        env={**runner, **settings},
        capture_output=True,
        text=True,
        timeout=60,
    )


async def a_session(db: AsyncSession, session_id: str, **columns: Any) -> None:
    db.add(
        IRSession(
            **{
                "id": session_id,
                "pericope": "P03",
                "project_id": "time-de-ruth",
                "messages": [{"role": "user", "content": "Noemi voltou para Belém."}],
                "updated_at": NOW - timedelta(minutes=5),
                **columns,
            }
        )
    )
    await db.commit()


async def test_a_team_in_the_middle_of_a_passage_holds_the_deploy(
    db_session: AsyncSession,
) -> None:
    await a_session(db_session, "sessao-da-ruth")

    held = await hold_deploy.holding(db_session, NOW, HOUR)

    assert [session.id for session in held] == ["sessao-da-ruth"]


async def test_a_session_opened_with_no_team_never_holds_the_deploy(
    db_session: AsyncSession,
) -> None:
    await a_session(db_session, "sessao-da-chave-da-sala", project_id=None)

    assert await hold_deploy.holding(db_session, NOW, HOUR) == []


async def test_a_passage_the_team_finished_a_minute_ago_does_not_hold_the_deploy(
    db_session: AsyncSession,
) -> None:
    await a_session(
        db_session,
        "sessao-terminada",
        status=IRSessionStatus.DONE,
        ended_at=NOW - timedelta(minutes=1),
        updated_at=NOW - timedelta(minutes=1),
    )

    assert await hold_deploy.holding(db_session, NOW, HOUR) == []


async def test_a_session_the_facilitator_zeroed_does_not_hold_the_deploy(
    db_session: AsyncSession,
) -> None:
    await a_session(db_session, "sessao-zerada", archive_id="arquivo-do-zerar")

    assert await hold_deploy.holding(db_session, NOW, HOUR) == []


async def test_a_session_minted_on_a_launch_nobody_entered_does_not_hold_the_deploy(
    db_session: AsyncSession,
) -> None:
    await a_session(db_session, "sessao-de-ninguem", messages=[])

    assert await hold_deploy.holding(db_session, NOW, HOUR) == []


async def test_the_panorama_a_team_heard_does_not_hold_the_deploy(
    db_session: AsyncSession,
) -> None:
    await a_session(db_session, "panorama-de-rute", pericope="OV-Ruth")

    assert await hold_deploy.holding(db_session, NOW, HOUR) == []


async def test_a_session_left_untouched_for_longer_than_the_window_does_not_hold_the_deploy(
    db_session: AsyncSession,
) -> None:
    await a_session(db_session, "sessao-de-ontem", updated_at=NOW - timedelta(minutes=61))

    assert await hold_deploy.holding(db_session, NOW, HOUR) == []


async def test_a_column_the_pending_migration_adds_does_not_break_the_count(
    tmp_path: Path,
) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'antes-da-migracao.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine) as db:
        await a_session(db, "sessao-da-ruth")
    async with engine.begin() as conn:
        await conn.execute(text("ALTER TABLE ir_sessions DROP COLUMN canon_pin"))

    async with AsyncSession(engine) as db:
        held = await hold_deploy.holding(db, NOW, HOUR)
    await engine.dispose()

    assert [session.id for session in held] == ["sessao-da-ruth"]


async def test_with_no_team_in_the_room_the_deploy_goes_on(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    await a_session(db_session, "sessao-da-chave-da-sala", project_id=None)

    hold = the_hold_runs(a_runner(tmp_path))

    assert hold.returncode == 0, hold.stderr
    assert "No team session is open; the deploy goes on." in hold.stdout
