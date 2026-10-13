"""Her `buildCoverageElements` (src/ingest/coverage.ts, app 18fa7c4), run by node over the
canon this repository serves, beside our spine for every passage the room opens.

Her ingest is vendored read-only at the freeze, under `docs/doctrine/vendor/ingest/`, and
`sync_doctrine.py --check` holds its bytes to the pin. Node 24 runs her TypeScript as it is.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from app.services.internalization_room.canon.book_material import unwalkable
from app.services.internalization_room.canon.elements import elements_for
from app.services.internalization_room.canon.parse_map import VENDOR, load_book

HER_SPINE = Path(__file__).parent / "her_spine.mjs"

#: The two kinds she names otherwise (`src/ingest/types.ts`); the other nine read the same.
HER_KIND = {"absence": "significant_absence", "preserved": "preserved_element"}


def _served() -> list[str]:
    return [
        meaning_map.pericope_num
        for meaning_map in load_book("Ruth")
        if unwalkable(meaning_map) is None
    ]


def _hers(pericopes: list[str]) -> dict[str, list[tuple[str, str]]]:
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


def test_every_served_passage_strings_her_beads_in_her_order_under_her_ids() -> None:
    served = _served()
    hers = _hers(served)

    ours = {
        pericope: [
            (element.key, HER_KIND.get(element.kind.value, element.kind.value))
            for element in elements_for(pericope)
        ]
        for pericope in served
    }

    assert served
    assert ours == hers, (
        "as contas saíam da prosa do mapa, com chaves nossas, e o colar de cada passagem "
        "não era o dela"
    )
