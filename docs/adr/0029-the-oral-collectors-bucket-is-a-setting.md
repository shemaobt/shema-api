---
status: accepted
date: 2026-09-21
---

# The oral-collector's bucket is a setting, and a stored URL gives only the object name

The bucket the oral-collector's audio lives in was a literal in Python, written twice — once
for the audio, once for the platform's images, the same value both times. A service built from
this image therefore addressed production by construction, and staging could not be pointed
anywhere. Staging's database is a Neon branch of production's ([ADR 0001](0001-staging-environment.md)),
so its rows carry production's ids and the object keys derive from those ids: deleting a
recording on staging deleted production's file, re-sending one wrote over it, and the cleaning
wrote over the original while saving a backup a second pass would overwrite in turn. That was
live from 2026-09-11 until this change.

Decided: the bucket is `Settings.gcs_oc_bucket`, environment variable `GCS_OC_BUCKET`, read on
every call and never at import, whose default is exactly production's name. Production's deploy
sets nothing and keeps deploying what it always deployed; `deploy-staging.yml` names
`tripod-image-uploads-staging`. The audio and the platform's images read the one setting
because they are one bucket today; giving them two would invent a distinction that does not
exist.

The second half of the decision is where a naive swap breaks. A stored `gcs_url` written before
this change carries production's prefix, and staging's rows carry it too. Reading such a URL
now yields **only its object name**: `blob_name_from_url` parses any
`https://storage.googleapis.com/<bucket>/<name>` and returns `<name>`, with no comparison
against a configured prefix. The bucket every write, copy and delete acts in is the setting's.
In production, where the setting is the default, this is exactly today's behaviour. On staging
an inherited row resolves to its name and the action lands in staging's bucket, so production's
object is never reached — which is the business rule this ticket exists for.

Rejected: an empty default that fails loudly, because production's deploy sets no such variable
today and would break on the next merge to `main`; two settings, one for the images and one for
the audio, for the reason above; and taking the bucket from the stored URL for writes, which
reads honestly and is precisely the harm — staging would write into production for every row it
inherited.

Consequences: the staging bucket must exist, with production's CORS
([`gcs-cors.json`](../../gcs-cors.json), applied by hand like the others — see
[buckets](../buckets.md)) and the same public read, before `dev` deploys with the name on it;
until that deploy runs, staging still writes into production's bucket. The sound necklace's
`GCS_SN_BUCKET` and the annotation studio's `GCS_AS_BUCKET` are exposed the same way and are
ENG-967's, not this record's. The objects staging already wrote into production's bucket since
2026-09-11 are extra files under new keys, none written over another, and are a separate check.
