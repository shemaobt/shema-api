"""The bucket's signer, replaced by one that writes every grant down.

A case about a link the room mints has to see what was asked of the signer — the key, the
minutes, the content type — and has to tell one grant from the next. The builder sets the
bucket the signer refuses to run without and puts the double where `takes` reaches for the
real one; the fixture that calls it stays in the module, for the reason `room_harness` gives.
"""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services.internalization_room import takes as takes_service


class Signer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, str | None]] = []

    async def __call__(
        self, bucket: str, key: str, *, expiry_minutes: int, response_content_type: str | None
    ) -> str:
        self.calls.append((key, expiry_minutes, response_content_type))
        return f"https://signed.example/{bucket}/{key}?grant={len(self.calls)}"


def the_bucket_signs(monkeypatch: pytest.MonkeyPatch) -> Signer:
    monkeypatch.setattr(get_settings(), "gcs_platform_bucket", "balde-de-teste", raising=False)
    signing = Signer()
    monkeypatch.setattr(takes_service, "generate_signed_download_url", signing)
    return signing
