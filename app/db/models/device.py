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

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


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
    claim_code_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    #: Null while the code is unspent. Set once, when the code is spent; a second claim
    #: against the same code reads this and is refused.
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
