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


def test_new_canon_has_its_missing_titles_filled_before_the_smoke_checks_hers() -> None:
    steps = _steps()
    filled = _index("scripts/fill_scene_titles.py")

    assert (
        _index("scripts/sync_internalization_canon.py --sync")
        < filled
        < _index("scripts/smoke_internalization_canon.py")
    ), "a sincronização não preenchia os títulos que faltam antes da checagem dos dela"
    assert steps[filled].get("if") == UPDATED


def test_the_change_carries_the_titles_the_fill_wrote() -> None:
    change = _steps()[_index("peter-evans/create-pull-request")]["with"]

    assert (
        "app/services/internalization_room/canon/ui-labels.pt.json" in change["add-paths"].split()
    ), "os títulos preenchidos ficavam fora da mudança aberta"


def test_the_change_carries_her_title_and_her_review_sentence() -> None:
    change = _steps()[_index("peter-evans/create-pull-request")]["with"]

    assert change["title"] == "Canon sync: new published canon from the compiler"
    assert "**Review the new content, then merge to ship it.**" in change["body"]


def test_the_change_is_opened_with_an_app_token_so_its_checks_start() -> None:
    mint = _steps()[_index("actions/create-github-app-token")]
    change = _steps()[_index("peter-evans/create-pull-request")]
    body = " ".join(change["with"]["body"].split())

    assert mint["if"] == UPDATED
    assert mint["with"]["permission-contents"] == "write"
    assert mint["with"]["permission-pull-requests"] == "write"
    assert _index("actions/create-github-app-token") < _index("peter-evans/create-pull-request")
    assert change["with"]["token"] == "${{ steps.app-token.outputs.token }}", (
        "a mudança aberta com o GITHUB_TOKEN do job não dispara nenhum check"
    )
    assert "start on it as on any change: merge only once they pass" in body
    assert "Close and reopen" not in body, "o texto ainda mandava fechar e reabrir"


def test_the_change_leaves_the_wait_for_a_team_session_to_the_deploy() -> None:
    body = " ".join(_steps()[_index("peter-evans/create-pull-request")]["with"]["body"].split())

    assert "the deploy waits while a team session is open" in body
    assert "merge only outside a team session" not in body, "quem mesclava era mandado esperar"


def test_the_change_names_the_titles_a_model_filled_in() -> None:
    body = " ".join(_steps()[_index("peter-evans/create-pull-request")]["with"]["body"].split())

    assert "`ui-labels.pt.json`" in body, (
        "os títulos preenchidos chegavam sem que o texto os citasse"
    )
    assert "a model's draft, not hers" in body
    assert body.index("ran in the job that opened this change") < body.index(
        "`ui-labels.pt.json`"
    ), "o texto nomeava o preenchimento antes de dizer o que o trabalho já rodou"


def test_nothing_in_it_merges() -> None:
    text = WORKFLOW.read_text()

    assert "gh pr merge" not in text
    assert "merge-method" not in text
    assert "auto-merge" not in text
    assert "enable-pull-request-automerge" not in text


def test_the_scheduled_sync_runs_the_sync_and_never_the_prune() -> None:
    runs = [step["run"] for step in _steps() if "run" in step]
    canon_runs = [run for run in runs if "sync_internalization_canon.py" in run]

    assert canon_runs, "the control: the workflow runs the canon script"
    assert all("--sync" in run or "--check" in run for run in canon_runs)
    assert not [run for run in runs if "--prune" in run], (
        "o agendamento apagava canon sem os pins vivos de produção"
    )
