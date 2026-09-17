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

**BE-13 owns the network, and answered the first of the three.** ``docs/shema.md`` §10 item 5
left the aggregate with two owners; the settlement and its evidence are in BE-13's pull
request, and the short form is that INT-10 — *Integrar Equipe e Intercessores* — is blocked
by this issue and not by BE-09. The consent that was owed is
``app/db/models/shema_consent.py``, a row per person per context, and it is not a column here
on purpose: ``add_intercessor`` will not create a row in this table without one, which is the
rule written where it can be seen rather than in a service somebody has to remember.

The other two are still owed and neither is a schema question. Named again here, because this
is the file the next person opens.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, String, text
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

    ``sensitive_country`` is BE-13's, and it is the project flag's shape rather than a second
    idea of danger. ``CLAUDE.md`` §6.1 asks that the rule be treated as a cross-cutting
    invariant that every new output surface goes through, and FE-44 §8.1 rule 5 already
    extends it from ``location`` to the record's three personal contacts. A person in the
    network is the same kind of subject with none of the project around them, so the flag
    travels on their own row. **Entered, never derived**: the project's is entered too, and
    the only way to derive one here would be to map 249 alpha-2 codes onto the export's
    free-text country spellings — the normalisation ``docs/shema.md`` §4.9 forbids by name.
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
    #: Withheld in every shape that leaves coordination, never on the read the Resource
    #: Circle works from. ``app/services/shema/_directory.py`` is the one owner of both
    #: halves of that split.
    sensitive_country: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    added_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now()
    )
