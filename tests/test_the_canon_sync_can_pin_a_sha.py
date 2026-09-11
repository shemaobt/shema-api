"""`--sync` always resolved `/commits/main` and wrote that sha, so a re-vendor could not be
reproduced at a chosen commit: any future sync brought everything upstream had pushed since,
whether or not the ticket wanted it (ENG-926 — on 10 September the ENG-787 agent had to diff
the vendor by hand to prove only P07 had moved). `--pin <sha>` fixes the sha instead of asking
upstream for its head; the current, un-pinned behaviour is kept as the fallback.

Never runs `sync()` against the real vendor: `_listing`/`_raw` are doubled here, and `VENDOR` /
`PIN_FILE` are redirected into `tmp_path`, so the pin this branch ships with (`7372ec0`, from
ENG-787) cannot move by running these tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import scripts.sync_internalization_canon as canon

PINNED_SHA = "cafef00dfacade00cafef00dfacade00cafef00d"
HEAD_SHA = "1eadbeef1eadbeef1eadbeef1eadbeef1eadbeef"


@pytest.fixture
def redirected_vendor(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    vendor = tmp_path / "vendor"
    monkeypatch.setattr(canon, "VENDOR", vendor)
    monkeypatch.setattr(canon, "PIN_FILE", vendor / "VENDOR_PIN")
    monkeypatch.setattr(canon, "_listing", lambda kind, sha: [])
    monkeypatch.setattr(canon, "_raw", lambda kind, sha, name: b"")
    return vendor


def test_sync_with_pin_never_asks_upstream_for_its_head(
    redirected_vendor: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _head_sha_must_not_be_called() -> str:
        raise AssertionError("--pin was given; sync() still resolved the upstream head")

    monkeypatch.setattr(canon, "_head_sha", _head_sha_must_not_be_called)

    canon.sync(pin=PINNED_SHA)

    assert canon.PIN_FILE.read_text().strip() == PINNED_SHA


def test_sync_without_pin_still_resolves_the_upstream_head(
    redirected_vendor: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(canon, "_head_sha", lambda: HEAD_SHA)

    canon.sync(pin=None)

    assert canon.PIN_FILE.read_text().strip() == HEAD_SHA
