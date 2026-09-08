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
environment variables on the service directly. They are not the same few. Production sets one,
the platform bucket. Staging sets that one and three more — the environment name, the mail
provider and the job-queue app id — because each has to differ from production's: the app id
in particular, since a second registration under production's id would overwrite it. Anything
secret comes from Secret Manager, never from a workflow file.

The migrations job is expected to go red on an integration branch between certain steps, and
that is not a reason to switch it off: every merge that brings its own migration leaves the
graph with more than one head until a merge revision collapses them. Red there means a merge
revision is owed. The suite stays green through all of it, because pytest creates its tables
directly and never walks the graph — which is the whole reason that job exists.

Merge gates differ by target. A pull request into `dev` needs the checks and a blocking bot
review, with no human approval; one into `main` needs the checks and one human approval, with
the bot advisory.
