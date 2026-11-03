from __future__ import annotations

import hashlib
import json

from tests.canon_harness import HER_CANON

RECORD = json.loads((HER_CANON / "PROVENANCE.json").read_text(encoding="utf-8"))


def test_the_record_names_her_canon_pin_and_her_manifest() -> None:
    assert RECORD["pin_commit"] == "5b5c8d2b3ae7632279c07017224f861ae369b0d7"
    assert RECORD["source"] == (
        "shemaobt/Tripod-Internalization at 18fa7c4, _spec/canon/VENDOR_MANIFEST.json"
    )


def test_every_file_of_her_canon_in_the_fixtures_hashes_to_what_her_manifest_records() -> None:
    held = {
        path.relative_to(HER_CANON).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(HER_CANON.glob("*/*.md"))
    }

    assert held == RECORD["files"]
