"""Where a Shemá photo, recording or material lives, and for how long a link to it stands.

**A per-item authorization that ends in a public URL enforces nothing**, which is FE-44 §8.3's
sentence and the reason this file exists rather than an import of the module next door.
``app/services/storage/upload.py`` is refused by name, the way
``app/services/resource_request/_attachment_storage.py`` refuses it: it is a proxy upload to
the open ``tripod-image-uploads`` bucket that answers a plain
``https://storage.googleapis.com/...`` object URL, and four things about it bite here in
order — an unsigned URL makes ``can_share_media`` decorative; its accept list is images only,
while a material is ``text | audio | video`` and a prayer request carries audio; its 5 MB
ceiling is below one field-recorded audio file; and ``app/api/uploads.py`` coerces any folder
it does not know to ``images``.

So: a dedicated **private** bucket — uniform bucket-level access, public-access prevention
enforced, provisioned like ``resource-requests-private`` and ``sound-necklace-private`` — and
rows that store **a key and never a URL** (``app/db/models/shema_media.py`` says so on the
column). A key becomes a URL only as the short-lived signed GET of
``media_download_url.py``, minted per call and persisted nowhere. The GCS calls themselves are
``app/services/oral_collector/gcs_utils.py``, reused with this bucket the way sound-necklace
and the Resource Circle reuse them with theirs.

**The key is content-addressed, and the client's filename never enters it.** The sha256 in the
path means a replacement never overwrites its predecessor's object — which matters more here
than elsewhere, because FE-44 §8.3 resets the authorization to *undecided* when the artifact
is replaced, and an overwritten object would leave the old bytes reachable under a decision
that was made about them. A user-controlled segment (``../..``, a newline) signs fine and then
404s, which is the silent custody failure the sound-necklace docstring names; ``file_name``
stays on the row, for display.

**The project's slug is deliberately not in the key, and this is the one place this module
departs from the sibling's shape.** ``resource-requests-private`` scopes by ``request_id``
because an attachment is one per request and has no id of its own. A Shemá media row does have
one, and a Shemá project id is not a uuid — it is ``<language>-<place>``, so for the records
this whole issue exists to protect **the slug names the place**. A signed URL travels further
than the payload it came from: into browser history, a referrer, a proxy log, a message
somebody forwards. Keying by the row's own uuid costs a lookup to answer *which project owns
this object* — which the row answers anyway, and it is the row that is authoritative — and
buys a URL that names nothing.
"""

from __future__ import annotations

from typing import Final, Literal

#: Configuration, not a secret, the same as every other bucket constant in this repository.
GCS_SHEMA_BUCKET: Final = "shema-private"

#: Minutes a minted link stands. The sibling's fifteen, for the sibling's reason: long enough
#: for a browser to follow a redirect on a slow connection, short enough that a leaked URL is
#: an incident with an end.
DOWNLOAD_URL_EXPIRY_MINUTES: Final = 15

#: The two collections that keep bytes. ``ShemaMediaItem`` holds the record's photos (a video
#: is a URL on somebody else's service and has no object here); ``ShemaMaterial`` holds what
#: the project produced.
#:
#: A set this small and this closed is a ``Literal`` in this codebase — ``Sex`` in
#: ``app/models/oc_storyteller.py``, ``InviteStatus`` in ``app/models/resource_request_access.py``
#: — so that a wrong collection is a name ``mypy`` reads at the call site rather than a string
#: that travels as far as :func:`storage_key` before anybody notices.
MediaCollection = Literal["media", "materials"]

MEDIA: Final[MediaCollection] = "media"
MATERIALS: Final[MediaCollection] = "materials"

#: The last segment is frozen per collection because it is what a browser saves the download
#: as, and the only alternative — the name the person uploaded — is the user-controlled
#: segment this file will not put in a key.
_FILENAMES: Final[dict[MediaCollection, str]] = {MEDIA: "photo", MATERIALS: "material"}


def storage_key(collection: MediaCollection, item_id: str, sha256: str, extension: str) -> str:
    """One item's immutable object name: scoped to its row, addressed by its content.

    ``extension`` carries its own dot (``.jpg``) or is empty, which is what
    ``os.path.splitext`` answers and what the sibling's callers pass.

    The membership check stays behind the annotation rather than instead of it: ``mypy`` does
    not run over ``tests/`` (``pyproject.toml``), and a collection can also arrive as a plain
    string off a row or a request body, where a typo has to raise rather than build a key
    under a folder nothing will ever look in.
    """
    if collection not in _FILENAMES:
        raise ValueError(f"unknown media collection: {collection}")
    return f"shema/{collection}/{item_id}/{sha256}/{_FILENAMES[collection]}{extension}"
