"""The dev and test environments run against the local Postgres container.

Nothing here touches the app: it pins the contract of docker-compose.yml, which is
what actually decides where a developer's data lives.
"""

import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
COMPOSE = ROOT / "docker-compose.yml"
NEON_LOCAL_SECRET = "tripod_backend_neon_database_url_local"
DUMP_DIR = ".local-dump"


@pytest.fixture(scope="module")
def compose() -> dict:
    return yaml.safe_load(COMPOSE.read_text())


def _pilot_statements(sql: str) -> list[str]:
    """The INSERT statements of the pilot overlay, with comments removed first.

    Splitting raw text on `;` mixes prose into the statements: the header is a paragraph
    of English whose punctuation decides where the first block ends. Stripping the `--`
    lines makes the split depend on the SQL alone.
    """
    code = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
    return [block for block in code.split(";") if "INSERT INTO" in block]


def _tables_touched(statements: list[str]) -> set[str]:
    return {
        line.split()[2]
        for block in statements
        for line in block.splitlines()
        if line.lstrip().startswith("INSERT INTO")
    }


def test_local_database_service_exists(compose: dict) -> None:
    db = compose["services"]["db"]

    assert db["image"].startswith("postgres:")
    assert "db_data:/var/lib/postgresql/data" in db["volumes"]
    assert "healthcheck" in db


def test_the_healthcheck_waits_for_the_seed_to_finish(compose: dict) -> None:
    """The postgres entrypoint runs /docker-entrypoint-initdb.d against a temporary
    server started with `listen_addresses=''` — reachable over the unix socket and not
    over TCP. A socket probe therefore reports healthy while the restore is still
    running, `backend` starts on `service_healthy`, and its `alembic upgrade head` meets
    a refused connection on 5432. On an empty database that window is a blink; on a
    production dump it is minutes.

    Probing TCP is what makes the healthcheck mean what `depends_on` reads it to mean,
    because 5432 only starts listening once the real server replaces the temporary one.
    """
    probe = " ".join(compose["services"]["db"]["healthcheck"]["test"])

    assert "pg_isready" in probe
    assert "-h 127.0.0.1" in probe


