# CI

Lint, Test and Migrations are the pull request gates: they run on every pull request, and also
on `integration/**` pushes, which have no pull request of their own. That filter stays narrow on
purpose, because the test job has been measured between 6 and 56 minutes and a chain merged
one step at a time pays the slowest job once per step. The rest run on their own triggers,
named in the table.

| Workflow | What it gates |
|---|---|
| Lint | `ruff check` and `ruff format --check` over the repository. |
| Lint, boot job | The application imports in a clean interpreter. A suite's collection order can hide an import cycle; this cannot. |
| Lint, mypy job | Type checking over the application package. |
| Test | The pytest suite on SQLite, with `ffmpeg` installed first so recordings are measured the way the deployed image measures them. |
| Migrations | The graph stands at one head with no duplicate revision ids, and the newest migrations walk down and back up on a clean Postgres. |
| Deploy | A push to `main` builds the image, upgrades the production database and deploys to Cloud Run. |
| Deploy staging | A push to `dev` does the same against the Neon `staging` branch and the staging service, then checks that the service answers publicly. |
| Claude mention | Answers an `@claude` mention on a pull request or issue. |
| Claude cost report | A weekly usage rollup, posted to a webhook when one is configured. |
| Reviews | Two review workflows, each fired by requesting its reviewer on the pull request; re-request to re-run. On a pull request into `dev` the request is made automatically, and remade on every head, because the check is keyed to the head SHA. A third, `claude-review.yml.disabled`, is switched off and runs nothing. |
| Request Joãozinho on dev | Requests the reviewer on every head of a pull request into `dev`, including one retargeted onto it, which is what fires the review there. It requests nobody when the author is Joãozinho's own login or a bot, because the review would skip and a skipped check counts as passing. |

Both deploys pull their configuration from GCP Secret Manager, and each sets a few plain
environment variables on the service directly. They are not the same few. Production sets five:
the platform bucket, the mail provider, the Azure tenant id, the Azure client id and the CORS
origins. Staging sets five of its own — the environment name, the mail provider, the job-queue
app id, its bucket and its CORS origins — because each has to differ from production's: the app
id in particular, since a second registration under production's id would overwrite it. Anything
secret comes from Secret Manager, never from a workflow file, and the Azure client secret is
mounted from there like the rest; the tenant and client ids beside it are not secret.

A workflow that names only some of the service's plain variables still deploys, because
`--update-env-vars` merges: whatever was set by hand survives, unnamed and unrecorded. The
secret set has no such mercy — `--set-secrets` replaces it whole, so a mapping missing from the
file is a mount removed from the service on the next merge. The other edge of naming them is that
these keys now belong to the file: changing a CORS origin is a pull request, and an edit made on
the service by hand is reverted, silently, by the next deploy.

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
