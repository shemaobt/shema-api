"""One-shot fix: give every recording the hours count the duration measured on its file.

Thin wrapper over app.services.oral_collector.duration_audit so the logic is covered by the
backend test suite. Dry run by default; --write updates the divergent rows in one transaction.
"""

import argparse
import asyncio
import shutil
import sys

from app.core.database import AsyncSessionLocal
from app.services.oral_collector.duration_audit import audit_durations
from app.services.platform.audio_duration import PROBE

HOW_TO_RUN = """\
Reads the bucket GCS_OC_BUCKET names and the database DATABASE_URL names.
Production's recordings live in tripod-image-uploads. Dry-run first on a Neon branch:
  DATABASE_URL=<branch> GCS_OC_BUCKET=tripod-image-uploads \\
    uv run python -m scripts.fix_recording_durations
Then the same with --write on the branch, check it, and only then on production.
"""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Measure every counted recording on its file and fix stored durations "
        "more than one second off.",
        epilog=HOW_TO_RUN,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--write", action="store_true", help="write the measured durations (default: dry run)"
    )
    return parser


async def run(argv: list[str]) -> int:
    args = _parser().parse_args(argv)
    if shutil.which(PROBE) is None:
        print(
            f"{PROBE} is not installed: nothing can be measured, nothing was read.", file=sys.stderr
        )
        return 2

    audit = await audit_durations(AsyncSessionLocal, write=args.write)

    print(f"bucket: {audit.bucket}")
    for row in audit.divergent:
        print(
            f"{row.recording_id}  {row.project_id}  "
            f"stored {row.stored_seconds:.3f} s  measured {row.measured_seconds:.3f} s"
        )
    for project in audit.hours:
        print(
            f"hours  {project.project_id}  before {project.before:.2f}  after {project.after:.2f}"
        )
    for unreadable in audit.unreadable:
        print(
            f"unreadable  {unreadable.recording_id}  {unreadable.project_id}  {unreadable.reason}"
        )
    print(f"divergent: {len(audit.divergent)}")
    print(f"unreadable: {len(audit.unreadable)}")
    if args.write:
        print(f"written: {audit.written}")
    return 0


def main() -> int:
    return asyncio.run(run(sys.argv[1:]))


if __name__ == "__main__":
    sys.exit(main())