def test_local_postgres_major_matches_production(compose: dict) -> None:
    """Production runs Postgres 17. A lower local major cannot restore a production
    dump — pg_dump refuses a newer server outright — so the two have to track."""
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
    the restore happens on a from-scratch database and never on an existing one."""
    db = compose["services"]["db"]

    assert "./scripts/seed_local_db.sh:/docker-entrypoint-initdb.d/10-seed.sh:ro" in db["volumes"]
    assert f"./{DUMP_DIR}:/seed:ro" in db["volumes"]


def test_the_dump_is_fetched_without_a_manual_step(compose: dict) -> None:
    """`docker compose up` on a machine with no dump has to end up with one: db-seed
    downloads it into the directory db mounts, and db waits for that to finish before it
    initialises the cluster. Same one-shot shape as bhsa-fetcher."""
    seed = compose["services"]["db-seed"]

    assert seed["restart"] == "no"
    assert f"./{DUMP_DIR}:/seed" in seed["volumes"]
    assert compose["services"]["db"]["depends_on"]["db-seed"]["condition"] == (
        "service_completed_successfully"
    )


def test_seeding_can_be_turned_off(compose: dict) -> None:
    """One switch covers both halves: db-seed skips the download, and the seed script
    skips a dump an earlier run already left in the directory."""
    for service in ("db", "db-seed"):
        assert (
            "${SEED_FROM_DUMP:-1}" in compose["services"][service]["environment"]["SEED_FROM_DUMP"]
        )
    for name in ("seed_local_db.sh", "fetch_local_dump.sh"):
        assert 'SEED_FROM_DUMP" = "0"' in (ROOT / "scripts" / name).read_text()


def test_the_sound_necklace_pilot_is_replayed_on_top_of_the_dump(compose: dict) -> None:
    """Production carries the 49 Ruth acousteme artifacts but none of the sn_audio_refs
    that bind them to a project, because those rows were only ever created in the dev
    database. No production dump will ever carry them, so they are replayed from a file
    — along with the pilot project and its language, which production also lacks."""
    db = compose["services"]["db"]
    overlay = ROOT / "scripts" / "seed_sn_pilot.sql"

    assert "./scripts/seed_sn_pilot.sql:/pilot/sn-pilot.sql:ro" in db["volumes"]
    assert overlay.read_text().count("INSERT INTO sn_audio_refs") == 49
    assert "INSERT INTO projects" in overlay.read_text()
    assert "INSERT INTO languages" in overlay.read_text()


def test_the_pilot_overlay_is_replayable(compose: dict) -> None:
    """It runs on every from-scratch database, and a developer may also apply it by hand
    against one that already has some of it. Each statement carries its own guard: a
    file-wide search would keep passing after every guard but one had been dropped."""
    guarded = _pilot_statements((ROOT / "scripts" / "seed_sn_pilot.sql").read_text())

    assert guarded
    for block in guarded:
        assert "ON CONFLICT" in block or "NOT EXISTS" in block, block


def test_the_guard_check_survives_rewording_the_header(compose: dict) -> None:
    """The split is on `;` and the header is prose that happens to contain two of them.
    Take those away — an ordinary reword, no SQL touched — and the block holding
    `INSERT INTO languages` begins with `--`. A filter that skipped blocks by their
    leading `--` would drop the statement it most wants to check and still report green,
    so the comments come out before the split rather than being reasoned around."""
    sql = (ROOT / "scripts" / "seed_sn_pilot.sql").read_text()
    reworded = "\n".join(
        line.replace(";", ",") if line.lstrip().startswith("--") else line
        for line in sql.splitlines()
    )

    assert _tables_touched(_pilot_statements(reworded)) == _tables_touched(_pilot_statements(sql))
    assert "languages" in _tables_touched(_pilot_statements(reworded))


def test_every_insert_in_the_pilot_is_checked(compose: dict) -> None:
    """The guard assertion is only worth as much as its coverage: a statement the split
    loses is a statement that passes by never being looked at."""
    sql = (ROOT / "scripts" / "seed_sn_pilot.sql").read_text()

    written = sum(1 for line in sql.splitlines() if line.lstrip().startswith("INSERT INTO"))
    checked = sum(
        1
        for block in _pilot_statements(sql)
        for line in block.splitlines()
        if line.lstrip().startswith("INSERT INTO")
    )

    assert checked == written


def test_the_pilot_asserts_no_consent(compose: dict) -> None:
    """``consent_present`` is the §12/O6 collection consent, which a human asserts by
    hand through scripts/seed_sn_audio_refs.py --consent. Nobody recorded it for the
    pilot rows, so the overlay must not put an agreement into every developer's database
    that never happened. The column is NOT NULL with no server default, so the honest
    value has to be written out rather than omitted."""
    refs = [
        line
        for line in (ROOT / "scripts" / "seed_sn_pilot.sql").read_text().splitlines()
        if line.startswith("INSERT INTO sn_audio_refs")
    ]

    assert refs
    for line in refs:
        assert ", false, " in line, line


def test_the_pilot_names_no_individual(compose: dict) -> None:
    """Every developer runs this file. A grant keyed on one person's address gives
    everyone else a project they cannot open, and puts a real address in the repository."""
    overlay = (ROOT / "scripts" / "seed_sn_pilot.sql").read_text()

    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", overlay)
    assert "is_platform_admin" in overlay


def test_the_restore_script_replays_the_pilot_too() -> None:
    """restore_local_db.sh drops and recreates the database, so the initdb hook that
    normally applies the overlay never runs on that path. Without this the documented
    promise — the pilot is replayed right after the restore — holds on one route only,
    and the other leaves the Sound Necklace with no audios."""
    script = (ROOT / "scripts" / "restore_local_db.sh").read_text()

    assert "seed_sn_pilot.sql" in script


def test_the_local_database_requires_a_password(compose: dict) -> None:
    """The dump lands on the machine without anyone typing anything now, so an open
    `trust` on a published port would hand production data to any local account."""
    db = compose["services"]["db"]

    assert "POSTGRES_HOST_AUTH_METHOD" not in db["environment"]
    assert db["environment"]["POSTGRES_PASSWORD"]
    for service in ("backend", "worker"):
        url = compose["services"][service]["environment"]["DATABASE_URL"]
        assert "postgresql://postgres:" in url


def test_a_failed_download_never_blocks_the_stack() -> None:
    """db-seed gates db through service_completed_successfully, so a nonzero exit takes
    the whole stack down. No gcloud credentials and an unreachable bucket are ordinary
    states on a fresh machine — they have to degrade to an empty database."""
    script = (ROOT / "scripts" / "fetch_local_dump.sh").read_text()

    assert "set -e" not in script
    assert script.count("exit 0") >= 3


def test_seeding_never_blocks_the_stack() -> None:
    """No dump on the machine still has to give a working stack: the seed script exits
    clean and the backend migrates an empty database."""
    script = (ROOT / "scripts" / "seed_local_db.sh").read_text()

    assert 'if [ ! -f "$DUMP" ]; then' in script
    assert script.count("exit 0") >= 2
    assert "PILOT=/pilot/sn-pilot.sql" in script
    assert re.search(r"if ! psql", script)


def test_a_failing_restore_never_blocks_the_stack() -> None:
    """pg_restore exits nonzero whenever it ignores an error, and a production dump
    carries plenty of those — extensions and comments owned by Neon roles. Both scripts
    run under `set -e`, where that would abort the restore: initdb would fail and the
    database never go healthy, so backend and worker would never start at all."""
    for name in ("seed_local_db.sh", "restore_local_db.sh"):
        script = (ROOT / "scripts" / name).read_text()

        assert re.search(r"if ! .*pg_restore", script), name


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


def test_the_local_dump_never_reaches_the_image() -> None:
    """`.dockerignore` matches against the whole path and `*` does not cross a `/`, so a
    bare `*.dump` only covers the repository root and leaves `.local-dump/latest.dump` in
    the build context — where `COPY . .` bakes production data into every layer."""
    ignored = (ROOT / ".dockerignore").read_text().split()

    assert "**/*.dump" in ignored


def test_the_half_downloaded_dump_never_reaches_the_image() -> None:
    """Both scripts download to `latest.dump.partial` and rename on success, so for the
    length of the transfer — minutes, on a real dump — the production bytes sit under a
    name `**/*.dump` does not match. A `docker compose build` in another terminal during
    that window is all it takes. The directory is excluded rather than a second suffix
    pattern: nothing in `.local-dump/` belongs in an image under any name."""
    ignored = (ROOT / ".dockerignore").read_text().split()

    assert f"{DUMP_DIR}/" in ignored


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
