from __future__ import annotations

from pathlib import Path

import pytest

from scripts import sync_doctrine
from scripts.sync_doctrine import Pin, check, retired_faults

SELF_CHECK = "draft_check_system_prompt.md"
SELF_CHECK_PATH = f"app/services/internalization_room/prompts/{SELF_CHECK}"
DECISION = "the production team's decision of 8 Oct 2026"


def _pin(digests: dict[str, str]) -> Pin:
    return Pin(repo="", branch="", commit="f" * 40, digests=digests)


def test_a_retired_prompt_that_comes_back_to_the_prompts_directory_is_named_as_returned(
    tmp_path: Path,
) -> None:
    retired = {SELF_CHECK: DECISION}

    assert retired_faults(_pin({}), retired, root=tmp_path) == []

    (tmp_path / SELF_CHECK_PATH).parent.mkdir(parents=True)
    (tmp_path / SELF_CHECK_PATH).write_text("hers\n", encoding="utf-8")

    assert retired_faults(_pin({}), retired, root=tmp_path) == [f"returned: {SELF_CHECK_PATH}"], (
        "a prompt the team retired sat back in the room's prompts directory and the check let it"
    )


def test_a_pin_that_still_records_a_retired_prompt_is_named_as_pinned(tmp_path: Path) -> None:
    pin = _pin({SELF_CHECK_PATH: "7" * 64})

    assert retired_faults(pin, {SELF_CHECK: DECISION}, root=tmp_path) == [
        f"pinned: {SELF_CHECK_PATH}"
    ], "the freeze pin kept vouching for bytes the room no longer carries"


def test_the_check_ci_runs_fails_on_a_retired_prompt_that_is_back_on_disk(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    on_disk = "guide_system_prompt.md"
    monkeypatch.setattr(sync_doctrine, "RETIRED_PROMPTS", {on_disk: DECISION})

    assert check() == 1
    assert f"returned: app/services/internalization_room/prompts/{on_disk}" in (
        capsys.readouterr().err
    ), "the doctrine check went green with a retired prompt on disk"
