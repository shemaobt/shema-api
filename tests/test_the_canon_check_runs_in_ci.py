"""`--check` costs two API calls plus one raw fetch per vendored file, and nothing invoked it.

`grep -rn canon .github/` found nothing (ENG-926): a vendored map edited by hand — or one that
simply drifted from `MarciaSuzuki/tripod_compiler` — passed CI green, because the only thing
that would have noticed was never run.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LINT = (REPO_ROOT / ".github/workflows/lint.yml").read_text(encoding="utf-8")


def test_the_drift_check_runs_on_every_pull_request() -> None:
    assert "uv run python scripts/sync_internalization_canon.py --check" in LINT, (
        "nothing in CI notices the vendored canon drifting from its pin"
    )
