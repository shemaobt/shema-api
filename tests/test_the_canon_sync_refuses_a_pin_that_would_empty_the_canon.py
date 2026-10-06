"""`--sync` deleted every vendored file the listing no longer had, so a pin with no consumable
passage in it, or an upstream that answered with an empty listing, left the room with no canon at
all and a `VENDOR_PIN` naming a commit that held nothing it could use (ENG-1201).

Never runs against the real vendor: the compiler is `tests/canon_sync_harness.Compiler`, answered
through `_get`, and `VENDOR`/`PIN_FILE` are redirected into `tmp_path`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import scripts.sync_internalization_canon as canon
from tests.canon_sync_harness import SHA, Compiler, point_the_sync_at, what_is_vendored

BEFORE_PIN = "cafef00dfacade00cafef00dfacade00cafef00d\n"


@pytest.fixture
def a_vendor_holding_a_passage_and_a_compiler_with_no_whole_passage(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Path:
    compiler = Compiler()
    compiler.book("ruth")
    compiler.passage("P01-Ruth-1-1-5", log=False)
    vendor = point_the_sync_at(monkeypatch, canon, compiler, tmp_path)
    (vendor / "meaning-map").mkdir(parents=True)
    (vendor / "meaning-map" / "P01-Ruth-1-1-5.md").write_bytes(b"the canon as it stood")
    (vendor / "VENDOR_PIN").write_text(BEFORE_PIN)
    return vendor


def test_a_pin_that_leaves_no_consumable_passage_refuses_and_the_canon_stays_as_it_was(
    a_vendor_holding_a_passage_and_a_compiler_with_no_whole_passage: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    vendor = a_vendor_holding_a_passage_and_a_compiler_with_no_whole_passage

    exit_code = canon.sync(pin=SHA)

    assert exit_code == 1
    assert "nothing consumable at pin" in capsys.readouterr().err
    assert what_is_vendored(vendor) == {"meaning-map/P01-Ruth-1-1-5.md": b"the canon as it stood"}
    assert (vendor / "VENDOR_PIN").read_text() == BEFORE_PIN
