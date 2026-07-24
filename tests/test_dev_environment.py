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
DUMP_DIR = ".local-dump"


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


def test_a_fresh_database_seeds_itself_from_the_local_dump(compose: dict) -> None:
    """Postgres runs /docker-entrypoint-initdb.d only when it creates the cluster, so
    the restore happens on a from-scratch database and never on an existing one. The
    dump comes off the host directory restore_local_db.sh writes to, which needs no
    sidecar and no network."""
    db = compose["services"]["db"]

    assert "./scripts/seed_local_db.sh:/docker-entrypoint-initdb.d/10-seed.sh:ro" in db["volumes"]
    assert f"./{DUMP_DIR}:/seed:ro" in db["volumes"]
    assert "db-seed" not in compose["services"]


def test_seeding_can_be_turned_off(compose: dict) -> None:
    assert "${SEED_FROM_DUMP:-1}" in compose["services"]["db"]["environment"]["SEED_FROM_DUMP"]
    assert 'SEED_FROM_DUMP" = "0"' in (ROOT / "scripts" / "seed_local_db.sh").read_text()


def test_seeding_never_blocks_the_stack() -> None:
    """No dump on the machine still has to give a working stack: the seed script exits
    clean and the backend migrates an empty database."""
    script = (ROOT / "scripts" / "seed_local_db.sh").read_text()

    assert 'if [ ! -f "$DUMP" ]; then' in script
    assert script.count("exit 0") >= 2


def test_the_local_dump_stays_out_of_git() -> None:
    """It is production data sitting in the working tree."""
    ignored = (ROOT / ".gitignore").read_text()

    assert f"{DUMP_DIR}/*" in ignored
    assert f"!{DUMP_DIR}/.gitkeep" in ignored


def test_signing_key_never_reaches_the_image() -> None:
    """Dockerfile.dev ends in `COPY . .`, so a service account key in the working
    directory would be baked into every layer. Compose mounts it at runtime instead."""
    ignored = (ROOT / ".dockerignore").read_text().split()

    assert "gcs-signing-key.json" in ignored
    assert ".env" in ignored


def test_restore_refuses_without_confirmation() -> None:
    """It puts real user data on the machine. Declining at the prompt has to stop it
    before it reaches gcloud, so a stray run cannot copy production anywhere."""
    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "restore_local_db.sh")],
        input="no\n",
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode != 0
    assert "aborted" in result.stdout + result.stderr
