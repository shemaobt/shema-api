"""Media and materials — the two collections whose default is *not authorized*.

FE-44 §8.3 and ``docs/shema.md`` §5.5 give this aggregate one rule that inverts the
prototype's own behaviour, and it is the rule the whole module's media story rests on:
**only an explicit** ``granted = true`` **counts**, so an item with no recorded decision
behaves exactly as a refused one. The prototype shipped a default-checked toggle; a server
that copies it publishes photographs of field teams nobody agreed to publish.

That is why the authorization column is **nullable** rather than a boolean defaulting to
false. There are three states, not two: undecided, granted, refused — and the third rule of
the section needs all three, because **replacing the artifact resets the decision to
undecided**. The consent belonged to that file, not to the slot, and a reset to *refused*
would be the server recording a decision nobody made. Readers ask ``granted is True``;
everything else is a no.

**Who decided is a name and not a reference.** ``authorized_by`` is the acting user's name as
it was then — an accountability record of who acted under the name they had, which must not
follow a later rename. FE-44 §5.3 names it as one of exactly two stored copies of a person's
name that are correct, beside ``RoleChange.changedBy``.

**A row stores a key, never a URL.** ``docs/shema.md`` §4.6 refuses
``app/services/storage/upload.py`` by name: it is a proxy upload to an open bucket returning
a plain object URL, and *a per-item authorization that ends in a public URL enforces
nothing*. BE-04 builds the adapter against a private Shemá bucket, following
``app/services/resource_request/_attachment_storage.py`` — content-addressed keys, the
client's filename never in the key, and a short-lived signed GET minted per call and
persisted nowhere. The video is the exception and is not one: ``ProjectVideo.url`` is an
address on somebody else's service, so it is a URL because that is what it is.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.db.models.shema_enums import (
    MATERIAL_KIND,
    MEDIA_KIND,
    ShemaMaterialKind,
    ShemaMediaKind,
)
from app.db.types import UtcDateTime


class ShemaMediaItem(Base):
    """A photo or a video on a project's record, with the decision about sharing it.

    One table for both, as ``docs/shema.md`` §5.5 asks. ``MediaPhoto`` and ``ProjectVideo``
    are two frozen shapes that differ in one field each — a stored image against an external
    URL — and share the caption and the whole authorization triple, which is the part every
    output path has to consult. Two tables would mean two places for ``can_share_media`` to
    read and two chances for the second one to be forgotten.

    Rows are ordered by ``created_at`` and addressed by ``id``. There is no ``position``
    column: FE-44 says materials are addressed by id and never by position, the same reading
    holds here, and a position column is an invitation to address by it.
    """

    __tablename__ = "shema_media_items"
    __table_args__ = (Index("ix_shema_media_items_project_kind", "project_id", "kind"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("shema_projects.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[ShemaMediaKind] = mapped_column(MEDIA_KIND, nullable=False)

    #: The photo's object in the module's private bucket. NULL on a video, and on a photo
    #: slot that has a caption and no image yet — ``MediaPhoto.image`` is nullable.
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    #: The filename the person uploaded, kept for display only. It is deliberately not part
    #: of ``storage_key``.
    file_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    #: The video's address on someone else's service. NULL on a photo.
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    caption: Mapped[str] = mapped_column(Text, default="", server_default="")

    #: NULL is undecided and refuses like ``False``; only ``True`` authorizes. Replacing the
    #: artifact sets this back to NULL.
    authorization_granted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    #: The deciding user's name as it was then — a snapshot, not a reference.
    authorized_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    authorized_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShemaMaterial(Base):
    """A translated artifact the project produced — text, audio or video.

    **Audio is an artifact, not an attachment**: ``format`` and ``duration_seconds`` are read
    from the file at import and never typed, which is why they are nullable here and why
    nothing asks a coordinator for them.

    The primary key is the client-generated id the contract already addresses rows by, with
    a uuid default for a row the server creates. ``dataUrl`` has no column: it is how the
    prototype kept a file inside a browser, and the server's answer to the same need is
    ``storage_key`` — the same private bucket and the same per-call signed GET as
    ``ShemaMediaItem``.
    """

    __tablename__ = "shema_materials"
    __table_args__ = (Index("ix_shema_materials_project_kind", "project_id", "kind"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("shema_projects.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[ShemaMaterialKind] = mapped_column(MATERIAL_KIND, nullable=False)
    scope: Mapped[str] = mapped_column(String(300), default="", server_default="")

    file_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    link: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    #: Read from the file, never typed.
    format: Mapped[str | None] = mapped_column(String(60), nullable=True)
    #: ``Float`` and not ``Integer``: a recording's length is fractional, which is what
    #: ``oc_recordings.duration_seconds`` already settled in this repository.
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    authorization_granted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    authorized_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    authorized_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
