"""The intercessor's exit link — how somebody who cannot log in leaves the network.

``docs/shema.md`` §10 item 8 asked *how someone outside the platform asks to be removed when
they cannot log in*, and the client's answer on 22/sep was *"ainda não existe caminho"*. This
is the path: every send to the network (BE-09) carries a link, and opening it and confirming
erases the person exactly as the Resource Circle's own removal does.

**A table of its own, with a real foreign key — ``docs/shema.md`` §6.7.** The token module is
shared; the row is not. What this row points at is a person in the network, and what *used*
would mean here is *the person is gone* — so there is no ``used_at`` and no ``revoked_at``:

* **Nothing revokes an exit link.** Each send mints its own and every one of them lives its own
  life, so somebody holding an older message can still leave. Revoking the previous link on
  each send would strand exactly that person, and a link that leaks can only do the one thing
  it exists for — remove somebody, which is the safe direction.
* **Nothing is ever *used and kept*.** Spending the link erases the person, and the link goes
  with them by ``ON DELETE CASCADE``: no row survives to say it was used, which is the same
  no-tombstone rule the network's own table states. ``_directory`` reads the state through
  ``app/services/common/tokens/status.py`` with the two absent columns stated as ``None``.

**Only the digest is stored.** The raw value leaves once, in the message it was minted for;
nothing can read it back, and a database dump opens no door.
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.db.types import UtcDateTime


class ShemaIntercessorExitLink(Base):
    """One exit link, minted for one send to one person."""

    __tablename__ = "shema_intercessor_exit_links"
    __table_args__ = (Index("ix_shema_intercessor_exit_links_intercessor", "intercessor_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    intercessor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("shema_intercessors.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now()
    )
