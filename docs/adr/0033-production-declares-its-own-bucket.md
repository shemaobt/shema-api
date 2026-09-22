---
status: accepted
date: 2026-09-22
---

# Production's deploy now names the oral-collector's bucket

[ADR 0029](0029-the-oral-collectors-bucket-is-a-setting.md) made the bucket a setting and
rejected naming it on production's deploy, on the grounds that a second place to keep in
step with the Python default was a risk, not a safeguard. Measured since: the running
service declares `GCS_OC_BUCKET` nowhere — not in `deploy.yml`, not by hand on the Cloud Run
service — and reaches the right bucket only by falling through to the default. That default
is one silent edit of `config.py` away from redirecting production, with nothing in the
repository to catch it.

Decided: `deploy.yml` now names `GCS_OC_BUCKET=tripod-image-uploads` beside
`GCS_PLATFORM_BUCKET`, the same value the service already runs with, so the deployed
behaviour does not change. A test ties that token to
`Settings.model_fields["gcs_oc_bucket"].default`, so the deploy's literal and the Python
default can no longer drift apart without turning a test red. The local files
(`docker-compose.yml`, `.env.example`) default to the staging bucket, so a run at home that
configures nothing can no longer reach production's files.

Rejected: an empty Python default that refuses to boot without the variable — that changes
behaviour on every existing deploy and is a separate decision. Naming production's name as
the compose fallback, the way `GCS_PLATFORM_BUCKET` already does — that documents the hole
this record exists to close instead of closing it, and is `GCS_PLATFORM_BUCKET`'s own
decision to revisit, not this one's.
