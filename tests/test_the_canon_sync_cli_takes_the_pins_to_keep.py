"""The sync drops every kept tree whose pin it is not told to keep (ENG-1511), and the command
line is where it is told: `--keep <sha>`, once per pin.
"""

from __future__ import annotations

import pytest

import scripts.sync_internalization_canon as canon

OLDER = "a" * 40
OLDEST = "b" * 40


def test_each_pin_given_with_keep_reaches_the_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        "sys.argv", ["sync_internalization_canon.py", "--sync", "--keep", OLDER, "--keep", OLDEST]
    )
    monkeypatch.setattr(canon, "sync", lambda pin=None, keep=(): seen.append(keep) or 0)

    canon.main()

    assert seen == [
        ("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
    ]
