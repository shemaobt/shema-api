from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"
COMPILER = "https://github.com/MarciaSuzuki/tripod_compiler.git"


def _steps(workflow: str, job: str) -> list[dict[str, Any]]:
    return yaml.safe_load((WORKFLOWS / workflow).read_text())["jobs"][job]["steps"]


def _index(steps: list[dict[str, Any]], fragment: str) -> int:
    found = [index for index, step in enumerate(steps) if fragment in step.get("run", "")]
    assert len(found) == 1, f"{fragment} is run by {len(found)} steps"
    return found[0]


def test_the_canon_smoke_runs_on_every_pull_request() -> None:
    steps = _steps("checks.yml", "checks")
    smoke = steps[_index(steps, "uv run python scripts/smoke_internalization_canon.py")]

    assert smoke.get("env", {}).get("DATABASE_URL"), f"{smoke.get('name')} has {smoke.get('env')}"


def test_a_deploy_holds_the_canon_to_a_clone_of_the_compiler_before_it_builds() -> None:
    steps = _steps("deploy.yml", "deploy")
    check = _index(steps, "scripts/sync_internalization_canon.py --check")
    clone = steps[check]["env"]["TRIPOD_COMPILER_REPO"]
    build = next(
        index for index, step in enumerate(steps) if step["name"] == "Build and Push Backend"
    )
    cloned = [
        index
        for index, step in enumerate(steps)
        if COMPILER in step.get("run", "") and clone in step["run"]
    ]

    assert cloned and cloned[0] < check < build
