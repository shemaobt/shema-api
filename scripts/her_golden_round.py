"""Play a golden round through her own runner, from her checkout at the pin.

Her runner (`npm run golden -- --http <base>`) plays her scripts against the Golden doors, runs
her judge and her mechanical checks, and writes `.golden/<name>.<stamp>.md`. Nothing here
patches it: the command finds her checkout through `TRIPOD_INTERNALIZATION_REPO`, refuses one
that is not at the commit `docs/doctrine/FREEZE_PIN` names, hands the runner our key as
`GOLDEN_HTTP_TOKEN`, and copies the reports that run wrote into `golden/reports/<date>/` beside
a `JUDGED.md` naming the backend commit and the pin.

Her exit code is the round's: 0 passed, 1 a session failed, 2 her preflight stopped the run,
3 the backend died mid-script. 4 is ours: refused before anything was played.

    TRIPOD_INTERNALIZATION_REPO=~/Tripod-Internalization INTERNALIZATION_ROOM_RUNNER_KEY=<key> \\
        uv run python scripts/her_golden_round.py --base-url <host>/api/internalization-room
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FREEZE_PIN = ROOT / "docs/doctrine/FREEZE_PIN"
REFUSED = 4


def _pin(record: str) -> str:
    return next(line.split()[1] for line in record.splitlines() if line.startswith("commit "))


def _head(where: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(where), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()


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
    if _head(checkout) != pin:
        print(f"refused: {checkout} is not at the pin {pin}", file=sys.stderr)
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
    (out / "JUDGED.md").write_text(
        f"backend commit: {args.backend_commit or _head(ROOT)}\n"
        f"her pin: {pin}\n"
        f"base: {args.base_url}\n"
        f"exit: {played.returncode}\n"
    )
    return played.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
