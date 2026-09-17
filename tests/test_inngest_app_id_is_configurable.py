"""No module may name the Inngest app id in its own source.

Inngest identifies an app by its id, and a sync writes that app's serve endpoint. With
the id a literal, staging and production are the same app: whichever deployed last owns
the endpoint, and the events the other publishes are delivered to the wrong service.
Here the app a deploy registers under is an environment variable, so
`tripod-backend-staging` can exist without repointing production.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.inngest_client import build_inngest_client

APP = Path(__file__).resolve().parent.parent / "app"

#: The one module allowed to name an app id. Matching on the file name alone would
#: exempt any `config.py` anywhere under `app/`, including one that does not exist yet.
CONFIG = (APP / "core" / "config.py").resolve()

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

#: An Inngest app id of this project's family. Only `CONFIG` above may name one.
_APP_ID = re.compile(r'"tripod-backend[\w.\-]*"')


def test_the_app_id_defaults_to_production_name() -> None:
    """Production is the default, so an unset variable deploys what it deploys today."""
    settings = Settings(database_url=TEST_DATABASE_URL)

    assert build_inngest_client(settings).app_id == "tripod-backend"


def test_the_app_id_comes_from_settings() -> None:
    settings = Settings(database_url=TEST_DATABASE_URL, inngest_app_id="tripod-backend-staging")

    assert build_inngest_client(settings).app_id == "tripod-backend-staging"


def test_the_env_var_sets_the_app_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """What the staging deploy does: set INNGEST_APP_ID on the Cloud Run service."""
    monkeypatch.setenv("INNGEST_APP_ID", "tripod-backend-staging")
    settings = Settings(database_url=TEST_DATABASE_URL)

    assert build_inngest_client(settings).app_id == "tripod-backend-staging"


def test_no_module_hardcodes_the_app_id() -> None:
    offenders = {
        str(path.relative_to(APP)): _APP_ID.findall(path.read_text())
        for path in APP.rglob("*.py")
        if path.resolve() != CONFIG and _APP_ID.search(path.read_text())
    }
    assert not offenders, (
        f"these modules pin the Inngest app id in source: {offenders}. "
        f"Read it from Settings instead, so a second service registers under its own "
        f"app rather than overwriting production's serve endpoint."
    )
