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


def test_a_pin_to_keep_that_is_not_a_whole_sha_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["sync_internalization_canon.py", "--sync", "--keep", OLDER, "--keep", "bbbbbbb"],
    )
    monkeypatch.setattr(
        canon,
        "sync",
        lambda pin=None, keep=(): pytest.fail(
            "sync() dropped the tree of a short sha it was told to keep"
        ),
    )

    with pytest.raises(SystemExit) as excinfo:
        canon.main()

    assert excinfo.value.code != 0


def test_a_pin_to_keep_without_sync_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["sync_internalization_canon.py", "--check", "--keep", OLDER])
    monkeypatch.setattr(canon, "check", lambda: pytest.fail("check() ran with an ignored --keep"))

    with pytest.raises(SystemExit) as excinfo:
        canon.main()

    assert excinfo.value.code != 0
