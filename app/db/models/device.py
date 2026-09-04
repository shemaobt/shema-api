"""The device table.

A device is a tablet the platform knows about: a row with a project, an optional label,
and the single-use code it displayed once at installation. Until a facilitator spends
that code the row exists with no project, which is a normal state and not an error.

The code itself is never stored. What the row keeps is a SHA-256 of it, which is what
lets a replayed code still be recognised as *spent* — the distinction Behaviour 4 needs
in the log — without a credential-shaped string outliving its purpose in the table. See
``app/services/device/claim_code.py`` for what that hash does and does not buy.
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.db.types import UtcDateTime


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    #: Null until a claim code is spent against a project, and null again if the device
    #: is unlinked. Everything downstream has to tolerate it.
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )

    #: Free text a facilitator uses to tell two tablets apart on a shelf. It authenticates
    #: nothing, it is optional, and it is editable after the fact.
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)

    claim_code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    claim_code_expires_at: Mapped[datetime] = mapped_column(UtcDateTime(timezone=True))

    #: Null while the code is unspent. Set once, when the code is spent; a second claim
    #: against the same code reads this and is refused.
    claimed_at: Mapped[datetime | None] = mapped_column(UtcDateTime(timezone=True), nullable=True)

    #: SHA-256 of the long-lived credential the device authenticates with, issued when the
    #: claim code is spent (ENG-443). Null until then. The credential itself is returned
    #: once, at claim, and never stored — so this is the only trace of it that survives.
    credential_hash: Mapped[str | None] = mapped_column(
        String(64), unique=True, index=True, nullable=True
    )
    credential_issued_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime(timezone=True), nullable=True
    )

    #: When the tablet itself came and took a credential (ENG-622). Distinct from
    #: ``credential_issued_at`` above: issuing is something the server did, collecting is
    #: something the device did, and only the second may happen once. This is the column
    #: the collection route's guarded write tests for NULL, which is what makes it
    #: exactly-once rather than a check a second caller can race past.
    credential_collected_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime(timezone=True), nullable=True
    )

    #: The credential this device held before its last rotation, still good until the new
    #: one is used once. Cleared by that first use. Null the rest of the time — see
    #: ``rotate_device_credential`` for why the window closes on evidence and not a clock.
    previous_credential_hash: Mapped[str | None] = mapped_column(
        String(64), index=True, nullable=True
    )

    #: The hash of a credential that was revoked, kept so a revoked device can be told
    #: apart from one presenting a string that was never issued. **The lookup that
    #: authenticates never reads this column**; only the refusal path does, and only to
    #: choose which refusal. Writing it does not weaken ENG-444's revocation, because
    #: nothing authenticates against it.
    revoked_credential_hash: Mapped[str | None] = mapped_column(
        String(64), index=True, nullable=True
    )

    #: When a facilitator took this device out of service (ENG-444). Set once, and it is
    #: what every read path filters on — an unlinked device is gone from the Desk without
    #: its row being gone from the table. ``credential_hash`` is nulled at the same moment,
    #: which is what actually stops it authenticating; this column is the record, not the
    #: revocation.
    unlinked_at: Mapped[datetime | None] = mapped_column(UtcDateTime(timezone=True), nullable=True)

    #: The last time this device asked the API anything. Null until it does. Nothing but
    #: ``GET /api/devices/me`` moves it, because that is the only request a device makes.
    last_seen_at: Mapped[datetime | None] = mapped_column(UtcDateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
