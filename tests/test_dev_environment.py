"""The dev and test environments run against the local Postgres container.

Nothing here touches the app: it pins the contract of docker-compose.yml, which is
what actually decides where a developer's data lives.
"""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
COMPOSE = ROOT / "docker-compose.yml"
NEON_LOCAL_SECRET = "tripod_backend_neon_database_url_local"
DUMP_DIR = ".local-dump"
DANGEROUS_OPERATIONS = ("gcloud storage", "pg_restore", "DROP DATABASE")


@pytest.fixture(scope="module")
def compose() -> dict:
    return yaml.safe_load(COMPOSE.read_text())


def _seconds(duration: str | int) -> float:
    """Compose durations (`5s`, `10m`) as seconds."""
    text = str(duration).strip()
    units = {"s": 1, "m": 60, "h": 3600}
    if text[-1] in units:
        return float(text[:-1]) * units[text[-1]]
    return float(text)


def _pilot_statements(sql: str) -> list[str]:
    """The INSERT statements of the pilot overlay, with comments removed first."""
    code = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
    return [block for block in code.split(";") if "INSERT INTO" in block]


def _tables_touched(statements: list[str]) -> set[str]:
    return {
        line.split()[2]
        for block in statements
        for line in block.splitlines()
        if line.lstrip().startswith("INSERT INTO")
    }


def _shell_lines(script: str) -> list[str]:
    """The script's lines with comments blanked out, original indices kept."""
    return ["" if line.lstrip().startswith("#") else line for line in script.splitlines()]


def test_local_database_service_exists(compose: dict) -> None:
    db = compose["services"]["db"]

    assert db["image"].startswith("postgres:")
    assert "db_data:/var/lib/postgresql/data" in db["volumes"]
    assert "healthcheck" in db


def test_the_healthcheck_waits_for_the_seed_to_finish(compose: dict) -> None:
    probe = " ".join(compose["services"]["db"]["healthcheck"]["test"])

    assert "pg_isready" in probe
    assert "-h 127.0.0.1" in probe


def test_the_restore_is_not_capped_by_the_retry_budget(compose: dict) -> None:
    health = compose["services"]["db"]["healthcheck"]

    assert "start_period" in health
    budget = _seconds(health["start_period"])
    assert budget > _seconds(health["interval"]) * health["retries"]


def test_local_postgres_major_matches_production(compose: dict) -> None:
    db_major = compose["services"]["db"]["image"].split(":")[1].split(".")[0]
    ci_major = (
        yaml.safe_load((ROOT / ".github/workflows/migrations.yml").read_text())["jobs"][
            "migrations"
        ]["services"]["postgres"]["image"]
        .split(":")[1]
        .split(".")[0]
    )

    assert db_major == "17"
    assert ci_major == "17"


def test_local_database_is_not_reachable_from_outside_the_machine(compose: dict) -> None:
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


def test_no_service_reads_the_neon_dev_secret() -> None:
    assert NEON_LOCAL_SECRET not in COMPOSE.read_text()


def test_secrets_container_still_provides_the_remaining_secrets(compose: dict) -> None:
    command = "".join(compose["services"]["gcp-secrets"]["command"])

    assert "tripod_backend_jwt_secret" in command
    assert "DATABASE_URL" not in command


def test_a_fresh_database_seeds_itself_from_the_local_dump(compose: dict) -> None:
    db = compose["services"]["db"]

    assert "./scripts/seed_local_db.sh:/docker-entrypoint-initdb.d/10-seed.sh:ro" in db["volumes"]
    assert f"./{DUMP_DIR}:/seed:ro" in db["volumes"]


def test_the_dump_is_fetched_without_a_manual_step(compose: dict) -> None:
    seed = compose["services"]["db-seed"]

    assert seed["restart"] == "no"
    assert f"./{DUMP_DIR}:/seed" in seed["volumes"]
    assert compose["services"]["db"]["depends_on"]["db-seed"]["condition"] == (
        "service_completed_successfully"
    )


def test_seeding_can_be_turned_off(compose: dict) -> None:
    for service in ("db", "db-seed"):
        assert (
            "${SEED_FROM_DUMP:-1}" in compose["services"][service]["environment"]["SEED_FROM_DUMP"]
        )
    for name in ("seed_local_db.sh", "fetch_local_dump.sh"):
        assert 'SEED_FROM_DUMP" = "0"' in (ROOT / "scripts" / name).read_text()


def test_the_sound_necklace_pilot_is_replayed_on_top_of_the_dump(compose: dict) -> None:
    db = compose["services"]["db"]
    overlay = ROOT / "scripts" / "seed_sn_pilot.sql"

    assert "./scripts/seed_sn_pilot.sql:/pilot/sn-pilot.sql:ro" in db["volumes"]
    assert overlay.read_text().count("INSERT INTO sn_audio_refs") == 49
    assert "INSERT INTO projects" in overlay.read_text()
    assert "INSERT INTO languages" in overlay.read_text()


