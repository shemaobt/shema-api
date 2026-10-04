"""`--check --pin <sha>` parsed clean and silently did nothing with the sha: `check()` takes
no argument and reads whatever is already in `VENDOR_PIN`, so the drift check ran against a
different commit than the one on the command line, with nobody told (found in review, ENG-926).
"""

from __future__ import annotations

import pytest

import scripts.sync_internalization_canon as canon

SOME_SHA = "cafef00dfacade00cafef00dfacade00cafef00d"


def test_pin_without_sync_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """`check` is doubled to fail the test loudly if the guard lets the call through."""
    monkeypatch.setattr("sys.argv", ["sync_internalization_canon.py", "--check", "--pin", SOME_SHA])
    monkeypatch.setattr(canon, "check", lambda: pytest.fail("check() ran with an ignored --pin"))

    with pytest.raises(SystemExit) as excinfo:
        canon.main()

    assert excinfo.value.code != 0
