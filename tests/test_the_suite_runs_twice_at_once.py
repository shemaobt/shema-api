"""Two pytest runs in one worktree do not corrupt each other, and the caller's URL is honoured.

The test database was one fixed file in the working directory, named twice and read from
neither the environment nor the process. So two runs in one worktree shared it: each test drops
every table and creates them again, and a run doing that under another run takes its tables out
from under it. The failures land anywhere and look like the code under test — measured twice
this round, once on each of two agents working the same repository.

The file is per run now, and `DATABASE_URL` decides when the caller sets one. These two cases
are what stops it quietly going back to a fixed name.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

#: The smallest module in the suite whose tests write through `db_session`, which is the
#: fixture that drops and recreates every table. Small so two runs of it stay quick; writing so
#: that a shared file is a collision rather than a coincidence.
MODULE = "tests/test_rag_admin.py"

#: A table `db_session` creates and seeds, so a database that has it is one the suite actually
#: worked in rather than one somebody merely connected to. SQLite makes the file on connect.
SEEDED_TABLE = "apps"

#: Seconds to wait on a child before giving up on it. A run of one small module takes a few;
#: this is long enough that a slow machine is not a failure, and short enough that a child
#: wedged on a locked database fails the case instead of hanging the suite and the CI job.
PATIENCE = 300


def _environment(**overrides: str) -> dict[str, str]:
    """The caller's environment with no `DATABASE_URL`, which is what a bare run has.

    This process has one: its own conftest set it to this run's file. Handing that to a child
    would be handing it this run's database, which is the very thing under test.
    """
    env = {name: value for name, value in os.environ.items() if name != "DATABASE_URL"}
    env.update(overrides)
    return env


def _run_pytest(environments: list[dict[str, str]], logs: list[Path]) -> list[int | None]:
    """Start one pytest per environment, all at once, and wait for every one of them."""
    handles = [log.open("w") for log in logs]
    try:
        runs = [
            subprocess.Popen(
                [sys.executable, "-m", "pytest", MODULE, "-q", "-p", "no:cacheprovider"],
                cwd=REPO_ROOT,
                env=environment,
                stdout=handle,
                stderr=subprocess.STDOUT,
                text=True,
            )
            for environment, handle in zip(environments, handles, strict=True)
        ]
        codes = []
        for run in runs:
            try:
                codes.append(run.wait(timeout=PATIENCE))
            except subprocess.TimeoutExpired:
                run.kill()
                codes.append(None)
        return codes
    finally:
        for handle in handles:
            handle.close()


def _tables(database: Path) -> set[str]:
    with sqlite3.connect(database) as connection:
        return {
            name
            for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }


def test_two_pytest_runs_in_one_directory_do_not_collide(tmp_path: Path) -> None:
    """Both runs answer for themselves, which they cannot do over one file."""
    logs = [tmp_path / "first.log", tmp_path / "second.log"]

    codes = _run_pytest([_environment(), _environment()], logs)
    outputs = [log.read_text() for log in logs]

    assert codes == [0, 0], outputs
    for output in outputs:
        assert "passed" in output, output


def test_the_callers_database_url_is_honoured(tmp_path: Path) -> None:
    """A caller that names a database gets that database, with the suite's own tables in it.

    Anybody reproducing a failure against a file they want to keep names one. A run that
    quietly used a name of its own would work somewhere nobody asked for, and leave the named
    file empty or absent.
    """
    mine = tmp_path / "mine.db"
    log = tmp_path / "mine.log"

    codes = _run_pytest([_environment(DATABASE_URL=f"sqlite+aiosqlite:///{mine}")], [log])

    assert codes == [0], log.read_text()
    assert mine.exists(), "the run wrote its tables somewhere the caller did not name"
    assert SEEDED_TABLE in _tables(mine), "the named database was connected to and then ignored"
