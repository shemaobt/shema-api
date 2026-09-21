---
status: accepted
date: 2026-09-21
---

# One lint check, and a schema created once per worker instead of once per test

Lint was five jobs — `ruff`, `boots`, `mypy`, `doctrine`, `canon` — each repeating the same
four setup steps, and a pull request carried five lines for them. Measured, the five cost 40
seconds of work between them and there was not one duplicated tool in the set: ruff already
does lint, formatting and import order, and there is no black, isort, flake8 or pylint
anywhere. The clock was never the cost; the list was. One of the five, `canon`, also had no
`timeout-minutes` at all and inherited GitHub's 360-minute default — the same hole
[ENG-913](https://linear.app/shema-obt/issue/ENG-913) closed on `test.yml`.

Decided: `lint.yml` is one job named `lint`, running the same seven commands in a queue, with
the boot import's three variables and the canon check's `GITHUB_TOKEN` travelling with their
own steps, an explicit `permissions: contents: read`, and a ceiling of 10 minutes. The first
failure stops the queue. Rejected: keeping the checks apart so a red arrives from whichever
finishes first — nobody read them separately, and the separation is what left one of them
without a ceiling for as long as it had one.

The test job is the other half, and the real one. Green runs took 28 to 61 minutes against a
40-minute ceiling whose slack had gone from twice to about 1.1, so a slightly slower run
would fail on time rather than on tests. There is no slow test to blame: 3259 tests, median
0.53 s, and the 102 above a second account for 208 s of 1657 s. The floor was the fixture.
`db_session` ran `Base.metadata.drop_all` and `create_all` before **every** test — 138 DDL
statements over 69 tables, measured at 0.20 s (0.29 / 0.21 / 0.20 / 0.21 / 0.21), which over
3259 tests is around ten minutes locally and three to six times that on the runner.

Decided: the schema is created once per worker process, in the session-scoped engine fixture,
and each test is given a clean database by a **sweep** — every row of every table deleted in
one transaction in reverse dependency order, then the two seeded `App` rows written again.
Measured at 0.014 s (0.016 / 0.013 / 0.014 / 0.014 / 0.013), a fifteenth of the DDL cycle.
The suite runs `pytest -n 4 --dist loadfile`, four processes split by file, with
`pytest-xdist` as a development dependency only. Both ceilings are 10 minutes, each of them on the job: the
five minutes are what the test step is expected to take and what the ceiling is calibrated
against, and nothing enforces them separately.

Rejected: a per-test rollback, which reads as the obvious answer and cannot work here — 24
sites in `app/` open their own session from `AsyncSessionLocal` and commit on another
connection to the same file, and several cases deliberately read the result back through a
second session or a second engine, so there is no single transaction to roll back. Rejected:
the SQLite savepoint recipe, which fails on the driver's own legacy transaction control, a
SAVEPOINT taken before a BEGIN not joining the enclosing transaction. Rejected: Postgres in
the suite, and `--dist loadscope`, which would split a module across workers and break the
file order two of the database's own cases depend on. Measured and not kept:
`PRAGMA foreign_keys=OFF` around the sweep, which is a no-op inside a transaction in SQLite
and measured slower, not faster.

A consequence worth naming. `--dist loadfile` is load-bearing, not a preference: a module's
tests share one worker and run in file order, which is what lets a case prove that a row
committed on the production path did not survive into the next test. And the database file is
now named by `PYTEST_XDIST_WORKER` rather than by the pid, because the controller imports the
conftest too, names a file, and the workers inherit that name through their environment —
measured, two workers both landed on `shema-api-test-<controller pid>.db`. The conftest
publishes the URL it generated beside the value, so a worker overrides an inherited name of
the suite's own making while a `DATABASE_URL` a caller set on purpose is still honoured.
