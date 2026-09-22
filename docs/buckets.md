# Buckets

Two CORS configuration files sit at the repository root, one per bucket. **They are applied by
hand and by nobody else** — no workflow, script or startup path reads them. They can drift
from the live buckets silently, and one of them already had. Read the bucket before trusting
the file:

```sh
gcloud storage buckets describe gs://sound-necklace-private --format="json(cors_config)"
gcloud storage buckets update  gs://sound-necklace-private --cors-file=sound-necklace-cors.json
```

What belongs in the allowlist, and why the range header stays while the write verbs went, is
[ADR 0011](adr/0011-range-stays-in-the-bucket-cors-allowlist.md).

The oral-collector's bucket — its audio and the console's uploaded images, one bucket — is
named per environment by `GCS_OC_BUCKET`, which is not `GCS_PLATFORM_BUCKET` above: that one
is the server-side TTS cache. Its CORS is `gcs-cors.json`, applied by hand like the others.
See [ADR 0029](adr/0029-the-oral-collectors-bucket-is-a-setting.md). Production's deploy
names it explicitly; the local files (`docker-compose.yml`, `.env.example`) default to the
staging bucket, so a run at home that configures nothing cannot reach production's files
([ADR 0033](adr/0033-production-declares-its-own-bucket.md)).

## Cloud Run origins

A Cloud Run service answers on two URL forms. The deterministic one is
`SERVICE-PROJECTNUMBER.REGION.run.app`, which can be written down before the service exists;
the legacy one carries a random hash Cloud Run assigns at creation, which cannot be known in
advance.

That distinction has already produced a wrong entry, and it is still live: the Sound Necklace
CORS file lists a hash-form origin for a service that did not exist when it was written, so
that hash was never read off a deployment and identifies nothing. Once the service is deployed,
read its real URL and replace that origin, rather than deleting the line and assuming the
deterministic form is enough — Cloud Run gives every service both.
