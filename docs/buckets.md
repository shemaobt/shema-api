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
