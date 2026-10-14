"""Her `buildCoverageElements` (src/ingest/coverage.ts, app 18fa7c4), run by node.

Her ingest is vendored read-only at the freeze, under `docs/doctrine/vendor/ingest/`, and
`sync_doctrine.py --check` holds its bytes to the pin. Node runs her TypeScript as it is, so
what a case compares against is her answer and not a second reading of it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from app.services.internalization_room.canon.parse_map import VENDOR

HER_SPINE = Path(__file__).parent / "her_spine.mjs"


def her_spine(pericopes: list[str]) -> dict[str, list[tuple[str, str]]]:
    node = shutil.which("node")
    assert node is not None, "sem node o colar dela não roda, e nada mais o compara com o nosso"
    ran = subprocess.run(
        [node, str(HER_SPINE), str(VENDOR), *pericopes],
        capture_output=True,
        text=True,
        check=True,
    )
    return {
        pericope: [(element_id, kind) for element_id, kind in spine]
        for pericope, spine in json.loads(ran.stdout).items()
    }
