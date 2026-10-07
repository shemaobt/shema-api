from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "canon-sync.yml"
UPDATED = "steps.sync.outputs.updated == 'true'"


def _workflow() -> dict[Any, Any]:
    return yaml.safe_load(WORKFLOW.read_text())


def _steps() -> list[dict[str, Any]]:
    return _workflow()["jobs"]["sync"]["steps"]


def _index(fragment: str) -> int:
    found = [
        index
        for index, step in enumerate(_steps())
        if fragment in step.get("run", "") or fragment in step.get("uses", "")
    ]
    assert len(found) == 1, f"{fragment} is in {len(found)} steps"
    return found[0]


def test_it_runs_on_mondays_and_thursdays_at_nine_seventeen_utc() -> None:
    assert _workflow()[True]["schedule"] == [{"cron": "17 9 * * 1,4"}]


@pytest.mark.parametrize(
    ("last_line", "updated"),
    [
        ("UP_TO_DATE", "updated=false"),
        ("pinned at 1eadbeef1eadbeef1eadbeef1eadbeef1eadbeef", "updated=true"),
    ],
)
def test_it_decides_whether_anything_is_new_from_the_syncs_own_last_line(
    last_line: str, updated: str, tmp_path: Path
) -> None:
    sync = _steps()[_index("scripts/sync_internalization_canon.py --sync")]
    uv = tmp_path / "bin" / "uv"
    uv.parent.mkdir()
    uv.write_text(f"#!/bin/sh\necho '  meaning-map/P01-Ruth-1-1-5.md'\necho '{last_line}'\n")
    uv.chmod(0o755)
    output = tmp_path / "output"

    subprocess.run(
        ["bash", "-e", "-c", sync["run"].replace("/tmp/sync.log", str(tmp_path / "sync.log"))],
        check=True,
        env={
            **os.environ,
            "PATH": f"{uv.parent}:{os.environ['PATH']}",
            "GITHUB_OUTPUT": str(output),
        },
    )

    assert sync["id"] == "sync"
    assert output.read_text() == f"{updated}\n"


def test_only_new_canon_reaches_the_guard_the_smoke_the_build_and_the_change_in_that_order() -> (
    None
):
    steps = _steps()
    order = [
        _index("scripts/sync_internalization_canon.py --sync"),
        _index("https://github.com/MarciaSuzuki/tripod_compiler.git"),
        _index("scripts/sync_internalization_canon.py --check"),
        _index("scripts/smoke_internalization_canon.py"),
        _index("docker build"),
        _index("peter-evans/create-pull-request"),
    ]

    assert order == sorted(order)
    assert all(steps[index].get("if") == UPDATED for index in order[1:])
    check = steps[order[2]]
    clone = steps[order[1]]["run"]
    assert check["env"]["TRIPOD_COMPILER_REPO"] in clone


def test_the_change_carries_her_title_and_her_review_sentence() -> None:
    change = _steps()[_index("peter-evans/create-pull-request")]["with"]

    assert change["title"] == "Canon sync: new published canon from the compiler"
    assert "**Review the new content, then merge to ship it.**" in change["body"]


def test_nothing_in_it_merges() -> None:
    text = WORKFLOW.read_text()

    assert "gh pr merge" not in text
    assert "merge-method" not in text
    assert "auto-merge" not in text
    assert "enable-pull-request-automerge" not in text
