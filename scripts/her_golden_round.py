"""Play a golden round through her own runner, from her checkout at the pin.

Nothing of hers is patched. The command finds her checkout through `TRIPOD_INTERNALIZATION_REPO`,
refuses one that is not at the commit `docs/doctrine/FREEZE_PIN` names or carries changes to it,
runs `npm run golden -- --http <base>` with our key as `GOLDEN_HTTP_TOKEN`, and copies the reports
that run wrote into `golden/reports/<date>/` beside a `JUDGED.<stamp>.md` naming the pin and the
backend commit the running backend reports at `/api/version`.

Her exit code is the round's: 0 passed, 1 a session failed, 2 her preflight stopped the run,
3 the backend died mid-script. 4 is ours: refused before anything was played.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FREEZE_PIN = ROOT / "docs/doctrine/FREEZE_PIN"
REFUSED = 4


def _pin(record: str) -> str:
    return next(line.split()[1] for line in record.splitlines() if line.startswith("commit "))


def _git(where: Path, *args: str) -> str | None:
    done = subprocess.run(["git", "-C", str(where), *args], capture_output=True, text=True)
    return done.stdout.strip() if done.returncode == 0 else None


def _backend_commit(base_url: str) -> str:
    version = base_url.partition("/api/")[0] + "/api/version"
    with urllib.request.urlopen(version, timeout=10) as answered:
        return str(json.load(answered)["build"])


def _reports(checkout: Path) -> set[Path]:
    return set((checkout / ".golden").glob("*.md"))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--pin-file", type=Path, default=FREEZE_PIN)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--backend-commit")
    args = parser.parse_args(argv)

    where = os.environ.get("TRIPOD_INTERNALIZATION_REPO")
    key = os.environ.get("INTERNALIZATION_ROOM_RUNNER_KEY")
    if not where or not key:
        print(
            "refused: set TRIPOD_INTERNALIZATION_REPO to her checkout and "
            "INTERNALIZATION_ROOM_RUNNER_KEY to the runner key",
            file=sys.stderr,
        )
        return REFUSED
    checkout = Path(where)
    pin = _pin(args.pin_file.read_text())
    if _git(checkout, "rev-parse", "HEAD") != pin:
        print(f"refused: {checkout} is not a checkout at the pin {pin}", file=sys.stderr)
        return REFUSED
    if _git(checkout, "status", "--porcelain", "--untracked-files=no"):
        print(f"refused: {checkout} carries changes to the pin {pin}", file=sys.stderr)
        return REFUSED
    try:
        backend = args.backend_commit or _backend_commit(args.base_url)
    except OSError as error:
        print(f"refused: no backend answered at {args.base_url} ({error})", file=sys.stderr)
        return REFUSED

    before = _reports(checkout)
    played = subprocess.run(
        ["npm", "run", "golden", "--", "--http", args.base_url],
        cwd=checkout,
        env={**os.environ, "GOLDEN_HTTP_TOKEN": key},
    )

    out = args.out or ROOT / "golden/reports" / datetime.now(UTC).date().isoformat()
    out.mkdir(parents=True, exist_ok=True)
    for report in _reports(checkout) - before:
        shutil.copy(report, out / report.name)
    (out / f"JUDGED.{datetime.now(UTC):%Y%m%dT%H%M%S%f}.md").write_text(
        f"backend commit: {backend}\n"
        f"her pin: {pin}\n"
        f"base: {args.base_url}\n"
        f"exit: {played.returncode}\n"
    )
    return played.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
