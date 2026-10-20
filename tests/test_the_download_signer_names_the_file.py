"""ENG-1283 — storage is asked to save a signed download under a name, for as long as asked.

The one place the disposition can be seen leaving the API is the call to storage, so the client
is the house's stand-in at the third-party boundary and nothing else is replaced.
"""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from app.services.oral_collector.gcs_utils import generate_signed_download_url

GCS_CLIENT = "app.services.oral_collector.gcs_utils.storage.Client"
AMBIENT_CREDENTIALS = "app.services.oral_collector.gcs_utils.google.auth.default"


class _SigningBlob:
    def __init__(self, signed: list[dict[str, Any]]) -> None:
        self._signed = signed

    def generate_signed_url(self, **asked: Any) -> str:
        self._signed.append(asked)
        return "https://storage.test/assinado"


class _SigningBucket:
    def __init__(self, signed: list[dict[str, Any]]) -> None:
        self._signed = signed

    def blob(self, _name: str) -> _SigningBlob:
        return _SigningBlob(self._signed)


class _SigningClient:
    def __init__(self) -> None:
        self.signed: list[dict[str, Any]] = []

    def bucket(self, _name: str) -> _SigningBucket:
        return _SigningBucket(self.signed)


def _service_account(**_scopes: Any) -> tuple[SimpleNamespace, None]:
    return SimpleNamespace(valid=True, service_account_email="sa@example.com", token="t"), None


async def _signed_by_storage(**asked: Any) -> dict[str, Any]:
    client = _SigningClient()
    with patch(GCS_CLIENT, return_value=client), patch(AMBIENT_CREDENTIALS, _service_account):
        await generate_signed_download_url("balde", "chave/tomada.wav", **asked)
    assert len(client.signed) == 1
    return client.signed[0]


async def test_storage_is_asked_to_save_the_file_under_its_name_for_an_hour() -> None:
    disposition = 'attachment; filename="internalize-terena-p03-v1-S1.wav"'

    asked = await _signed_by_storage(expiry_minutes=60, response_disposition=disposition)

    assert asked["expiration"] == timedelta(hours=1)
    assert asked["response_disposition"] == disposition


async def test_a_link_signed_without_a_name_asks_storage_for_none() -> None:
    asked = await _signed_by_storage(expiry_minutes=15, response_content_type="audio/wav")

    assert asked["response_disposition"] is None
    assert asked["expiration"] == timedelta(minutes=15)
