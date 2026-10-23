"""`--pin` went through to `?ref=` untouched, and that query param takes any git ref, not just
a sha (`gh api "repos/shemaobt/shema-api/contents/scripts?ref=main"` returns the listing exactly
as a sha does — found in review, ENG-926). `--sync --pin main` would write the literal string
`main` into `VENDOR_PIN`, and `check()` would re-resolve that ref live on every run: the module's
own first line, "Vendor ... at a pinned commit", would stop holding, and the canon job would
redden on the next upstream push rather than staying still until someone re-pins.
"""

from __future__ import annotations

import pytest

import scripts.sync_internalization_canon as canon

SHA = "cafef00dfacade00cafef00dfacade00cafef00d"


def test_pin_that_is_not_a_sha_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["sync_internalization_canon.py", "--sync", "--pin", "main"])
    monkeypatch.setattr(
        canon, "sync", lambda pin=None: pytest.fail("sync() ran with a non-sha pin")
    )

    with pytest.raises(SystemExit) as excinfo:
        canon.main()

    assert excinfo.value.code != 0


def test_a_real_sha_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str | None] = []
    monkeypatch.setattr("sys.argv", ["sync_internalization_canon.py", "--sync", "--pin", SHA])
    monkeypatch.setattr(canon, "sync", lambda pin=None: seen.append(pin) or 0)

    canon.main()

    assert seen == [SHA]
