"""The gates that guard the integration branch, pinned as a contract.

Nothing here touches the app. It pins `.github/workflows/`, which is what actually decides
whether a push to `integration/**` is audited at all.

The branch is no longer a depot — it is the base every new slice is cut from — and until
ENG-554 nothing ever ran on it, because a workflow triggered by `pull_request` needs a pull
request and the integration branch has none. It sat red on `ruff format` and was fixed by
whoever happened to branch off it next, which is luck rather than process.

A gate protects by being in the ancestor, not by being good — the argument the `boots` job
already makes about itself in `lint.yml`. These cases are what keeps the push trigger from
being quietly dropped from that ancestor later.

**On the `True` key.** YAML 1.1 reads a bare `on` as a boolean, so `yaml.safe_load` returns
the trigger block under `True` and not under `"on"`. Reading it as `wf["on"]` raises, and the
obvious repair — `wf.get("on", {})` — returns an empty mapping and every assertion below
would pass over nothing. `_triggers` refuses that: it fails loudly if the block is missing
rather than treating absence as an empty answer.
"""

from pathlib import Path

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"

#: ENG-554 names four gates — lint, test, migrations, boots — and that is four names, not
#: four jobs. Lint was five jobs once, each paying the same four setup steps, and a pull
#: request showed five checks for 40 seconds of work: ENG-969 collapsed them into one job
#: that runs the same seven commands in a queue. Keyed by file, because nothing here assumes
#: one file is one job.
GATES = {
    "lint.yml": {"lint"},
    "test.yml": {"test"},
    "migrations.yml": {"migrations"},
}

#: The seven commands the five jobs ran, in the order the single job runs them. Held as an
#: ordered subsequence: a check that stops being reached is a check that stopped guarding.
LINT_COMMANDS_IN_ORDER = [
    "ruff check .",
    "ruff format --check .",
    "import app.main",
    "mypy app/",
    "scripts/check_doctrine.py",
    "scripts/sync_doctrine.py --check",
    "scripts/sync_internalization_canon.py --check",
]

INTEGRATION_GLOB = "integration/**"

#: A push filter that reaches these would put every branch in the repository through four
#: jobs on every push. The cost of the test job alone is between 6 and 56 minutes (ENG-556),
#: so the trigger staying narrow is a property worth holding, not a detail.
TOO_BROAD = {"**", "*", "main", "master"}


def _workflow(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text())


def _triggers(workflow: dict, name: str) -> dict:
    """The `on:` block, which YAML 1.1 hands back under the boolean `True`.

    Raises rather than defaulting: an empty mapping here would make every caller pass.
    """
    for key in (True, "on"):
        if key in workflow:
            return workflow[key]
    raise AssertionError(f"{name} has no trigger block under `True` or 'on'")


@pytest.mark.parametrize("filename", sorted(GATES))
def test_the_gate_runs_on_a_push_to_the_integration_branch(filename: str) -> None:
    triggers = _triggers(_workflow(filename), filename)

    assert "push" in triggers, f"{filename} does not run on push at all"
    branches = triggers["push"]["branches"]
    assert INTEGRATION_GLOB in branches, f"{filename} push filter is {branches}"


@pytest.mark.parametrize("filename", sorted(GATES))
def test_the_gate_still_runs_on_pull_requests(filename: str) -> None:
    """The 24 open pull requests depend on this trigger; adding push must not cost it."""
    triggers = _triggers(_workflow(filename), filename)

    assert "pull_request" in triggers, f"{filename} stopped running on pull requests"


@pytest.mark.parametrize("filename", sorted(GATES))
def test_the_push_trigger_reaches_only_the_integration_branches(filename: str) -> None:
    triggers = _triggers(_workflow(filename), filename)
    branches = set(triggers["push"]["branches"])

    assert not branches & TOO_BROAD, f"{filename} would run on every push: {branches}"


