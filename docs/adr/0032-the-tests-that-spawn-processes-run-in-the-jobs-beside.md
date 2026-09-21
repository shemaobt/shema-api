---
status: accepted
date: 2026-09-21
---

# The tests that spawn processes run in the jobs already running beside

[ADR 0031](0031-one-lint-check-and-a-schema-once-per-worker.md) took the suite from 28–61
minutes down to a `Run tests` step measured at 231 s and 440 s, and left the target written
down: five minutes on that step. What was left over is not the constant floor 0031 removed.
Measured on 2026-09-21: the whole suite in four processes takes 85.6 s; without seventeen
files it takes 46.8 s; those seventeen alone take 41.75 s. Sixty-nine tests of 3277 — 2.1 %
of them — are 46 % of the clock.

What the seventeen share is not a subject. Fourteen walk a migration, and each case replays
all 100 migrations against a throwaway SQLite file to reach the one it is about; three open
fresh interpreters to prove something the suite's own process cannot prove about itself —
that every room module imports without a cycle, that the application boots, that two runs of
the suite in one checkout do not tear each other's tables down. Each of them pays for a
process it starts.

The obvious guess is that the subprocess is the cost, and it is not. Measured:
`alembic upgrade head` over the 100 migrations on a clean SQLite file is 0.40 s
(0.39 / 0.41 / 0.42); a bare interpreter start is 0.05 s, `import app.models` 0.16 s,
`python -m alembic --help` 0.20 s. The interpreter is a fifth of the call. Replaying a
hundred migrations to reach the one under test is the rest.

The second guess, the one that brought the question here, was that the suite carries tests
that do not belong in it: the ones that read the CI workflows, `docker-compose.yml` and the
sha256 pins of Marcia's artifacts. Measured: twenty-one such files, 0.66 s between all of
them. They are not the cost, and several are the only thing standing between a named
incident and its return — [ENG-554](https://linear.app/shema-obt/issue/ENG-554)'s gateless
integration branch, [ENG-926](https://linear.app/shema-obt/issue/ENG-926)'s canon check that
was written in the file and never invoked, the fixtures rule `AGENTS.md` names by the test
that holds it. They stay exactly where they are.

Decided: a test that spawns processes to prove what it proves does not run in the pull
request's test job. The fourteen that walk a migration carry the `migration` marker and run
in the Migrations job, which already walks the graph on Postgres. The three that open a fresh
interpreter carry `fresh_interpreter` and run in the job that already boots the application
in a clean interpreter as one of its seven commands — renamed `Checks`, because it no longer
only lints. The test job selects `-m "not migration and not fresh_interpreter"`, and a test
asserts the three selections are disjoint and their union is every test collected: a file
cannot fall outside all three jobs without turning it red.

Both destinations already run on every pull request, in parallel, on their own runners: 53 s
and 66 s against the test job's 231–440 s. Nothing leaves the gate, nothing waits longer, and
the pull request gains no new line. That last part is why a fourth job was rejected — ADR
0031 collapsed five lint jobs into one because the list of checks was the cost and the clock
never was, and a new job puts back what it had just removed.

Rejected: cutting the twenty-one configuration tests, which is where the question started.
0.66 s is not a lever, and each one guards an incident that already happened. Rejected:
making the migration harness cheap first, by starting from a database file prepared at the
revision under test instead of replaying a hundred migrations. It is the larger saving in
CPU and it stays available, but it is new machinery in the harness, it does nothing for the
three that spawn interpreters, and the separation gets the whole clock today without it.
Rejected: a path list in the workflows instead of markers — two lists to keep in step by
hand, and a new file forgotten in one of them runs in one job or in neither, silently.
Rejected: more parallelism. The repository is public and the organization is on the free
plan, so Actions minutes are unlimited and a step costs nothing, and the standard runner has
four cores — exactly the four processes ADR 0031 configured. There is no oversubscription to
fix and no larger runner to buy.

A trap worth writing down, because it fails somewhere other than where it is made. The
Migrations job sets `DATABASE_URL` at job level, pointed at its Postgres container, and the
suite's conftest honours `DATABASE_URL` when it is set. A pytest step added there without
clearing it runs the fourteen against Postgres instead of the SQLite file each case builds
for itself, runs them serially — a run that names its own database runs without `-n` — and
creates tables over the schema the previous step migrated. The failure then surfaces in
`alembic check`, a step later, as models that do not match the schema.

A consequence worth naming. `tests/test_migration_graph.py` carries no marker and stays in
the test job: it reads the graph with `ScriptDirectory` instead of walking it, costs almost
nothing, and is the sibling of the `alembic heads` command that job already runs. The rule is
what a test does, not what it is about.
