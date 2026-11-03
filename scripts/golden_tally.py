"""Lay the tally of her frozen app and ours side by side under her bar.

    uv run python scripts/golden_tally.py --hers golden/reports/<hers> [<re-run>...] \\
        --ours golden/reports/<ours> [<re-run>...]

Each folder holds the runs of one app: her runner's `<name>.run<k>.<stamp>.md` (a session passes
when its report says `**PASS**` and not `**FAIL**`), our bt runner's `<name>.run<k>.<stamp>.json`
(a script passes when no round of it failed a check) and the `JUDGED.<stamp>.md` that names the
app's pin. A folder named after the first is a re-run: the scripts it holds replace the earlier
rows of that app. Her bar: the copy passes when it has at most 10 passes fewer than hers; a script
that trails by 2 or more passes is listed "re-run before reading" until a re-run replaces it.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

MOST_PASSES_FEWER = 10
TRAILS_BY = 2


@dataclass(frozen=True)
class Row:
    passes: int
    runs: int
    rerun: bool = False


def _passed(report: Path) -> bool:
    if report.suffix == ".json":
        rounds = json.loads(report.read_text(encoding="utf-8"))["rounds"]
        return not any(line["checks"] for line in rounds)
    text = report.read_text(encoding="utf-8")
    return "**PASS**" in text and "**FAIL**" not in text


def _runs(folder: Path) -> dict[str, list[bool]]:
    found: dict[str, list[bool]] = {}
    for report in sorted(folder.glob("*.run*.*")):
        name, _, rest = report.name.partition(".run")
        if report.suffix in (".md", ".json") and not rest.endswith(
            (".transcript.txt", ".verdict.json")
        ):
            found.setdefault(name, []).append(_passed(report))
    return found


def rows(folders: list[Path]) -> dict[str, Row]:
    table: dict[str, Row] = {}
    for position, folder in enumerate(folders):
        for name, results in _runs(folder).items():
            table[name] = Row(sum(results), len(results), rerun=position > 0)
    return table


def _pin(folder: Path) -> str:
    for judged in sorted(folder.glob("JUDGED.*.md")):
        return " · ".join(judged.read_text(encoding="utf-8").splitlines()[:2])
    return "no pin recorded"


def tally(hers: list[Path], ours: list[Path]) -> str:
    theirs, mine = rows(hers), rows(ours)
    names = sorted(theirs.keys() | mine.keys())
    lines = ["| script | hers | ours | |", "|---|---|---|---|"]
    for name in names:
        her, our = theirs.get(name, Row(0, 0)), mine.get(name, Row(0, 0))
        replaced = her.rerun or our.rerun
        note = (
            "re-run before reading" if her.passes - our.passes >= TRAILS_BY and not replaced else ""
        )
        lines.append(f"| {name} | {her.passes}/{her.runs} | {our.passes}/{our.runs} | {note} |")
    her_total = sum(row.passes for row in theirs.values())
    our_total = sum(row.passes for row in mine.values())
    passes = her_total - our_total <= MOST_PASSES_FEWER
    verdict = "the copy passes" if passes else "the copy does not pass"
    return "\n".join(
        [
            f"# Tally — {len(names)} scripts",
            "",
            f"hers: {hers[0].name} · {_pin(hers[0])}",
            f"ours: {ours[0].name} · {_pin(ours[0])}",
            "",
            *lines,
            "",
            f"hers {her_total} · ours {our_total} · at most {MOST_PASSES_FEWER} passes fewer: "
            f"{verdict}",
            "",
        ]
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--hers", type=Path, nargs="+", required=True)
    parser.add_argument("--ours", type=Path, nargs="+", required=True)
    args = parser.parse_args(argv)
    print(tally(args.hers, args.ours))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
