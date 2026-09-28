"""The trail of every change to an account's region scope — OBT-543.

``shema_user_regions`` is the scope as it stands, and ``set_region_scope`` replaces it in
place: a region that leaves an account is a deleted row, and a region that stays keeps the
``granted_at`` it had. So the table answers *how far does this account reach* and nothing
about how it came to. The Admin's surface (``docs/shema.md``, *The Admin grants*) owes a
history of every grant and revocation with its author and date, and for a regional role the
region **is** the grant: moving a coordinator from one region to another writes no role row
at all. This table is where that move is recorded.

**Append-only, by the same trigger the module's other two trails use** (``docs/shema.md``
§7.2), and written by ``set_region_scope`` alone — the scope's only writer — so every path
that changes a scope leaves a row whether or not its author remembered: the Admin's grant and
revocation, an accepted invite, an operator.

**No foreign key on either account column, and that is the trigger's consequence rather than
a shortcut.** ``ON DELETE SET NULL`` is an UPDATE and ``CASCADE`` is a DELETE, and this table
refuses both — so either one would make deleting an account raise from a module nobody was
touching. The ids are kept as the event recorded them; the names are resolved when the trail
is read, and an account that no longer exists reads without one.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Index, String, event
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.db.models.shema_enums import REGION_KEY, ShemaRegionKey, guard_append_only
from app.db.types import UtcDateTime


class ShemaScopeChange(Base):
    """One region entering or leaving one account's scope, by whom and when.

    ``changed_at`` is stamped from Python as well as from the server, for the reason
    ``ShemaRoleChange`` gives: ``func.now()`` is the transaction's clock, and a scope replaced
    in one call writes several rows that a trail read in order must not tie on.
    """

    __tablename__ = "shema_scope_changes"
    __table_args__ = (Index("ix_shema_scope_changes_changed_at", "changed_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    region_key: Mapped[ShemaRegionKey] = mapped_column(REGION_KEY, nullable=False)
    #: True when the region entered the scope, False when it left it.
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    changed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )


event.listen(ShemaScopeChange.__table__, "after_create", guard_append_only)
