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
#: four jobs: `lint` is a file carrying `ruff`, `boots` and `mypy`, and the issue names
#: `boots` separately because it is the one it most wants held. As jobs it is five, which is
#: what a push actually costs. Keyed by file, because nothing here assumes one file is one job.
GATES = {
    "lint.yml": {"ruff", "boots", "mypy"},
    "test.yml": {"test"},
    "migrations.yml": {"migrations"},
}

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
