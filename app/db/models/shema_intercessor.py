"""The intercessor network — people around the world who will never sign in.

FE-44 §5.5 and ``docs/shema.md`` §5.7 put one structural rule above every other property of
this table: **it is never joined to roles, in either direction.** The ``resourceCircle`` role
is a platform grant held by one person per region; the network is contacts who have no
account and will never have one, and the frontend asserts the separation structurally in both
directions with a test of its own. A foreign key from here to ``users`` or to
``shema_region_teams`` would be the first step of merging two models that must not merge.

**Removal erases.** No tombstone, no ``removed`` flag, no ``deleted_at``: the contact string
is absent from storage. That is why this file has no soft-delete column — a column that lets
a row be *kept but hidden* is how silent retention starts, and it would be the first thing a
well-meaning follow-up added.

Three questions this table cannot ship without, and they are not engineering questions
(``docs/shema.md`` §10, item 8, owned by BE-09): what consent was given and how it is
evidenced; how someone outside the platform asks to be removed when they cannot log in; and
what happens to a contact nobody has used in a year. The schema is here so BE-09 has
something to build against, and the answers are still owed before it stores a real person.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.db.types import UtcDateTime


class ShemaIntercessor(Base):
    """One contact in the prayer network.

    Two of the three inherited rules are in the schema rather than only in a service, because
    each is a shape rather than a workflow and a service is the second place to be wrong.

    ``country`` is an **ISO 3166-1 alpha-2 code and never prose**, so that the network cannot
    fragment into *Brasil* / *Brazil* / *BR* — three spellings of one country in a list whose
    only use is reaching people in it. ``String(2)`` caps the length and the CHECK is what
    refuses ``''`` and a single letter; the code is uppercased on the way in by the service,
    which is the half a CHECK cannot do portably.

    ``contact`` is **NOT NULL and non-empty**: at least one usable channel or the record is
    refused. The full rule — an e-mail, or eight digits or more — is ``contactChannel``'s and
    belongs to the service, because it is a judgement about a string; what the database holds
    is the floor under it, and it costs nothing since nothing seeds this table.
    """

    __tablename__ = "shema_intercessors"
    __table_args__ = (
        CheckConstraint("length(country) = 2", name="ck_shema_intercessors_country_alpha2"),
        CheckConstraint("length(contact) > 0", name="ck_shema_intercessors_contact_present"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    contact: Mapped[str] = mapped_column(String(300), nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now()
    )
