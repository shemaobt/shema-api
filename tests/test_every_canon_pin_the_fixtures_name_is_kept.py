"""ENG-1753 — every canon pin the test fixtures name is the deployed pin or a kept canon.

A fixture copied from her canon at a pin stands for sessions opened under that pin. If a sync
or a prune lost that pin's canon, the fixture would describe a canon the room can no longer
read, and nothing else in the suite would say so.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.core.canon_pin import pinned_commit
from app.services.internalization_room.canon import kept

FIXTURES = Path(__file__).parent / "fixtures"
HER_CANON_PIN = "5b5c8d2b3ae7632279c07017224f861ae369b0d7"


def _pins_the_fixtures_name() -> set[str]:
    return {
        json.loads(provenance.read_text())["pin_commit"]
        for provenance in FIXTURES.rglob("PROVENANCE.json")
    }


def _is_kept(pin: str) -> bool:
    record = kept.KEPT_DIR / pin / "vendor" / "VENDOR_PIN"
    return record.is_file() and pinned_commit(record.read_text()) == pin


def test_every_canon_pin_the_fixtures_name_is_the_deployed_pin_or_a_kept_canon() -> None:
    pins = _pins_the_fixtures_name()

    assert HER_CANON_PIN in pins, "the control: the fixture of her canon names its pin"
    assert [
        pin for pin in sorted(pins) if pin != kept.deployed_pin() and not _is_kept(pin)
    ] == [], "uma fixture descreve um canon que a sala não lê mais"