@pytest.mark.parametrize(("filename", "jobs"), sorted(GATES.items()))
def test_the_gate_still_carries_the_jobs_it_is_named_for(filename: str, jobs: set) -> None:
    """Guards the other half: a trigger that fires on a file with no jobs guards nothing."""
    defined = set(_workflow(filename)["jobs"])

    assert jobs <= defined, f"{filename} lost {jobs - defined}"


#: A job with no `timeout-minutes` inherits GitHub's 360-minute default, which is how a hung
#: run stayed "pending" for six hours instead of turning red (ENG-913). The canon check was
#: the last job left without one. ENG-969 puts every gate under a ceiling: 10 for lint, whose
#: seven commands cost 40 seconds of work, and 10 for test, twice the five minutes its step
#: is expected to take now that the suite runs in four processes.
JOB_TIMEOUT_MINUTES = {
    ("test.yml", "test"): 10,
    ("lint.yml", "lint"): 10,
    ("migrations.yml", "migrations"): 5,
}


@pytest.mark.parametrize(
    ("filename", "job", "minutes"),
    sorted((filename, job, minutes) for (filename, job), minutes in JOB_TIMEOUT_MINUTES.items()),
)
def test_a_hung_job_turns_red_instead_of_staying_pending_for_hours(
    filename: str, job: str, minutes: int
) -> None:
    jobs = _workflow(filename)["jobs"]
    timeout = jobs[job].get("timeout-minutes")
    assert timeout == minutes, f"{filename}:{job} timeout-minutes is {timeout}, not {minutes}"


def _lint_steps() -> list[dict]:
    jobs = _workflow("lint.yml")["jobs"]
    assert "lint" in jobs, f"lint.yml defines {sorted(jobs)}, not a single `lint` job"
    return jobs["lint"]["steps"]


def _lint_step_running(fragment: str) -> dict:
    running = [step for step in _lint_steps() if fragment in step.get("run", "")]
    assert len(running) == 1, f"{fragment} is run by {len(running)} steps of the lint job"
    return running[0]


def test_lint_is_one_check_and_not_five() -> None:
    """Five jobs cost one pull request five lines and four repeated setups for 40 s of work."""
    jobs = sorted(_workflow("lint.yml")["jobs"])

    assert jobs == ["lint"], f"lint.yml defines {jobs}"


def test_the_one_job_runs_every_check_the_five_jobs_ran() -> None:
    """Collapsing the jobs must not drop a check: the seven commands still run, in order."""
    runs = [step["run"] for step in _lint_steps() if "run" in step]

    unreached = list(LINT_COMMANDS_IN_ORDER)
    for run in runs:
        if unreached and unreached[0] in run:
            unreached.pop(0)

    assert unreached == [], f"the lint job never reaches, in this order: {unreached}"


def test_the_canon_check_carries_the_token_its_api_calls_need() -> None:
    """Its two calls to Marcia's repository share the runner's 60 requests/hour without it."""
    step = _lint_step_running("scripts/sync_internalization_canon.py --check")

    assert step.get("env", {}).get("GITHUB_TOKEN"), f"{step.get('name')} has env {step.get('env')}"


def test_the_boot_import_carries_the_three_variables_it_needs() -> None:
    """The job-level env of the old `boots` job travels with the step, not with the job."""
    step = _lint_step_running("import app.main")

    assert set(step.get("env", {})) >= {"DATABASE_URL", "JWT_SECRET_KEY", "INNGEST_DEV"}, (
        f"the boot step has env {step.get('env')}"
    )


def test_the_suite_runs_in_four_processes_split_by_file() -> None:
    """ENG-969: the schema is created once per process, so the split has to be by file."""
    steps = _workflow("test.yml")["jobs"]["test"]["steps"]
    running_pytest = [step["run"] for step in steps if "pytest" in step.get("run", "")]
    assert len(running_pytest) == 1, f"test.yml runs pytest in {len(running_pytest)} steps"
    command = running_pytest[0]

    assert "-n 4" in command, f"the test step runs `{command}`"
    assert "--dist loadfile" in command, f"the test step runs `{command}`"
