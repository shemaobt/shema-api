import logging

import pytest

from app.core.config import get_settings
from app.main import create_app


def _warnings_naming_the_key(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [
        record
        for record in caplog.records
        if record.levelno == logging.WARNING
        and "INTERNALIZATION_ROOM_CLIP_SIGNING_KEY" in record.getMessage()
    ]


def test_a_server_booted_without_the_clip_signing_key_says_so_once(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(get_settings(), "internalization_room_clip_signing_key", "")

    with caplog.at_level(logging.WARNING):
        create_app()

    assert len(_warnings_naming_the_key(caplog)) == 1, (
        "o servidor subia entregando handles sem assinatura sem dizer a ninguém"
    )


def test_a_server_booted_with_the_clip_signing_key_says_nothing_about_it(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(get_settings(), "internalization_room_clip_signing_key", "chave-de-teste")

    with caplog.at_level(logging.WARNING):
        create_app()

    assert _warnings_naming_the_key(caplog) == []
