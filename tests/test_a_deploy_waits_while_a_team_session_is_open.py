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
    return {"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": os.environ["HOME"]}


def the_annotation(stdout: str, command: str) -> str:
    found = [line for line in stdout.splitlines() if line.startswith(command)]
    assert len(found) == 1, f"{command} is on {len(found)} lines"
    return found[0]


def the_hold_runs(runner: dict[str, str], **settings: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-e", "-c", the_hold()["run"]],
        cwd=ROOT,
        env={**runner, **settings},
        capture_output=True,
        text=True,
        timeout=20,
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


async def test_the_deploy_names_the_team_it_waits_for_and_goes_on_once_their_passage_ends(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    await a_session(db_session, "sessao-da-ruth", updated_at=datetime.now(UTC))
    hold = subprocess.Popen(
        ["bash", "-e", "-c", the_hold()["run"]],
        cwd=ROOT,
        env={**a_runner(tmp_path), "DEPLOY_HOLD_POLL_SECONDS": "0.1"},
        stdout=subprocess.PIPE,
        text=True,
    )
    assert hold.stdout is not None
    said = [hold.stdout.readline() for _ in range(2)]

    session = await db_session.get(IRSession, "sessao-da-ruth")
    assert session is not None
    session.status = IRSessionStatus.DONE
    session.ended_at = datetime.now(UTC)
    await db_session.commit()
    rest, _ = hold.communicate(timeout=60)

    assert said[0] == "Waiting on 1 open team session(s):\n"
    assert said[1].split()[:3] == ["sessao-da-ruth", "project", "time-de-ruth"]
    assert hold.returncode == 0
    assert rest.endswith("No team session is open; the deploy goes on.\n")


async def test_a_wait_that_outlives_its_deadline_fails_naming_who_held_it(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    await a_session(db_session, "sessao-da-ruth", updated_at=datetime.now(UTC))
    await a_session(
        db_session, "sessao-de-noemi", project_id="time-de-noemi", updated_at=datetime.now(UTC)
    )

    hold = the_hold_runs(
        a_runner(tmp_path),
        DEPLOY_HOLD_POLL_SECONDS="0.1",
        DEPLOY_HOLD_DEADLINE_MINUTES="0.005",
    )

    assert hold.returncode == 1
    annotation = the_annotation(hold.stdout, "::error::")
    assert "sessao-da-ruth  project time-de-ruth" in annotation
    assert "sessao-de-noemi  project time-de-noemi" in annotation


def test_the_wait_gives_up_inside_the_six_hours_github_gives_the_job() -> None:
    job = yaml.safe_load(DEPLOY.read_text())["jobs"]["deploy"]

    assert job["timeout-minutes"] == 360
    assert hold_deploy.DEADLINE_MINUTES < 360


async def test_an_urgent_deploy_does_not_wait_and_says_whose_room_it_ships_into(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    await a_session(db_session, "sessao-da-ruth", updated_at=datetime.now(UTC))
    await a_session(
        db_session, "sessao-de-noemi", project_id="time-de-noemi", updated_at=datetime.now(UTC)
    )

    hold = the_hold_runs(
        a_runner(tmp_path),
        DEPLOY_URGENT="true",
        DEPLOY_HOLD_POLL_SECONDS="0.1",
        DEPLOY_HOLD_DEADLINE_MINUTES="0.005",
    )

    assert hold.returncode == 0
    assert "Waiting on" not in hold.stdout
    annotation = the_annotation(hold.stdout, "::warning::")
    assert "sessao-da-ruth  project time-de-ruth" in annotation
    assert "sessao-de-noemi  project time-de-noemi" in annotation


def test_only_a_manual_run_can_be_urgent_and_it_is_not_unless_someone_says_so() -> None:
    triggers = yaml.safe_load(DEPLOY.read_text())[True]
    urgent = triggers["workflow_dispatch"]["inputs"]["urgent"]

    assert (urgent["type"], urgent["default"]) == ("boolean", False)
    assert triggers["push"] == {"branches": ["main"]}
    assert the_hold()["env"]["DEPLOY_URGENT"] == "${{ inputs.urgent }}"


def test_the_hold_reads_the_migrations_secret_from_the_checkout_before_anything_ships() -> None:
    steps = the_steps()
    names = [step["name"] for step in steps]
    hold = steps.index(the_hold())
    secret = "--secret=tripod_backend_neon_database_url --project=shemaobt-secrets"

    assert names.index("Setup Cloud SDK") < names.index("Build and Push Backend") < hold
    assert hold < names.index("Run migrations") < names.index("Deploy Backend")
    assert secret in steps[names.index("Run migrations")]["run"]
    assert secret in the_hold()["run"]
    assert "docker" not in the_hold()["run"]
    assert all("if" not in step and "continue-on-error" not in step for step in steps[hold:])


def test_one_production_deploy_runs_at_a_time_and_the_next_one_is_kept() -> None:
    workflow = yaml.safe_load(DEPLOY.read_text())

    assert workflow["concurrency"] == {"group": "deploy", "cancel-in-progress": False}


async def test_the_window_is_an_hour_unless_the_deploy_is_told_otherwise(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    await a_session(
        db_session, "sessao-da-ruth", updated_at=datetime.now(UTC) - timedelta(minutes=30)
    )
    runner = a_runner(tmp_path)

    an_hour = the_hold_runs(runner, DEPLOY_URGENT="true")
    a_quarter = the_hold_runs(runner, DEPLOY_URGENT="true", DEPLOY_HOLD_MINUTES="15")

    assert "sessao-da-ruth  project time-de-ruth" in an_hour.stdout
    assert a_quarter.stdout == "No team session is open; the deploy goes on.\n"
