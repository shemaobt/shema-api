"""Received submissions and the leader's intake link — the module's two unauthenticated seams.

``docs/shema.md`` §5.12 and FE-44 §5.7 settle what these hold before GATE-03 settles the file
format. Four of the rules are not open and are built on here: the import is **idempotent and
transactional** so a double import is a no-op, the submission is archived **byte-identically**,
**only the Pulse is archivable**, and the leader link grants the intake form and nothing else
and it expires.

**Only the Pulse is archivable — which is why there is no ``kind`` column.** ``ArchivedKind``
is ``"pulso"`` and deliberately narrower than ``FormKind``: the Avaliação de Saúde is filled
in-app and produces no file, so nothing of it ever leaves to come back, and its history
belongs to ``shema_health_assessments``. A column with one value would invite a second, and a
server that archives a ``health`` submission has landed a kind that by definition never left.
A table with no such column cannot hold one.

**The token is stored hashed**, following every other token in this repository —
``refresh_tokens``, ``password_reset_tokens`` and ``access_invites`` all keep a ``String(64)``
hash and let the raw value leave exactly once. ``docs/shema.md`` §6.6 adds the rule that
matters more than the storage: the guard is a **service function**, ``verify_intake_token``,
not a router condition, so it holds for any future caller of it.

**BE-12 added the third table and four columns**, and the third table is the one that changes
what the other two mean. A submission that recorded only its answers becomes unreadable the
first time the form is edited — the words the answers were given to are gone, and every past
answer has been silently rewritten. So a definition is **stored and versioned**, a submission
points at the version it answered, and a link points at the version it was minted with. The
spec itself is authored in ``app/utils/shema_forms.py`` and published here by content, which
is what makes *configured, not designed in-app* a property of the schema rather than a promise.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.db.types import UtcDateTime


class ShemaFormDefinition(Base):
    """One published version of one instrument's field spec — what an answer is read against.

    **A definition that changes in place rewrites the meaning of every past answer**, silently
    and with no way back: the words the answers were given to are gone. So a version is cut,
    never edited, and a submission points at the one it answered. That is OBT-401's first DoD
    line, and it is the whole reason this table exists rather than a constant in a module.

    ``content_hash`` is what makes publishing **idempotent**. The spec is authored in
    ``app/utils/shema_forms.py`` and published by ``_form_definitions.py``, which hashes what
    that file says and reuses the row when the hash already stands. So a deploy that changed
    nothing cuts no version, and a deploy that changed a label cuts one — without anybody
    remembering to bump an integer, which is the half of versioning that is always forgotten.

    ``kind`` is ``String(40)`` and **not a native enum**, against this module's usual habit
    (``docs/shema.md`` §7.3). ``FormKind`` is the vocabulary it would be, and FE-44 §12.9
    already refuses to type its own ``formType`` for the reason that applies here too: the
    values the product actually writes are not a closed list anybody has closed. An enum here
    would buy a ``CHECK`` and cost a migration the day a second field instrument exists.

    ``fields`` is the spec as it stood — the list of ``{key, type, required, labelKey, column,
    maxLength, options}`` rows ``FormField.as_spec()`` produces. Stored whole rather than
    normalised into rows, because it is read as a unit, never queried into, and its value is
    that it is a **frozen copy**: a spec in a second table is a spec a later migration can
    edit, which is the failure this table is built against.
    """

    __tablename__ = "shema_form_definitions"
    __table_args__ = (
        Index("uq_shema_form_definitions_kind_version", "kind", "version", unique=True),
        Index("uq_shema_form_definitions_kind_content", "kind", "content_hash", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    #: ``ArchivedKind`` today, and ``FormKind`` the day a second instrument produces a file.
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    #: 1-based and monotonic **per kind**, so *version 3 of the Pulse* is a sentence.
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    #: The frozen spec. ``list`` and not ``dict``: the order is the order the form is asked in.
    fields: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    #: SHA-256 of the canonical spec — the identity a version is cut against.
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now()
    )


class ShemaSubmission(Base):
    """One received Pulse, and the file it arrived as.

    ``language_name`` and ``submitted_by`` are **snapshots on the row**, because the contract
    puts them on ``ReceivedSubmission`` and because an archive that resolves them through the
    project would answer with today's values for a file received last year. That is the
    opposite of the *never duplicate a role-holder's name* rule and for the same reason: this
    is a record of what arrived, not a view of what is.

    ``storage_key`` is the archived artifact, byte-identical to what was submitted, in the
    module's private bucket. ``content_hash`` is what makes the import idempotent without a
    read of the file: a second arrival of the same bytes for the same project conflicts on
    the unique index rather than producing a second archive and a second progress entry.

    The project reference **restricts**: an archive whose project was deleted is an archive
    nobody can read, and what should happen to received files is a decision the issue that
    wants a project delete owns.
    """

    __tablename__ = "shema_submissions"
    __table_args__ = (
        Index("ix_shema_submissions_project_received", "project_id", "received_at"),
        Index(
            "uq_shema_submissions_project_content",
            "project_id",
            "content_hash",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("shema_projects.id", ondelete="RESTRICT"), nullable=False
    )
    #: The language name as the submission carried it, not as the project holds it today.
    language_name: Mapped[str] = mapped_column(String(200), default="", server_default="")
    submitted_by: Mapped[str] = mapped_column(String(200), default="", server_default="")
    received_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now()
    )
    #: The archived file, for the day GATE-03 settles a format that produces one. ``NULL``
    #: for everything received today, which arrives as a payload on the wire and is archived
    #: in :attr:`archived_payload` — the bytes are kept either way, which is the rule.
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    #: Content hash of the archived bytes — what makes a double import a no-op.
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    #: The version of the form this submission **answered**, not the newest one.
    definition_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("shema_form_definitions.id", ondelete="RESTRICT"), nullable=False
    )
    #: The link it arrived through, or ``NULL`` when a coordinator filed it directly.
    #:
    #: ``SET NULL`` and not ``RESTRICT``: revoking a link must not be blocked by an archive,
    #: and an archive must not keep a revoked credential's row alive to point at.
    intake_link_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("shema_intake_links.id", ondelete="SET NULL"), nullable=True
    )
    #: **The bytes, as they arrived** — the validated request body, verbatim, which is what
    #: *archived byte-identically* means for a submission that arrived as a payload rather
    #: than as a file. Written only after the submission passed its definition whole: a store
    #: of unvalidated payloads to clean later is a store nobody ever cleans.
    archived_payload: Mapped[str] = mapped_column(Text, nullable=False)
    #: When a coordinator applied this to the record, or ``NULL`` while it is still an inbox
    #: entry. It is what keeps applying **idempotent** on a second attempt, and it is a
    #: timestamp rather than a flag for the reason ``used_at`` below is one.
    applied_at: Mapped[datetime | None] = mapped_column(UtcDateTime(timezone=True), nullable=True)


class ShemaIntakeLink(Base):
    """A token that lets one team leader open one intake form, and nothing else.

    It is not a session and it mints no token pair. No console, no project data beyond the
    form, and it expires — three rules from ``docs/shema.md`` §6.6, of which only the expiry
    is a column, because the other two are about what the route serves.

    ``used_at`` records the first successful submission through the link and ``revoked_at``
    an explicit withdrawal. Both are timestamps rather than flags for the reason the sibling's
    ``retired_at`` records: *when* is the question a later reader asks and a boolean cannot
    answer. Neither is *the* guard — ``verify_intake_token`` composes expiry, revocation and
    the hash in one service function, so a future caller inherits all three.
    """

    __tablename__ = "shema_intake_links"
    __table_args__ = (Index("ix_shema_intake_links_project", "project_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("shema_projects.id", ondelete="CASCADE"), nullable=False
    )
    #: The raw token leaves once, at creation, and is never stored.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    #: **The version this link was minted against**, and the one the answer is read with.
    #:
    #: Pinned rather than resolved at submission time on purpose: a leader opens the form,
    #: drives out to where the team is, and answers it days later with no connection in
    #: between. A definition edited in that window would reject an answer nobody gave wrongly.
    definition_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("shema_form_definitions.id", ondelete="RESTRICT"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(UtcDateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now()
    )
