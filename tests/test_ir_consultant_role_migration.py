"""ENG-1213 — the consultant role exists after its migration, and the grant script grants it.

Same constraint as the sibling migration tests: Alembic's full chain does not run on SQLite,
so the schema is built from ``Base.metadata``, stamped at this revision and walked down to the
one before, with the app and its facilitator role written as ``20260812_room04`` leaves them.
The grant script runs as a subprocess against that file, as a person runs it by hand.
"""

import os
import subprocess
import sys

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

import app.db.models  # noqa: F401  (populates Base.metadata with every table)
from app.core.database import Base
from tests.alembic_harness import REPO_ROOT, run_alembic, scalar

pytestmark = pytest.mark.migration

REVISION = "20261011_cons01"
PREVIOUS_REVISION = "20261007_pend01"
APP_KEY = "internalization-room"

ROLE_KEYS_OF = (
    "SELECT r.role_key FROM user_app_roles g JOIN roles r ON r.id = g.role_id"
    " JOIN users u ON u.id = g.user_id WHERE u.email = :email AND g.revoked_at IS NULL"
)


async def _execute(url: str, *statements: tuple[str, dict]) -> None:
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        for sql, params in statements:
            await conn.execute(text(sql), params)
    await engine.dispose()


async def _roles_of(url: str, email: str) -> set[str]:
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        found = {row[0] for row in (await conn.execute(text(ROLE_KEYS_OF), {"email": email}))}
    await engine.dispose()
    return found


async def _a_facilitator(url: str, email: str) -> None:
    await _execute(
        url,
        (
            "INSERT INTO users (id, email, password_hash, is_active, is_platform_admin)"
            " VALUES (:id, :email, 'x', 1, 0)",
            {"id": f"u-{email}", "email": email},
        ),
        (
            "INSERT INTO user_app_roles (id, user_id, app_id, role_id) VALUES (:id, :user,"
            " 'app-room', 'role-facilitator')",
            {"id": f"g-{email}", "user": f"u-{email}"},
        ),
    )


def _grant(url: str, email: str, role: str, *flags: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "scripts/grant_app_role.py", email, APP_KEY, role, *flags],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "DATABASE_URL": url,
            "JWT_SECRET_KEY": "test-secret-for-pytest-only",
            "INNGEST_DEV": "1",
        },
        capture_output=True,
        text=True,
    )


@pytest.fixture()
async def before_the_migration(tmp_path) -> str:
    url = f"sqlite+aiosqlite:///{tmp_path / 'ir_consultant_role_migration.db'}"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    stamped = run_alembic(url, "stamp", REVISION)
    assert stamped.returncode == 0, stamped.stderr
    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr
    await _execute(
        url,
        (
            "INSERT INTO apps (id, app_key, name, platform, is_active)"
            " VALUES ('app-room', :key, 'Internalization Room', 'web', 1)",
            {"key": APP_KEY},
        ),
        (
            "INSERT INTO roles (id, app_id, role_key, label, is_system)"
            " VALUES ('role-facilitator', 'app-room', 'facilitator', 'Facilitador', 1)",
            {},
        ),
    )
    return url


async def test_the_consultant_role_exists_after_the_migration_and_the_grant_script_grants_it(
    before_the_migration,
) -> None:
    url = before_the_migration
    await _a_facilitator(url, "facilitadora@example.com")

    up = run_alembic(url, "upgrade", REVISION)
    granted = _grant(url, "facilitadora@example.com", "consultant", "--add")

    assert up.returncode == 0, up.stderr
    assert granted.returncode == 0, granted.stdout + granted.stderr
    assert await _roles_of(url, "facilitadora@example.com") == {"facilitator", "consultant"}


async def test_without_add_the_grant_script_still_replaces_the_persons_role_on_the_app(
    before_the_migration,
) -> None:
    url = before_the_migration
    await _a_facilitator(url, "trocada@example.com")
    assert run_alembic(url, "upgrade", REVISION).returncode == 0

    granted = _grant(url, "trocada@example.com", "consultant")

    assert granted.returncode == 0, granted.stdout + granted.stderr
    assert await _roles_of(url, "trocada@example.com") == {"consultant"}


async def test_the_consultant_role_migration_walks_back(before_the_migration) -> None:
    url = before_the_migration
    consultant = "SELECT count(*) FROM roles WHERE role_key = 'consultant'"
    assert run_alembic(url, "upgrade", REVISION).returncode == 0
    assert await scalar(url, consultant, {}) == 1

    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)

    assert down.returncode == 0, down.stderr
    assert await scalar(url, consultant, {}) == 0
    assert await scalar(url, "SELECT count(*) FROM roles WHERE role_key = 'facilitator'", {}) == 1
