# shema-api

The FastAPI server behind the Shemá oral Bible translation tools: the Internalization Room,
the Facilitator Desk, the Sound Necklace, the Oral Collector and the Annotation Studio.

## Commands

Package manager is `uv`, on Python 3.11: `uv python install 3.11`, then `uv sync --frozen --group dev`.

```sh
JWT_SECRET_KEY=test-secret-for-pytest-only uv run pytest tests/ -n 4 --dist loadfile -m "not migration and not fresh_interpreter"

uv run ruff check . && uv run ruff format --check .
DATABASE_URL=sqlite+aiosqlite:///./boot-check.db JWT_SECRET_KEY=test-secret-for-ci-only INNGEST_DEV=1 uv run python -c "import app.main"
uv run mypy app/
uv run python scripts/check_doctrine.py
uv run python scripts/sync_doctrine.py --check
TRIPOD_COMPILER_REPO=~/tripod_compiler uv run python scripts/sync_internalization_canon.py --check
DATABASE_URL=sqlite+aiosqlite:///./boot-check.db JWT_SECRET_KEY=test-secret-for-ci-only INNGEST_DEV=1 uv run python scripts/smoke_internalization_canon.py
JWT_SECRET_KEY=test-secret-for-ci-only uv run pytest tests/ -m fresh_interpreter

env -u DATABASE_URL JWT_SECRET_KEY=test-secret-for-ci-only uv run pytest tests/ -n 4 --dist loadfile -m migration
PYTHONWARNINGS=error::UserWarning uv run alembic heads   # exactly one head, no duplicate ids
```

A test that spawns a process to prove what it proves does not run in the first line, the
`test` job's own selection. The eight lines between the blank ones are the `checks` job — the
seven commands the old `lint` job ran, in order, the canon smoke, then the `fresh_interpreter` selection: the
three files that each open a clean interpreter to prove something the suite's own process
cannot. The `migration` selection is the `migrations` job's own step,
`DATABASE_URL` cleared: that job sets it at job level for its Postgres container, and left in
place the fifteen migration-walking files would run against that Postgres instead of the
SQLite file each builds for itself. The three selections partition the whole suite, pinned in
`tests/test_ci_gates.py`.

The suite needs `ffmpeg` and `ffprobe` on the host, because it measures recordings with them exactly as the deployed image does. It runs on SQLite and touches neither the local Postgres nor Neon. The test database is one file per process, in the system temporary directory and named by the xdist worker or, in a serial run, by the pid, so two runs in one checkout and four workers in one run do not corrupt each other; `DATABASE_URL` is honoured when set, and the run then uses that one file and leaves it behind — so a run that names its own database runs serially, without `-n`. The schema is created once per process and each test is given a clean database by a sweep, not by recreating it.

## Golden runs

Marcia's golden scripts are played against a running server through two doors that exist only
where `INTERNALIZATION_ROOM_RUNNER_KEY` is set — production sets none and both answer 404. The
Guide's conversation is played through the **Golden doors**,
`/api/internalization-room/golden/session` and `/golden/turn`, in her runner's wire, with the key
as `Authorization: Bearer <key>`; the back-translation check through the **Text seam**, which
reads it in `X-Access-Code`.
Two runners, one convention: reports land under `golden/reports/<date>/`, committed, and the key
travels as `ACCESS_CODE`. Her five session scripts are vendored at `golden/sessions/`
under the pin in `docs/doctrine/DOCTRINE_PIN`, beside her own 5/5 of 2026-09-03.

```sh
# the Guide's conversation: the five sessions, her mechanical checks, her judge, one README
# per run; a session passes only when the judge passed it and no check tripped, exit 1
# otherwise. --only <name> plays one of them. The judge runs in this process on the voice
# ladder, so it needs ANTHROPIC_API_KEY (and ANTHROPIC_WORKSPACE_ID for an identity-bound
# key) and a DATABASE_URL for the settings to load, in the environment or in .env.
ACCESS_CODE=<key> uv run python scripts/golden_runner.py --base-url <host>/api/internalization-room
# her own runner against this room, from her repository: the same doors and the same key
GOLDEN_HTTP_TOKEN=<key> node src/golden/run.ts --http <host>/api/internalization-room [P01-opening-and-mother-tongue]
# the judge again over a run already committed, without playing the room
uv run python scripts/golden_runner.py --rejudge golden/reports/<date> --out golden/reports/<date>-rejulgado
# the back-translation check, judged by her own checks; exit 1 on a failed check
ACCESS_CODE=<key> uv run python scripts/bt_golden_runner.py --base-url <host>/api/internalization-room/text-seam/back-translation/ --script <her-bt.json> --out golden/reports/<date>
```

