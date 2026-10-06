"""A production deploy waits for the three guards that a pull request already runs.

`deploy.yml` fires on a push to `main` and by hand, and `checks.yml` fires on a pull request, so a
direct push or a manual dispatch shipped with none of the three guards. They now run as the first
job of the deploy itself, and production is pinned to one instance while the turn door's in-flight
registry lives in one process (ADR 0050).

Nothing here runs a guard: GitHub does. These cases pin that the job exists, gates the deploy and
names the three commands. YAML 1.1 reads a bare `on` as the boolean `True`, so `_triggers` raises
when the block is missing instead of answering with an empty mapping every case would pass over.
"""

from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "deploy.yml"

GUARDS = [
    "scripts/check_doctrine.py",
    "scripts/sync_doctrine.py --check",
    "scripts/sync_internalization_canon.py --check",
]


def _deploy_workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _triggers(workflow: dict) -> dict:
    for key in (True, "on"):
        if key in workflow:
            return workflow[key]
    raise AssertionError("deploy.yml has no trigger block under `True` or 'on'")


def _checks_steps() -> list[dict]:
    return _deploy_workflow()["jobs"]["checks"]["steps"]


def _index_of_step_running(steps: list[dict], command: str) -> int:
    return next(i for i, step in enumerate(steps) if command in step.get("run", ""))


def test_the_production_deploy_waits_for_the_checks_job() -> None:
    needs = _deploy_workflow()["jobs"]["deploy"]["needs"]

    assert "checks" in ([needs] if isinstance(needs, str) else needs)


def test_the_checks_job_runs_the_three_guards_in_order() -> None:
    steps = _checks_steps()

    positions = [_index_of_step_running(steps, command) for command in GUARDS]

    assert positions == sorted(positions)


def test_the_canon_drift_check_in_the_deploy_carries_the_token_its_github_calls_need() -> None:
    steps = _checks_steps()
    drift = steps[_index_of_step_running(steps, GUARDS[2])]

    assert "GITHUB_TOKEN" in drift["env"]


def test_the_checks_job_installs_the_locked_dependencies_before_it_runs_a_guard() -> None:
    steps = _checks_steps()

    assert _index_of_step_running(steps, "uv sync --frozen --group dev") < _index_of_step_running(
        steps, GUARDS[0]
    )


def test_the_deploy_runs_on_a_push_to_main_and_by_hand_both_through_the_checks() -> None:
    workflow = _deploy_workflow()
    triggers = _triggers(workflow)

    assert "main" in triggers["push"]["branches"]
    assert "workflow_dispatch" in triggers
    assert "if" not in workflow["jobs"]["checks"]
    assert "if" not in workflow["jobs"]["deploy"]


def test_the_checks_job_turns_red_instead_of_hanging() -> None:
    assert _deploy_workflow()["jobs"]["checks"]["timeout-minutes"] == 10


def test_production_runs_one_instance() -> None:
    steps = _deploy_workflow()["jobs"]["deploy"]["steps"]
    deploy_step = next(step for step in steps if step["name"] == "Deploy Backend")

    assert "--max-instances=1" in deploy_step["run"].split()
