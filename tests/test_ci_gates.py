"""The gates that guard the integration branch, pinned as a contract.

Nothing here touches the app. It pins `.github/workflows/`, which is what actually decides
whether a push to `integration/**` is audited at all.

The branch is no longer a depot — it is the base every new slice is cut from — and until
ENG-554 nothing ever ran on it, because a workflow triggered by `pull_request` needs a pull
request and the integration branch has none. It sat red on `ruff format` and was fixed by
whoever happened to branch off it next, which is luck rather than process.

A gate protects by being in the ancestor, not by being good — the argument the `boots` step
already makes about itself in `checks.yml`. These cases are what keeps the push trigger from
being quietly dropped from that ancestor later.

**On the `True` key.** YAML 1.1 reads a bare `on` as a boolean, so `yaml.safe_load` returns
the trigger block under `True` and not under `"on"`. Reading it as `wf["on"]` raises, and the
obvious repair — `wf.get("on", {})` — returns an empty mapping and every assertion below
would pass over nothing. `_triggers` refuses that: it fails loudly if the block is missing
rather than treating absence as an empty answer.
"""

import ast
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"
PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"
TESTS_DIR = Path(__file__).resolve().parent

#: ENG-554 names four gates — lint, test, migrations, boots — and that is four names, not
#: four jobs. Lint was five jobs once, each paying the same four setup steps, and a pull
#: request showed five checks for 40 seconds of work: ENG-969 collapsed them into one job
#: that runs the same seven commands in a queue. ENG-980 renamed that job `checks` because it
#: no longer only lints. Keyed by file, because nothing here assumes one file is one job.
GATES = {
    "checks.yml": {"checks"},
    "test.yml": {"test"},
    "migrations.yml": {"migrations"},
}

#: The seven commands the five jobs ran, in the order the single job runs them, followed by
#: the process-spawning tests ENG-980 moved into this job. Held as an ordered subsequence: a
#: check that stops being reached is a check that stopped guarding.
CHECKS_COMMANDS_IN_ORDER = [
    "ruff check .",
    "ruff format --check .",
    "import app.main",
    "mypy app/",
    "scripts/check_doctrine.py",
    "scripts/sync_doctrine.py --check",
    "scripts/sync_internalization_canon.py --check",
    "-m fresh_interpreter",
]

INTEGRATION_GLOB = "integration/**"

#: A push filter that reaches these would put every branch in the repository through four
#: jobs on every push. The cost of the test job alone is between 6 and 56 minutes (ENG-556),
#: so the trigger staying narrow is a property worth holding, not a detail.
TOO_BROAD = {"**", "*", "main", "master"}

#: ENG-980's own lists: the fourteen files that walk a migration and the three that open a
#: fresh interpreter, read here rather than derived, so a file the ticket names and the repo
#: marks wrong is what `test_the_seventeen_files_carry_the_marker_the_ticket_gives_them`
#: catches instead of something this file assumes into agreement with itself.
MIGRATION_FILES = {
    "test_ir_spine_migration.py",
    "test_device_migration.py",
    "test_ir_project_id_migration.py",
    "test_ir_coverage_events_migration.py",
    "test_ir_session_ended_at_migration.py",
    "test_ir_attended_migration.py",
    "test_oc_recordings_dedupe_migration.py",
    "test_ir_prepared_pericope_migration.py",
    "test_ir_segments_migration.py",
    "test_ir_session_language_migration.py",
    "test_ir_bridge_mode_migration.py",
    "test_ir_session_version_migration.py",
    "test_ir_the_hard_stretch_migration.py",
    "test_ir_turns_migration.py",
}

