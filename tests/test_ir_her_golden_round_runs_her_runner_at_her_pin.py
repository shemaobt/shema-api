"""One command plays a round through her own runner at her pin; every dependency is a fake."""

from __future__ import annotations

import os
import subprocess
import threading
from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from scripts import her_golden_round

KEY = "the-runner-key"
BASE = "http://localhost:8000/api/internalization-room"
FAKE_NPM = """#!/bin/sh
mkdir -p .golden
echo "$GOLDEN_HTTP_TOKEN|$*" > .golden/ran
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


def _round(
    tmp_path: Path, pin: str, *, base: str = BASE, backend: str | None = "any"
) -> tuple[int, Path]:
    pin_file = tmp_path / "FREEZE_PIN"
    pin_file.write_text(f"repo her/repo\nbranch main\ncommit {pin}\n")
    out = tmp_path / "reports"
    flags = ["--base-url", base, "--pin-file", str(pin_file), "--out", str(out)]
    code = her_golden_round.main(flags + (["--backend-commit", backend] if backend else []))
    return code, out


def test_a_round_at_the_pin_runs_her_runner_over_http_with_the_key_and_keeps_her_reports(
    her_checkout: Path, tmp_path: Path
) -> None:
    pin = _git(her_checkout, "rev-parse", "HEAD")

    code, out = _round(tmp_path, pin, backend="b4ckend")

    assert code == 0
    assert (
        her_checkout / ".golden" / "ran"
    ).read_text().strip() == f"{KEY}|run golden -- --http {BASE}"
    assert (out / "P01-opening.2026-10-28T10-00-00.md").read_text().strip() == "played"
    (judged,) = out.glob("JUDGED.*.md")
    assert "b4ckend" in judged.read_text()
    assert pin in judged.read_text()


def test_a_checkout_at_another_commit_is_refused_naming_the_pin_and_plays_nothing(
    her_checkout: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pin = "18fa7c41f037e9f8728986400f5fcb4b3c243c4b"

    code, out = _round(tmp_path, pin)

    assert code == her_golden_round.REFUSED
    assert pin in capsys.readouterr().err
    assert not (her_checkout / ".golden" / "ran").exists()
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
    assert not (her_checkout / ".golden" / "ran").exists()


def test_a_checkout_carrying_a_change_to_the_pin_is_refused_and_plays_nothing(
    her_checkout: Path, tmp_path: Path
) -> None:
    (her_checkout / "judge.ts").write_text("original")
    _git(her_checkout, "add", "judge.ts")
    _git(her_checkout, "commit", "-q", "-m", "the pin")
    pin = _git(her_checkout, "rev-parse", "HEAD")
    (her_checkout / "judge.ts").write_text("patched")

    code, _ = _round(tmp_path, pin)

    assert code == her_golden_round.REFUSED
    assert not (her_checkout / ".golden" / "ran").exists()


@pytest.mark.parametrize("where", ["missing", "not-a-checkout"])
def test_a_path_that_is_not_her_checkout_is_refused_not_reported_as_a_failed_session(
    her_checkout: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, where: str
) -> None:
    pin = _git(her_checkout, "rev-parse", "HEAD")
    (tmp_path / "not-a-checkout").mkdir()
    monkeypatch.setenv("TRIPOD_INTERNALIZATION_REPO", str(tmp_path / where))

    code, _ = _round(tmp_path, pin)

    assert code == her_golden_round.REFUSED


def test_reports_already_in_her_checkout_are_not_copied_and_a_second_round_keeps_the_first_note(
    her_checkout: Path, tmp_path: Path
) -> None:
    (her_checkout / ".golden").mkdir()
    (her_checkout / ".golden" / "OLD.2026-01-01T00-00-00.md").write_text("an earlier round")
    pin = _git(her_checkout, "rev-parse", "HEAD")

    _, out = _round(tmp_path, pin, backend="first")
    _round(tmp_path, pin, backend="second")

    assert not (out / "OLD.2026-01-01T00-00-00.md").exists()
    notes = sorted(note.read_text().split()[2] for note in out.glob("JUDGED.*.md"))
    assert notes == ["first", "second"]


@pytest.fixture()
def a_backend() -> Iterator[Callable[[bytes], str]]:
    servers: list[HTTPServer] = []

    def serve(body: bytes) -> str:
        class Version(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(body)

        server = HTTPServer(("127.0.0.1", 0), Version)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return f"http://127.0.0.1:{server.server_port}/api/internalization-room"

    yield serve
    for server in servers:
        server.shutdown()


def test_the_backend_commit_judged_is_the_one_the_running_backend_reports(
    her_checkout: Path, tmp_path: Path, a_backend: Callable[[bytes], str]
) -> None:
    pin = _git(her_checkout, "rev-parse", "HEAD")
    code, out = _round(tmp_path, pin, base=a_backend(b'{"build": "deployed-sha"}'), backend=None)

    assert code == 0
    (judged,) = out.glob("JUDGED.*.md")
    assert "backend commit: deployed-sha" in judged.read_text()


@pytest.mark.parametrize("answer", [b'{"build": "unknown"}', b"<html>", b"{}"])
def test_a_backend_that_does_not_name_its_build_is_refused_not_recorded_as_unknown(
    her_checkout: Path, tmp_path: Path, a_backend: Callable[[bytes], str], answer: bytes
) -> None:
    pin = _git(her_checkout, "rev-parse", "HEAD")

    code, _ = _round(tmp_path, pin, base=a_backend(answer), backend=None)

    assert code == her_golden_round.REFUSED
    assert not (her_checkout / ".golden" / "ran").exists()


def test_a_script_added_to_her_checkout_without_a_commit_is_refused(
    her_checkout: Path, tmp_path: Path
) -> None:
    pin = _git(her_checkout, "rev-parse", "HEAD")
    (her_checkout / "golden" / "sessions").mkdir(parents=True)
    (her_checkout / "golden" / "sessions" / "ours.json").write_text("{}")

    code, _ = _round(tmp_path, pin)

    assert code == her_golden_round.REFUSED
    assert not (her_checkout / ".golden" / "ran").exists()


def test_rounds_five_plays_her_set_five_times_and_names_each_report_by_script_and_run(
    her_checkout: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pin = _git(her_checkout, "rev-parse", "HEAD")
    pin_file = tmp_path / "FREEZE_PIN"
    pin_file.write_text(f"repo her/repo\nbranch main\ncommit {pin}\n")
    out = tmp_path / "reports"
    counter = tmp_path / "counter"
    counter.write_text("0")
    npm = tmp_path / "bin" / "npm"
    npm.write_text(
        "#!/bin/sh\nmkdir -p .golden\nn=$(($(cat " + str(counter) + ") + 1))\n"
        "echo $n > " + str(counter) + '\necho played > ".golden/P01-opening.run-$n.md"\n'
    )

    code = her_golden_round.main(
        [
            *["--base-url", BASE, "--pin-file", str(pin_file), "--out", str(out)],
            *["--backend-commit", "b4ckend", "--rounds", "5"],
        ]
    )

    assert code == 0
    assert sorted(path.name for path in out.glob("P01-opening.*.md")) == [
        f"P01-opening.run{k}.run-{k}.md" for k in range(1, 6)
    ]
    (judged,) = out.glob("JUDGED.*.md")
    assert "b4ckend" in judged.read_text()
