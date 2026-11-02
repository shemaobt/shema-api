"""The meaning map's collection is named by the deploy; the environment's name picks the log format.

Production defined no `ENV`, so it ran as `development` and has read and written
`meaning_map_test` since the service exists. Turning `ENV=production` on would have pointed
it at `meaning_map_prod`, which may be empty. The deploy now names the collection it already
uses, and `ENV` only switches the logs to JSON.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator

import pytest

from app.core.config import Settings
from app.core.logging import setup_logging
from tests.deploy_harness import deploy_env_vars

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"


def _settings(**values: str) -> Settings:
    return Settings(_env_file=None, database_url=TEST_DATABASE_URL, **values)


def test_a_named_collection_wins_over_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QDRANT_COLLECTION", raising=False)

    settings = _settings(env="production", qdrant_collection_name="meaning_map_test")

    assert settings.qdrant_collection == "meaning_map_test"


def test_the_env_var_names_the_collection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QDRANT_COLLECTION", "meaning_map_test")

    assert _settings(env="production").qdrant_collection == "meaning_map_test"


@pytest.mark.parametrize(
    ("env", "collection"),
    [("production", "meaning_map_prod"), ("development", "meaning_map_test")],
)
def test_an_unnamed_collection_is_derived_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, env: str, collection: str
) -> None:
    monkeypatch.delenv("QDRANT_COLLECTION", raising=False)

    assert _settings(env=env).qdrant_collection == collection


def test_the_production_deploy_names_the_collection_it_has_always_used() -> None:
    deployed = deploy_env_vars("deploy.yml")

    assert deployed["QDRANT_COLLECTION"] == "meaning_map_test"
    assert deployed["ENV"] == "production"


@pytest.fixture
def root_handlers() -> Iterator[None]:
    root = logging.getLogger()
    saved = root.handlers[:]
    yield
    root.handlers[:] = saved


def _log_line(capsys: pytest.CaptureFixture[str]) -> str:
    setup_logging()
    logging.getLogger("probe").info("hello")
    return capsys.readouterr().out.strip()


@pytest.mark.usefixtures("root_handlers")
def test_production_logs_are_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("ENV", "production")

    line = json.loads(_log_line(capsys))

    assert line["event"] == "hello"
    assert line["level"] == "info"
    assert line["logger"] == "probe"
    assert "timestamp" in line


@pytest.mark.usefixtures("root_handlers")
def test_logs_without_env_are_for_the_console(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("ENV", raising=False)

    line = _log_line(capsys)

    assert "hello" in line
    with pytest.raises(json.JSONDecodeError):
        json.loads(line)
