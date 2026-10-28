"""One command plays a round through her own runner, from a checkout at her pin.

Her `npm run golden -- --http <base>` plays the scripts, runs her judge and her checks and writes
`.golden/<name>.<stamp>.md`. The command here only finds her checkout, refuses one that is not at
the pin, hands the runner its key and keeps her reports. Everything it drives is a fake: a git
checkout, and an `npm` that plays nothing and calls no model.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from scripts import her_golden_round

KEY = "the-runner-key"
BASE = "http://localhost:8000/api/internalization-room"
FAKE_NPM = """#!/bin/sh
mkdir -p .golden
echo "$GOLDEN_HTTP_TOKEN|$*" > .ran
echo "played" > ".golden/P01-opening.2026-10-28T10-00-00.md"
exit "${FAKE_NPM_EXIT:-0}"
"""


def _git(where: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(where), "-c", "user.email=a@b.c", "-c", "user.name=a", *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.strip()


@pytest.fixture()
def her_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    checkout = tmp_path / "her"
    checkout.mkdir()
    _git(checkout, "init", "-q")
    _git(checkout, "commit", "-q", "--allow-empty", "-m", "the pin")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    npm = bin_dir / "npm"
    npm.write_text(FAKE_NPM)
    npm.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("TRIPOD_INTERNALIZATION_REPO", str(checkout))
    monkeypatch.setenv("INTERNALIZATION_ROOM_RUNNER_KEY", KEY)
    return checkout


def _round(tmp_path: Path, pin: str, *more: str) -> tuple[int, Path]:
    pin_file = tmp_path / "FREEZE_PIN"
    pin_file.write_text(f"repo her/repo\nbranch main\ncommit {pin}\n")
    out = tmp_path / "reports"
    code = her_golden_round.main(
        ["--base-url", BASE, "--pin-file", str(pin_file), "--out", str(out), *more]
    )
    return code, out


def test_a_round_at_the_pin_runs_her_runner_over_http_with_the_key_and_keeps_her_reports(
    her_checkout: Path, tmp_path: Path
) -> None:
    pin = _git(her_checkout, "rev-parse", "HEAD")

    code, out = _round(tmp_path, pin, "--backend-commit", "b4ckend")

    assert code == 0
    assert (her_checkout / ".ran").read_text().strip() == f"{KEY}|run golden -- --http {BASE}"
    assert (out / "P01-opening.2026-10-28T10-00-00.md").read_text().strip() == "played"
    judged = (out / "JUDGED.md").read_text()
    assert "b4ckend" in judged
    assert pin in judged


def test_a_checkout_at_another_commit_is_refused_naming_the_pin_and_plays_nothing(
    her_checkout: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pin = "18fa7c41f037e9f8728986400f5fcb4b3c243c4b"

    code, out = _round(tmp_path, pin)

    assert code == her_golden_round.REFUSED
    assert pin in capsys.readouterr().err
    assert not (her_checkout / ".ran").exists()
    assert not out.exists()


@pytest.mark.parametrize("her_exit", [1, 2, 3])
def test_her_runners_exit_code_is_the_rounds_and_what_it_wrote_is_kept(
    her_checkout: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, her_exit: int
) -> None:
    monkeypatch.setenv("FAKE_NPM_EXIT", str(her_exit))
    pin = _git(her_checkout, "rev-parse", "HEAD")

    code, out = _round(tmp_path, pin)

    assert code == her_exit
    assert (out / "P01-opening.2026-10-28T10-00-00.md").exists()


def test_a_round_without_the_runner_key_is_refused_before_anything_runs(
    her_checkout: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("INTERNALIZATION_ROOM_RUNNER_KEY")
    pin = _git(her_checkout, "rev-parse", "HEAD")

    code, _ = _round(tmp_path, pin)

    assert code == her_golden_round.REFUSED
    assert not (her_checkout / ".ran").exists()
