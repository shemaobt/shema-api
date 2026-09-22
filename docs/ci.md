# CI

Checks, Test and Migrations are the pull request gates: they run on every pull request, and also
on `integration/**` pushes, which have no pull request of their own. That filter stays narrow on
purpose, because the test job has been measured between 6 and 56 minutes and a chain merged
one step at a time pays the slowest job once per step. The rest run on their own triggers,
named in the table.

A test that spawns a process to prove what it proves does not run in the Test job: the eight
that walk a migration carry the `migration` marker and run in Migrations, which already walks
the graph on Postgres; the one that opens a fresh interpreter carries `fresh_interpreter` and
runs in Checks, which already boots the application in a clean interpreter as one of its four
commands. `tests/test_ci_gates.py` pins the three selections as a partition of the whole
suite, so a file cannot fall outside all three without that turning red.
[ADR 0032](adr/0032-the-tests-that-spawn-processes-run-in-the-jobs-beside.md). `main` marks
fourteen files and three; this branch has eight and one, and the rest arrive with whatever
carries `main` into `dev`.

| Workflow | What it gates |
|---|---|
| Checks | One job, one check on the pull request, four commands in a queue under a 10-minute ceiling: `ruff check`, `ruff format --check`, the application importing in a clean interpreter (a suite's collection order can hide an import cycle; this cannot), and `mypy app/`, then the file marked `fresh_interpreter`. `main` runs three more commands here, the two doctrine passes and the canon drift check; this branch has no job for them and neither promotion invented one. |
| Test | The pytest suite on SQLite in four processes split by file, with the schema created once per process, selecting out the tests marked `migration` or `fresh_interpreter`, under a 7-minute ceiling. `ffmpeg` is installed first so recordings are measured the way the deployed image measures them. |
| Migrations | The graph stands at one head with no duplicate revision ids, the newest migrations walk down and back up on a clean Postgres, then the eight tests marked `migration` run with `DATABASE_URL` cleared so they build their own SQLite files instead of running against the job's Postgres. |
| Deploy | A push to `main` builds the image, upgrades the production database and deploys to Cloud Run. |
| Deploy staging | A push to `dev` does the same against the Neon `staging` branch and the staging service, then checks that the service answers publicly. |
| Claude mention | Answers an `@claude` mention on a pull request or issue. |
| Claude cost report | A weekly usage rollup, posted to a webhook when one is configured. |
| Reviews | Two review workflows, each fired by requesting its reviewer on the pull request; re-request to re-run. A third, `claude-review.yml.disabled`, is switched off and runs nothing. |

Both deploys pull their configuration from GCP Secret Manager, and each sets a few plain
environment variables on the service directly. They are not the same few. Production sets one,
the platform bucket. Staging sets that one and three more — the environment name, the mail
provider and the job-queue app id — because each has to differ from production's: the app id
in particular, since a second registration under production's id would overwrite it. Anything
secret comes from Secret Manager, never from a workflow file.

Staging answers at <https://tripod-backend-staging-f7ssqjozfq-uc.a.run.app>. Each client names
that address in its own variable, not a shared one: the Internalization Room reads
`BACKEND_URL`, and the Facilitator Desk reads `SHEMA_API_URL` for the dev server's proxy, or
`VITE_API_BASE_URL` with the `/api` prefix to reach the API directly. Outside 08:00–00:00
America/São_Paulo the service keeps no warm instance and wakes on the first request, which
costs a cold start of a few seconds. Running
`gcloud scheduler jobs run staging-on-8am --location us-central1`
warms it, but that instance then stands until the next midnight job — nothing switches it
off earlier — so at night the cold start is usually the better trade. If you do warm it, run
`gcloud scheduler jobs run staging-off-midnight --location us-central1`
when you are done.

Renewing staging's data is a Neon operation, not a deploy: open the `staging` branch and use
**Reset from parent**. That brings production's rows back and drops every migration that
reached `dev` after the branch point, so reapply them with `gh workflow run
deploy-staging.yml --ref dev`. It is done on request only — a reset erases whatever a team
was testing.

The migrations job is expected to go red on an integration branch between certain steps, and
that is not a reason to switch it off: every merge that brings its own migration leaves the
graph with more than one head until a merge revision collapses them. Red there means a merge
revision is owed. The suite stays green through all of it, because pytest creates its tables
directly and never walks the graph — which is the whole reason that job exists.

Merge gates differ by target. A pull request into `dev` needs the checks and a blocking bot
review, with no human approval; one into `main` needs the checks and one human approval, with
the bot advisory.
