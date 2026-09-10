"""The runner's own `GITHUB_TOKEN` raises the request past the shared anonymous ceiling.

`api.github.com/rate_limit` answers unauthenticated at 60 requests/hour, per egress IP —
verified against the live API on 2026-09-10, and shared across every Actions runner's
outbound address, not per-repository. A `canon` job running unauthenticated would fail on
crowded days for a reason that has nothing to do with the vendored canon.
"""

from __future__ import annotations

import urllib.request

import pytest

from scripts.sync_internalization_canon import _get


@pytest.fixture
def captured_request(monkeypatch: pytest.MonkeyPatch) -> list[urllib.request.Request]:
    seen: list[urllib.request.Request] = []

    class _FakeResponse:
        def read(self) -> bytes:
            return b""

        def __enter__(self) -> _FakeResponse:
            return self

        def __exit__(self, *exc_info: object) -> None:
            return None

    def fake_urlopen(request: urllib.request.Request, timeout: int = 30) -> _FakeResponse:
        seen.append(request)
        return _FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return seen


def test_the_request_carries_the_runner_token_when_it_is_set(
    captured_request: list[urllib.request.Request], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "r2d2-token")

    _get("https://api.github.com/repos/MarciaSuzuki/tripod_compiler/commits/main")

    assert captured_request[0].get_header("Authorization") == "token r2d2-token"


def test_the_request_carries_no_authorization_header_without_a_token(
    captured_request: list[urllib.request.Request], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    _get("https://api.github.com/repos/MarciaSuzuki/tripod_compiler/commits/main")

    assert captured_request[0].get_header("Authorization") is None