Each run costs real model calls, so neither is part of the suite. The back-translation run is
the gate on any change to the two back-translation prompts. The golden run is the gate on the
release, not only on CI: `docs/doctrine/vendor/DOCTRINE.md` §5.2 says the golden sessions
must pass before anything touching prompts, turn loop, model or canvas reaches the team, and
a green unit suite is not sufficient to ship a prompt change.

## The canon

Marcia's canon — the Meaning Maps, Meaning Coordinates, Compilation Logs and each book's
aliases list under `app/services/internalization_room/canon/vendor/` — moves only through
`scripts/sync_internalization_canon.py --sync`, and only to a commit on her compiler's main
line; the sync refuses anything else and writes `VENDOR_PIN` and `VENDOR_MANIFEST.json`
beside the copy. It keeps the canon it replaces, with the element labels, under
`canon/kept/<pin>/`: a session reads the canon it opened with until its passage is approved,
so a kept tree may be dropped only once no open session names its pin. Never edit vendored
files, the pin or the record by hand: `--check` holds the copy to the record, and to a clone
of the compiler at the pin where `TRIPOD_COMPILER_REPO` names one, and
`scripts/smoke_internalization_canon.py` fails on what the room could not serve.
`canon-sync.yml` runs the sync twice a week and opens a pull request for review when there
is new canon; it never merges.

`pin_committed` in our `VENDOR_PIN` is the commit's UTC date, because the sync reads the
compiler through GitHub's API, which reports the committer's time in UTC and drops the
offset; her `VENDOR_PIN` carries the committer's local date, `git show --format=%cs`. The
same commit can therefore read a day apart: `5b5c8d2` was committed at 21:42 at −0500, so
hers says 2026-09-29 and ours 2026-09-30. Nothing reads the field; `pin_commit` is the pin.

The order of a canon change is hers:

1. The compiler's spec change merges first, on her word, never during a team session.
2. The app re-pins to the compiler's merge commit.
3. The app's pull request merges.
4. The vault follows the compiler.
5. If the canon-sync bot opened its own pull request for the same change, close it.

## Rules

Every schema change is an Alembic migration, and nothing is applied by hand. Routers never touch the database and services never raise HTTP: [ADR 0009](docs/adr/0009-routers-never-touch-the-database.md).

All repository documentation — this file, `CONTEXT.md`, the ADRs, `README.md` and `docs/` — is written in English. Code identifiers and model prompts are not touched.

What one test module lends another lives in a `tests/*_harness.py`, which exports plain builders and constants. Fixtures never travel: each module keeps its own three-line fixture calling the builder. A package's own `conftest` is the only import between test modules there is, and `tests/test_the_harness_is_the_only_door_between_test_modules.py` holds that line.

## Staging

A push to `dev` deploys the `tripod-backend-staging` Cloud Run service. It has no domain of
its own, so read the URL rather than writing it down, and point a local client at it with
`BACKEND_URL`:

```sh
gcloud run services describe tripod-backend-staging --region us-central1 --format='value(status.url)'
```

## Where the rest is

- [`docs/doctrine/`](docs/doctrine/) — Marcia's [`DOCTRINE.md`](docs/doctrine/vendor/DOCTRINE.md), vendored at her freeze, under the pin in [`FREEZE_PIN`](docs/doctrine/FREEZE_PIN) and binding on every change here. Read it before touching a prompt, the turn loop or the model seam; a change to one of her artifacts needs a ruling in [`rulings/`](docs/doctrine/rulings/).
- [`CONTEXT.md`](CONTEXT.md) — the glossary. Use its terms in code, tests and commits.
- [`docs/adr/`](docs/adr/) — one hard-to-reverse decision each. Conventions and runbooks: [local development](docs/local-development.md), [database](docs/database.md), [API conventions](docs/api-conventions.md), [code style](docs/code-style.md), [CI](docs/ci.md), [buckets](docs/buckets.md), [what the voice says](docs/divine-name-speakable-form.md), and the pinned [Sound Necklace snapshot](docs/sound_necklace_interview_package.md).
- [`RUNNING-LOCALLY.md`](RUNNING-LOCALLY.md) — the composed API on its own port. [`http/`](http/) — request examples.
