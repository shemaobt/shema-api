"""Where a budget attachment's bytes live, and for how long a link to them stands.

A dedicated **private** bucket — uniform bucket-level access, public-access prevention
enforced, the same provisioning as ``sound-necklace-private`` — so a team's budget is
reachable only through a signed URL this module mints. The name is configuration, not a
secret, same as the other bucket constants in this repository.

The wrong pattern is one import away and is refused by name: ``app/services/storage/
upload.py`` answers a **public** URL from an open bucket, and routing a budget through it
would publish the one document in this form that prices a team's work. Nothing in this
module or its callers builds a ``storage.googleapis.com`` URL; rows store keys, and a key
becomes a URL only as the short-lived signed GET of ``attachment_download_url``.

The key is content-addressed — the sound-necklace pattern (``store_artifacts.py``): the
sha256 in the path means a replacement never overwrites its predecessor's object and a
re-upload of identical bytes lands on the same object instead of a duplicate. The frozen
last segment is what a browser saves the download as; the client's own filename never
enters the key, because a user-controlled segment (``../..``, a newline) signs fine and
then 404s — the silent custody failure the sound-necklace docstring names.

The GCS calls themselves are ``app/services/oral_collector/gcs_utils.py``, reused with
this bucket the way sound-necklace reuses them with its own.
"""

GCS_RR_BUCKET = "resource-requests-private"

DOWNLOAD_URL_EXPIRY_MINUTES = 15


def storage_key(request_id: str, sha256: str, extension: str) -> str:
    """One attachment's immutable object name: scoped to its request, addressed by content."""
    return f"resource-requests/{request_id}/{sha256}/orcamento{extension}"
