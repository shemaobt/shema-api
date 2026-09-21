"""What the Oral Collector's cases share, and none of them owns."""

from __future__ import annotations

#: The bucket the oral-collector deploys to when nothing names one, and a made-up name to
#: point the setting at. Both modules that read the bucket assert on the first, so it is
#: written once: it is a real deployed name, not a value a case invented.
PRODUCTION_BUCKET = "tripod-image-uploads"
STAGING_BUCKET = "balde-de-staging"
