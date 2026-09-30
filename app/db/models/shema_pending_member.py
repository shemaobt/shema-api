"""The people a pending project proposes — who the Admin will invite when confirming (OBT-547).

When the mesa approves a request that came by the Admin's link, the project it files carries the
form's team table (A4: a name and a role per row) and the address of the link itself — the person
who asked, whose e-mail the platform already has. The A4 has **no e-mail** column in any request
type, so every row but the link's starts with an empty one and the Admin completes it in the
conference. These rows are that list, in the order the form gave it.

**A proposal and never a membership.** Nothing here reaches anything: a membership is an account
on ``shema_project_members`` (OBT-524), and confirming turns each row with an e-mail into one — or
into an invitation, for an address with no account. The rows stay afterwards as what the form
proposed, read by nobody once the project is confirmed.

Text and not ``String(n)``: the form bounds neither column, and a row refused at the mesa's
approval would fail the decision for a name that was simply long.
"""

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ShemaProjectPendingMember(Base):
    """One person a pending project proposes, as the form named them."""

    __tablename__ = "shema_project_pending_members"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("shema_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: Where the row sat in the form's table, the link's own address last.
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(Text, default="", server_default="")
    #: The A4's *Papel / função*, as typed.
    role: Mapped[str] = mapped_column(Text, default="", server_default="")
    #: Empty for every A4 row; the link's address for the link's own row.
    email: Mapped[str] = mapped_column(String(320), default="", server_default="")