def test_the_pilot_overlay_is_replayable() -> None:
    guarded = _pilot_statements((ROOT / "scripts" / "seed_sn_pilot.sql").read_text())

    assert guarded
    for block in guarded:
        assert "ON CONFLICT" in block or "NOT EXISTS" in block, block


def test_the_guard_check_survives_rewording_the_header() -> None:
    sql = (ROOT / "scripts" / "seed_sn_pilot.sql").read_text()
    reworded = "\n".join(
        line.replace(";", ",") if line.lstrip().startswith("--") else line
        for line in sql.splitlines()
    )

    assert _tables_touched(_pilot_statements(reworded)) == _tables_touched(_pilot_statements(sql))
    assert "languages" in _tables_touched(_pilot_statements(reworded))


def test_every_insert_in_the_pilot_is_checked() -> None:
    sql = (ROOT / "scripts" / "seed_sn_pilot.sql").read_text()

    written = sum(1 for line in sql.splitlines() if line.lstrip().startswith("INSERT INTO"))
    checked = sum(
        1
        for block in _pilot_statements(sql)
        for line in block.splitlines()
        if line.lstrip().startswith("INSERT INTO")
    )

    assert checked == written


def test_the_pilot_asserts_no_consent() -> None:
    refs = [
        line
        for line in (ROOT / "scripts" / "seed_sn_pilot.sql").read_text().splitlines()
        if line.startswith("INSERT INTO sn_audio_refs")
    ]

    assert refs
    for line in refs:
        assert ", false, " in line, line


def test_the_pilot_names_no_individual() -> None:
    overlay = (ROOT / "scripts" / "seed_sn_pilot.sql").read_text()

    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", overlay)
    assert "is_platform_admin" in overlay


def test_the_restore_script_replays_the_pilot_too() -> None:
    script = (ROOT / "scripts" / "restore_local_db.sh").read_text()

    assert "seed_sn_pilot.sql" in script


def test_the_local_database_requires_a_password(compose: dict) -> None:
    db = compose["services"]["db"]

    assert "POSTGRES_HOST_AUTH_METHOD" not in db["environment"]
    assert db["environment"]["POSTGRES_PASSWORD"]
    for service in ("backend", "worker"):
        url = compose["services"][service]["environment"]["DATABASE_URL"]
        assert "postgresql://postgres:" in url


def test_a_failed_download_never_blocks_the_stack() -> None:
    script = (ROOT / "scripts" / "fetch_local_dump.sh").read_text()

    assert "set -e" not in script
    assert script.count("exit 0") >= 3


def test_seeding_never_blocks_the_stack() -> None:
    script = (ROOT / "scripts" / "seed_local_db.sh").read_text()

    assert 'if [ ! -f "$DUMP" ]; then' in script
    assert script.count("exit 0") >= 2
    assert "PILOT=/pilot/sn-pilot.sql" in script
    assert re.search(r"if ! psql", script)


def test_a_failing_restore_never_blocks_the_stack() -> None:
    for name in ("seed_local_db.sh", "restore_local_db.sh"):
        script = (ROOT / "scripts" / name).read_text()

        assert re.search(r"if ! .*pg_restore", script), name


def test_the_cleanup_instruction_is_not_undone_by_the_next_up() -> None:
    readme = (ROOT / "README.md").read_text()
    warning = readme[readme.index("**The dump is not anonymized.**") :][:1200]

    assert "down -v" in warning
    assert f"rm {DUMP_DIR}/latest.dump" in warning
    assert "SEED_FROM_DUMP=0" in warning


def test_the_local_dump_stays_out_of_git() -> None:
    ignored = (ROOT / ".gitignore").read_text()

    assert f"{DUMP_DIR}/*" in ignored
    assert f"!{DUMP_DIR}/.gitkeep" in ignored


def test_signing_key_never_reaches_the_image() -> None:
    ignored = (ROOT / ".dockerignore").read_text().split()

    assert "gcs-signing-key.json" in ignored
    assert ".env" in ignored


def test_the_local_dump_never_reaches_the_image() -> None:
    ignored = (ROOT / ".dockerignore").read_text().split()

    assert "**/*.dump" in ignored


def test_the_half_downloaded_dump_never_reaches_the_image() -> None:
    ignored = (ROOT / ".dockerignore").read_text().split()

    assert f"{DUMP_DIR}/" in ignored


def test_the_restore_aborts_before_it_can_touch_production_or_the_database() -> None:
    lines = _shell_lines((ROOT / "scripts" / "restore_local_db.sh").read_text())

    gates = [i for i, line in enumerate(lines) if "aborted" in line and "exit 1" in line]
    dangerous = [
        i for i, line in enumerate(lines) if any(op in line for op in DANGEROUS_OPERATIONS)
    ]

    assert len(gates) == 1
    assert dangerous
    for index in dangerous:
        assert gates[0] < index, lines[index]
