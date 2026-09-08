---
status: accepted
date: 2026-09-08
---

# Staging is a second Cloud Run service that tracks `dev`, on a Neon branch of production

No repository in the organisation had a staging environment; every merge to `main` was the production deploy, and the Bancada work (thirty stacked PRs) had nowhere to be exercised together before reaching users. We decided to add staging as a **second Cloud Run service, `tripod-backend-staging`, in the same GCP project and Artifact Registry as production**, deployed on every push to a new long-lived branch `dev`, with `main` unchanged as production. `dev` reaches `main` only through a pull request a person opens once staging has been validated.

Staging is realistic, not empty: its database is a **Neon branch named `staging`, created from production with the real, un-anonymised data**, reset from production by hand and on request only, so a reset never erases what a team was testing. The organisation already restores production dumps on developer machines, so real data in staging is no new exposure. Everything that would write into production on staging's behalf is its own: an Inngest app with its own keys (the app id was a literal in code and a second deploy under the same name would overwrite production's registration), the two GCS buckets (seeded once by copying production's objects, never synced again), the JWT signing secret (a production token must not open staging), and Qdrant through the non-production collection. Google and ElevenLabs API keys are shared with production, accepting the cost. E-mail is the `log` provider. Staging authenticates its deploy with the same service-account JSON key production uses, deliberately not Workload Identity Federation, because the environment was urgent and federation is a `shema-infra` migration.

Considered and rejected: a separate GCP project (new IAM and billing for no isolation the team needs), an empty seeded database (tests nothing that matters), promoting `dev` to `main` on a schedule (going to production is a human decision), and Cloud Run `min-instances=1` around the clock (a Cloud Scheduler pair sets it to one at 08:00 and zero at 00:00 America/Sao_Paulo, and the deploy never touches that value after creation so a night deploy cannot switch the service back on).

Consequences: staging and production share quota and billing; the migration graph is proven on staging first, since `alembic upgrade head` (singular, as in production) fails the staging deploy on a bifurcated graph before `main` ever sees it; and the merge gates differ by branch: PRs to `dev` need the CI checks and the Joãozinho review in block mode and no human approval, PRs to `main` need the CI checks and one human approval with the bot advisory only.
