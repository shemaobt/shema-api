"""Project members — the account ↔ project link that says who a project's team is (OBT-524).

Until this table, *equipe* was free text on ``shema_projects`` (``team_leader``, ``mentor``,
``translators``) and the only link between an account and a project was regional, through the
org chart. OBT-522 (22 and 25/sep) made the team **the project's members in the PME**, and this is
the table the form (OBT-520), the *Solicitar recurso* button (OBT-544) and the Admin's access
screen (OBT-546) read.

**Its own table, not ``project_user_access``.** That table grants access to Tripod's ``projects``
rows, and a Shemá project is not one (``docs/shema.md`` §4.3): its id is the export's slug and it
has no ``projects`` row to point at.

**Removal marks, it never deletes.** A request a member sent stays the project's after they leave,
which is the same reason OBT-520 stamps the project on a request instead of deriving it — so the
row that says *this person was on this team, from then to then* has to survive the leaving.
``removed_at`` and ``removed_by`` are that mark, and somebody who comes back gets a **new** row:
the history keeps both stays.

**One live row per pair, as a partial unique index.** ``(project_id, user_id)`` repeats across the
history, so the key is a surrogate ``id`` and the uniqueness is written on the live rows only —
``WHERE removed_at IS NULL``, declared for both dialects here because ``Base.metadata.create_all``
builds the suite's SQLite schema from this model, while the migration carries the PostgreSQL half.
``RRAttachment`` is the precedent and says the same thing about its current file.

**``role`` is text under a CHECK, not a native enum.** Only ``equipe`` exists *"por ora"*, and a
vocabulary the client is expected to widen is a column of text (``docs/shema.md`` §7.3): widening
it is swapping this CHECK in a migration, with no ``ALTER TYPE``. The word is the session's
``EQUIPE_ROLE`` (``app/services/shema/_scope.py``), which a live row puts in the PME's session.

**Who added and who removed are ``SET NULL``, not ``RESTRICT``.** A membership is a grant, and the
platform's grant — ``user_app_roles.granted_by`` / ``revoked_by`` — is the precedent. ``RESTRICT``
would make ``delete_user`` (a hard delete) fail for the Admin, who writes every membership there
is; ``SET NULL`` loses the *who* when that account goes, which is the trade the grant makes too.
The member's own account cascades, as ``shema_user_regions`` does: deleting a person deletes their
links. The project cascades as its health readings do — a roster does not outlive its project.
"""

import uuid
from datetime import UTC, datetime
from typing import Final

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.db.types import UtcDateTime

#: The one role a membership carries today. Spelled here because a table model may not import the
#: service layer; ``tests/test_shema/test_project_members.py`` holds it to ``_scope.EQUIPE_ROLE``.
MEMBER_ROLE: Final = "equipe"


class ShemaProjectMember(Base):
    """One stay of one account on one project's team — live while ``removed_at`` is NULL."""

    __tablename__ = "shema_project_members"
    __table_args__ = (
        CheckConstraint("role IN ('equipe')", name="ck_shema_project_members_role"),
        Index(
            "uq_shema_project_members_live",
            "project_id",
            "user_id",
            unique=True,
            postgresql_where=text("removed_at IS NULL"),
            sqlite_where=text("removed_at IS NULL"),
        ),
        Index("ix_shema_project_members_user", "user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("shema_projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    #: The Admin who added the account. Always written; NULL only once that account is deleted.
    added_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    #: Stamped by the ORM from Python on every write through the model, so two rows written under
    #: one commit carry two moments — ``func.now()`` is the transaction's clock and would tie them.
    #: The server default only fills a row inserted outside the model.
    added_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )
    removed_at: Mapped[datetime | None] = mapped_column(UtcDateTime(timezone=True), nullable=True)
    removed_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
