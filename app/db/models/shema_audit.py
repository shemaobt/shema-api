"""The edit trail — who changed which field of a record, when, and from what to what.

``docs/shema.md`` §5.1 gives the record's lifecycle to BE-06 and the issue gives it one line
that no other aggregate has: *audit who changed what; author and timestamp on every write*.
This is that line as a table, and its shape is the sibling's —
``rr_request_field_history`` (``docs/resource_requests.md`` §4.4) carries the same five
facts for the same reason, answered there by a client gate (*"sim, sempre mantenha os
históricos das mudanças"*) and here by the product: ten tabs and several coordinators write
one row, so *what did the save actually change* is a question somebody asks about every
write.

**Two things it is not.** It is not ``shema_progress_history``, which is a derived record of
what the counts *were* and is read by the ETEN report — that table answers *what was true on
a date* and this one answers *who moved it*. And it is not a second copy of the record: a
trail that could reconstruct the row would be a second store with different readers, which is
precisely what the module spends four files refusing.

**The values of a guarded field are not in the trail, and the field key is.** A change to
``location``, to a contact or to the sensitive flag records *that* the field moved, by whom
and when, with ``old_value`` and ``new_value`` NULL. ``app/services/shema/_redaction.py``
owns which fields those are and ``app/services/shema/_audit.py`` asks it. The argument is
``log_reference``'s, one layer along: a trail is read by more people and kept longer than a
response body, and a country copied into it has left the one boundary the module holds. What
is lost is small and stated — a reader of the trail learns that the place changed and goes to
the record, where being allowed is checked.

**``changed_by`` is nullable and ``changed_by_name`` is not**, which is the one departure
from the sibling's own rule (*"a record of who changed something is worth nothing if the who
can be forgotten"*, hence ``NOT NULL`` there). This module has a write path that is
deliberately unauthenticated by design — BE-12's intake link, ``docs/shema.md`` §6.6 — and a
``NOT NULL`` account id would either refuse that write or invite a service account standing
in for a field leader, which is worse than an honest NULL. So the **name** is always
recorded and the **account** whenever there is one, and the two together say which kind of
write this was without a flag column to get wrong.

**Append-only in the database**, through the trigger pair ``shema_progress_history`` and
``shema_role_changes`` already use (``app/db/models/shema_enums.py``). A history whose rows
can be edited answers nothing — the sibling's sentence, and the reason the rule is DDL here
rather than a convention the second writer inherits by reading this docstring.
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.db.models.shema_enums import guard_append_only
from app.db.types import UtcDateTime


class ShemaRecordEdit(Base):
    """One field of one record, moved by one person in one save.

    **The row is keyed by the version the save produced**, not only by a timestamp, and that
    is what makes the trail answerable rather than merely readable. A client that saved from
    version 7 and was refused asks *what happened between 7 and now*; a timestamp cannot
    answer that without trusting two clocks, and ``version > 7`` can. It is also what groups
    the rows of one save: every field a single ``PATCH`` moved carries the same version.

    ``old_value`` and ``new_value`` are nullable **text**, both sides, for the sibling's
    reasons — a field that had no value has no old side, and the record's fields are strings,
    integers, booleans, dates and JSON arrays, so a trail that recorded only some of them is
    not a trail. Rendering is the reader's; what is stored is what ``str`` gave, and ``None``
    means *there was nothing* or *this field's values are not recorded* (the module
    docstring's guarded case), which the field key tells apart.

    ``changed_at`` is the server's clock and **not** Python's, which is the opposite of the
    choice ``shema_progress_history`` made one file over, and deliberately: there the tie
    ``func.now()`` produces between rows written in one transaction was the defect, because
    each entry is its own event. Here the rows of one save **are** one event and sharing a
    microsecond is the truth about them; ``version`` is what orders one save against the
    next.
    """

    __tablename__ = "shema_record_edits"
    __table_args__ = (
        Index("ix_shema_record_edits_project_version", "project_id", "version"),
        Index("ix_shema_record_edits_changed_at", "changed_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("shema_projects.id", ondelete="RESTRICT"), nullable=False
    )
    #: The record's version **after** this save. Every field one save moved shares it.
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    #: The record's field, in the wire spelling the console reads
    #: (``statusComments``) — not the column name. A key space, like the sibling's: the
    #: record's fields already live in two homes (columns and JSON arrays on the row) and a
    #: later tab will put one in a third, where a design keyed on a column reaches only the
    #: first.
    field_key: Mapped[str] = mapped_column(String(80), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: The account, when there was one. NULL is the unauthenticated intake — see the module
    #: docstring. ``RESTRICT`` for the sibling's reason: a *who* that can be deleted is not a
    #: record of anything.
    changed_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    #: The actor's name **as it was then**, which is the third stored copy of a person's name
    #: this module holds and is correct for the same reason the other two are
    #: (``ShemaMediaItem.authorized_by``, ``ShemaRoleChange.changed_by``): it records who
    #: acted under the name they had, and a rename does not change who acted.
    changed_by_name: Mapped[str] = mapped_column(String(200), nullable=False)

    changed_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now()
    )


event.listen(ShemaRecordEdit.__table__, "after_create", guard_append_only)
