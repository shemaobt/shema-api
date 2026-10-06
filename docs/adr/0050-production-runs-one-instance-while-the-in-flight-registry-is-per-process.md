---
status: accepted
date: 2026-10-06
---

# Production runs one instance while the in-flight registry is per-process

The turn door keeps the turns it is running in a module-level dict (`turn_dedup.py`), one per
process. With more than one instance, a look at a turn (ENG-1445) can land on an instance that
never saw it and answer 404, and a resend of the same idempotency key (ENG-1354) can land on a
second instance and run the turn twice.

Decided with Henok on 2026-10-05 (ENG-1337): the production `gcloud run deploy` carries
`--max-instances=1`, beside `--min-instances=1`; the pin is a ceiling, not a guarantee of one process: it holds between deploys, and not across one, because both revisions serve for a moment during a rollout, so a resend crossing processes becomes rare, not impossible, and the window returns on each deploy.

The pin lifts when the registry is shared across instances, for example held in the database.
Until then, raising it reopens both failures.

Rejected: no pin. Cloud Run's default ceiling lets the service scale out under load, which is
when the look and the resend are most likely to cross instances.
