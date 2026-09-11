"""The org chart — the single source of who holds which role where, and its audit trail.

FE-44 §5.3 freezes this as the module's one answer to *who is the coordinator for Asia*, with
**four consumers, all by reference**: the record's Team tab, the sidebar's region panel,
Rhythm's meeting cards, and the session itself — the signed-in persona's *name* is resolved
out of this chart, so renaming a role-holder renames who the session says you are. **No other
model stores a role-holder's name.** ``shema_projects`` drops the three export columns that
would have; ``docs/shema.md`` §6.2 explains why a name stored there is a second owner.

Seven regions times three roles is twenty-one seats, and the seed leaves all twenty-one
unassigned on purpose — the prototype's names were real people hardcoded in a file.

**A team change is a write with an audit row, not a silent update.** The audit row is
``ShemaRoleChange``, and it is append-only in the database for the reason ``docs/shema.md``
§7.2 gives: this is the trail that makes the rule true, and a rule that lives in the one
service that writes today is a rule the second writer will not have.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import ForeignKey, Index, String, event
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.db.models.shema_enums import (
    REGION_KEY,
    ROLE_KEY,
    ShemaRegionKey,
    ShemaRoleKey,
    guard_append_only,
)
from app.db.types import UtcDateTime


class ShemaRegionTeam(Base):
    """One seat: a region, a role, and the name of whoever holds it.

    The primary key is ``(region_key, role)`` rather than a surrogate id, which is the whole
    *single source* claim written as a constraint — two rows claiming the coordinator of Asia
    cannot exist, so no reader needs a tie-break and no service needs to enforce uniqueness.

    ``holder_name`` is free text and **empty is a real state**, not a gap: twenty-one seats
    ship unassigned and a region with nobody in a seat is a fact the screen shows.

    ``holder_user_id`` is **BE-13's answer to the question this docstring used to leave
    open**, and the shape of the answer is narrower than the question. The issue's first DoD
    line asks that people be *related to existing users where such a user exists*, and its
    fourth paragraph asks that no second user system be built. A nullable reference does both:
    the seat holder who has a Tripod account is identifiable as that account, the seat holder
    who has none is a name and nothing else, and neither case grows an identity model.

    **It is not the name, and it never becomes the name.** ``holder_name`` stays the single
    source FE-44 §5.3 freezes, with four consumers reading it by reference and the session
    among them. Resolving the seat's name through the account instead would move the fact into
    ``users.display_name``, where renaming a role-holder would be a different act from
    renaming the chart — two owners for one string, which is the defect the whole section
    exists to prevent. The reference answers *which account is this*, and nothing else asks
    it a question.

    **The link belongs to the holder, not to the slot**, so writing a different
    ``holder_name`` clears it in the same statement. That is ``docs/shema.md`` §5.5's rule for
    media authorization — *replacing the artifact resets the decision to undecided* — read on
    a seat: an account left pointing at a name it no longer belongs to is worse than an empty
    column, because it reads as a verified identity. ``app/services/shema/save_region_team.py``
    is where the clearing happens and it is the only writer.

    ``ON DELETE SET NULL``: deleting an account empties the reference and leaves the chart
    standing. A seat is an office of the organisation and an office does not vacate itself
    because somebody's login was removed.
    """

    __tablename__ = "shema_region_teams"

    region_key: Mapped[ShemaRegionKey] = mapped_column(REGION_KEY, primary_key=True)
    role: Mapped[ShemaRoleKey] = mapped_column(ROLE_KEY, primary_key=True)
    holder_name: Mapped[str] = mapped_column(String(200), default="", server_default="")
    #: The Tripod account of whoever holds the seat, when they have one. Never a name source.
    holder_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShemaRoleChange(Base):
    """Who changed which seat, from whom to whom, and when. Append-only.

    All three names here are **snapshots that must not follow a rename**, which is what makes
    them correct copies rather than duplicated state: ``from_name`` and ``to_name`` are who
    the seat held and who it holds as the change recorded them, and ``changed_by`` is the
    acting person's name as it was then. FE-44 §5.3 names ``RoleChange.changedBy`` as one of
    exactly two stored copies of a person's name that the *never duplicate a role-holder's
    name* rule deliberately allows, beside ``MediaAuthorization.by``.

    ``changed_at`` is stamped from Python as well as from the server, for the reason the
    progress trail records: ``func.now()`` is the transaction's clock and ties two rows
    written under one commit, which is exactly what a trail read in order cannot have.
    """

    __tablename__ = "shema_role_changes"
    __table_args__ = (Index("ix_shema_role_changes_region_changed", "region_key", "changed_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    region_key: Mapped[ShemaRegionKey] = mapped_column(REGION_KEY, nullable=False)
    role: Mapped[ShemaRoleKey] = mapped_column(ROLE_KEY, nullable=False)
    from_name: Mapped[str] = mapped_column(String(200), default="", server_default="")
    to_name: Mapped[str] = mapped_column(String(200), default="", server_default="")
    changed_by: Mapped[str] = mapped_column(String(200), default="", server_default="")
    changed_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )


event.listen(ShemaRoleChange.__table__, "after_create", guard_append_only)
