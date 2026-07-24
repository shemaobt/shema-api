"""The dev and test environments run against the local Postgres container.

Nothing here touches the app: it pins the contract of docker-compose.yml, which is
what actually decides where a developer's data lives.
"""

import subprocess
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parent.parent
COMPOSE = ROOT / "docker-compose.yml"
NEON_LOCAL_SECRET = "tripod_backend_neon_database_url_local"


@pytest.fixture(scope="module")
def compose() -> dict:
    return yaml.safe_load(COMPOSE.read_text())


def test_local_database_service_exists(compose: dict) -> None:
    db = compose["services"]["db"]

    assert db["image"].startswith("postgres:")
    assert "db_data:/var/lib/postgresql/data" in db["volumes"]
    assert "healthcheck" in db


def test_local_database_is_not_reachable_from_outside_the_machine(compose: dict) -> None:
    """A production dump gets restored here, so the port stays on the loopback."""
    for mapping in compose["services"]["db"]["ports"]:
        assert str(mapping).startswith("127.0.0.1:")


@pytest.mark.parametrize("service", ["backend", "worker"])
def test_services_point_at_the_local_database(compose: dict, service: str) -> None:
    url = compose["services"][service]["environment"]["DATABASE_URL"]

    assert "@db:5432/" in url
    assert "neon.tech" not in url


@pytest.mark.parametrize("service", ["backend", "worker"])
def test_services_wait_for_the_database(compose: dict, service: str) -> None:
    assert compose["services"][service]["depends_on"]["db"]["condition"] == "service_healthy"


def test_no_service_reads_the_neon_dev_secret(compose: dict) -> None:
    """Retiring the shared Neon dev database is the point of the local container."""
    assert NEON_LOCAL_SECRET not in COMPOSE.read_text()


def test_secrets_container_still_provides_the_remaining_secrets(compose: dict) -> None:
    """Only the database moved off Secret Manager; API keys still come from there."""
    command = "".join(compose["services"]["gcp-secrets"]["command"])

    assert "tripod_backend_jwt_secret" in command
    assert "DATABASE_URL" not in command


def test_signing_key_never_reaches_the_image() -> None:
    """Dockerfile.dev ends in `COPY . .`, so a service account key in the working
    directory would be baked into every layer. Compose mounts it at runtime instead."""
    ignored = (ROOT / ".dockerignore").read_text().split()

    assert "gcs-signing-key.json" in ignored
    assert ".env" in ignored


@pytest.mark.parametrize("script", ["dump_prod_db.sh", "restore_local_db.sh"])
def test_production_data_scripts_refuse_without_confirmation(script: str) -> None:
    """Both move real user data. Declining at the prompt has to stop them before
    they reach gcloud, so a stray run cannot copy production anywhere."""
    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / script)],
        input="no\n",
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode != 0
    assert "aborted" in result.stdout + result.stderr