FRESH_INTERPRETER_FILES = {
    "test_internalization_room_import_order.py",
    "test_app_boots.py",
    "test_the_suite_runs_twice_at_once.py",
}


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
#: the last job left without one. ENG-969 puts every gate under a ceiling: 10 for lint (now
#: checks), whose seven commands cost 40 seconds of work, and 10 for test, twice the five
#: minutes its step is expected to take now that the suite runs in four processes. ENG-980
#: raises the migrations ceiling to fit the `-m migration` step it adds, at twice the 3m04s
#: the whole job measured on shemaobt/shema-api#474's own CI run. ENG-1092 raises the test
#: ceiling to 12: at ~3700 tests the step measured 6m21s on shemaobt/shema-api#534, and a
#: run cancelled at 7m15s was the timeout doing the wrong job.
JOB_TIMEOUT_MINUTES = {
    ("test.yml", "test"): 12,
    ("checks.yml", "checks"): 10,
    ("migrations.yml", "migrations"): 7,
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


def _checks_steps() -> list[dict]:
    jobs = _workflow("checks.yml")["jobs"]
    assert "checks" in jobs, f"checks.yml defines {sorted(jobs)}, not a single `checks` job"
    return jobs["checks"]["steps"]


def _checks_step_running(fragment: str) -> dict:
    running = [step for step in _checks_steps() if fragment in step.get("run", "")]
    assert len(running) == 1, f"{fragment} is run by {len(running)} steps of the checks job"
    return running[0]


def test_checks_is_one_check_and_not_five() -> None:
    """Five jobs cost one pull request five lines and four repeated setups for 40 s of work."""
    jobs = sorted(_workflow("checks.yml")["jobs"])

    assert jobs == ["checks"], f"checks.yml defines {jobs}"


def test_checks_yml_replaces_lint_yml() -> None:
    """G4 (criterion 5): a stale lint.yml beside checks.yml would run the same checks twice."""
    assert not (WORKFLOWS / "lint.yml").exists(), "lint.yml still exists beside checks.yml"

    workflow = _workflow("checks.yml")
    assert workflow.get("name") == "Checks", f"checks.yml is named {workflow.get('name')}"


def test_the_one_job_runs_every_check_the_five_jobs_ran() -> None:
    """Collapsing the jobs must not drop a check: the seven commands, then the tests that
    spawn processes, still run, in order."""
    runs = [step["run"] for step in _checks_steps() if "run" in step]

    unreached = list(CHECKS_COMMANDS_IN_ORDER)
    for run in runs:
        if unreached and unreached[0] in run:
            unreached.pop(0)

    assert unreached == [], f"the checks job never reaches, in this order: {unreached}"


def test_the_canon_check_carries_the_token_its_api_calls_need() -> None:
    """Its two calls to Marcia's repository share the runner's 60 requests/hour without it."""
    step = _checks_step_running("scripts/sync_internalization_canon.py --check")

    assert step.get("env", {}).get("GITHUB_TOKEN"), f"{step.get('name')} has env {step.get('env')}"


def test_the_boot_import_carries_the_three_variables_it_needs() -> None:
    """The job-level env of the old `boots` job travels with the step, not with the job."""
    step = _checks_step_running("import app.main")

    assert set(step.get("env", {})) >= {"DATABASE_URL", "JWT_SECRET_KEY", "INNGEST_DEV"}, (
        f"the boot step has env {step.get('env')}"
    )


def test_the_suite_runs_in_four_processes_split_by_file() -> None:
    """ENG-969: the schema is created once per process, so the split has to be by file.

    G2 (criterion 3): ENG-980 selects out the tests that spawn processes to prove what they
    prove — they run in Migrations and Checks instead.
    """
    steps = _workflow("test.yml")["jobs"]["test"]["steps"]
    running_pytest = [step["run"] for step in steps if "pytest" in step.get("run", "")]
    assert len(running_pytest) == 1, f"test.yml runs pytest in {len(running_pytest)} steps"
    command = running_pytest[0]

    assert "-n 4" in command, f"the test step runs `{command}`"
    assert "--dist loadfile" in command, f"the test step runs `{command}`"
    assert '-m "not migration and not fresh_interpreter"' in command, (
        f"the test step runs `{command}`"
    )


def test_the_migrations_job_runs_the_migration_marked_tests_with_the_variable_cleared() -> None:
    """G3 (criterion 4): a step `env` cannot unset a job-level `env` in Actions — only the
    `run` line can, and without it the fourteen would run serially, against the job's
    Postgres, on top of the schema the previous step just migrated."""
    steps = _workflow("migrations.yml")["jobs"]["migrations"]["steps"]
    running = [step for step in steps if "-m migration" in step.get("run", "")]

    assert len(running) == 1, f"-m migration runs in {len(running)} steps of migrations.yml"
    run = running[0]["run"]
    assert "-u DATABASE_URL" in run or "unset DATABASE_URL" in run, (
        f"DATABASE_URL is not cleared before the migration-marked tests: {run}"
    )


def _pyproject_pytest_markers() -> dict[str, str]:
    config = tomllib.loads(PYPROJECT.read_text())
    entries = config["tool"]["pytest"]["ini_options"].get("markers", [])
    return dict(entry.split(":", 1) for entry in entries)


def test_the_two_markers_are_registered() -> None:
    """G1 (criterion 1): an unregistered marker selects nothing instead of failing loudly."""
    markers = _pyproject_pytest_markers()

    assert set(markers) == {"migration", "fresh_interpreter"}, (
        f"pyproject.toml registers {sorted(markers)}"
    )
    for name, description in markers.items():
        assert description.strip(), f"{name} has no description"


def _module_level_marker(path: Path) -> str | None:
    """The name of the mark a file's `pytestmark = pytest.mark.<name>` line carries, by AST.

    Reads the source rather than importing it: importing one of the seventeen files to ask
    what it is marked with is exactly the cost this ticket moves out of the PR job.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "pytestmark" for target in node.targets
        ):
            continue
        value = node.value
        if (
            isinstance(value, ast.Attribute)
            and isinstance(value.value, ast.Attribute)
            and isinstance(value.value.value, ast.Name)
            and value.value.value.id == "pytest"
            and value.value.attr == "mark"
        ):
            return value.attr
    return None


def test_the_seventeen_files_carry_the_marker_the_ticket_gives_them() -> None:
    """G6 (criteria 6 and 7): placement. Coverage (G7) does not prove a file sits in the right
    one of the three jobs, only that it sits in one — this is the test that goes red if a
    migration file is marked `fresh_interpreter` or left unmarked but selected by coincidence.
    """
    marks = {path.name: _module_level_marker(path) for path in sorted(TESTS_DIR.glob("test_*.py"))}

    for name in MIGRATION_FILES:
        assert marks[name] == "migration", f"{name} carries {marks[name]!r}, not 'migration'"
    for name in FRESH_INTERPRETER_FILES:
        assert marks[name] == "fresh_interpreter", (
            f"{name} carries {marks[name]!r}, not 'fresh_interpreter'"
        )

    named = MIGRATION_FILES | FRESH_INTERPRETER_FILES
    stray = {name: mark for name, mark in marks.items() if mark is not None and name not in named}
    assert stray == {}, f"marked outside the ticket's lists: {stray}"


def _collect(*args: str) -> set[str]:
    """The node ids one selection collects, in a child interpreter.

    A plugin hook collecting in-process would re-import the suite here, in this file, which
    is the cost ENG-980 moves out of the PR job in the first place — so this case pays a
    subprocess itself and carries `fresh_interpreter` below.
    """
    command = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "--collect-only",
        "-q",
        "-p",
        "no:cacheprovider",
        *args,
    ]
    finished = subprocess.run(
        command,
        cwd=TESTS_DIR.parent,
        capture_output=True,
        text=True,
    )
    assert finished.returncode in (0, 5), (
        f"collecting {args} exited {finished.returncode}: {finished.stderr}"
    )
    return {line for line in finished.stdout.splitlines() if "::" in line}


@pytest.mark.fresh_interpreter
def test_the_three_selections_partition_the_suite() -> None:
    """G7 (criterion 2): the risk this ticket closes — a file cannot fall outside all three
    jobs without this going red. Falsify by unmarking one migration file: its tests fall into
    the PR selection, so the union still holds and this test stays green — placement going
    wrong is `test_the_seventeen_files_carry_the_marker_the_ticket_gives_them`'s job, not
    this one's.
    """
    whole = _collect()
    migration = _collect("-m", "migration")
    fresh_interpreter = _collect("-m", "fresh_interpreter")
    the_rest = _collect("-m", "not migration and not fresh_interpreter")

    assert migration & fresh_interpreter == set(), migration & fresh_interpreter
    assert migration & the_rest == set(), migration & the_rest
    assert fresh_interpreter & the_rest == set(), fresh_interpreter & the_rest
    assert migration | fresh_interpreter | the_rest == whole, whole - (
        migration | fresh_interpreter | the_rest
    )
