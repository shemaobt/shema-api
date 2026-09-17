"""Consent to be held in the intercessor network, recorded **per context**.

``docs/shema.md`` §10 item 8 is the open question this table answers: *what consent was
given, and how it is evidenced.* It is listed there as one of three that *"are not
engineering questions"*, and that is still true of the other two — how a person outside the
platform asks to be removed when they cannot log in, and what happens to a contact nobody has
used in a year. Neither is answered here. What is answered is the half that **is** a schema
decision and that blocks the other two from ever being answerable: a store that records a
single yes cannot later say *yes to what*.

**Why a row per context and not a column on the person.** The obligation is not one fact.
Someone who agreed that the Resource Circle may write to them has not agreed to be listed on
a screen, and someone listed on a screen has not agreed to be named in a file that leaves for
a partner organisation. A single boolean answers all three with whichever one was asked
first, and the answer it gives is *yes* — which is the failure mode this product exists to
avoid on the project side (``docs/shema.md`` §7.4's two absences) arriving on the person side
by a different door.

**Presence is consent; there is no** ``granted`` **column.** Withdrawal deletes the row. A
``granted = false`` row would be a flag-and-retain, which FE-44 §8.2 refuses by name for a
withdrawn prayer request — *"deleted from that store, never flagged and retained"* — and
§5.7 refuses again for the network itself: *removal erases, no tombstone, no* ``removed``
*flag*. So the absence of a row is a refusal, exactly as the absence of ``prayer_visibility``
is ``coordenacao``: **nothing has to be written to stay out, and something has to be written
to travel.**

The rows go when the person does: ``ON DELETE CASCADE`` from ``shema_intercessors``. A
consent record surviving the record it consents to would be retained personal data whose
subject no longer exists in the system — the precise shape of what §5.7's no-tombstone rule
refuses.

The only reader is ``app/services/shema/_directory.py``, which is why this table has no
service of its own; ``tests/test_shema/test_people_privacy.py`` globs the module and fails on
a second one.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.db.models.shema_enums import _enum_type
from app.db.types import UtcDateTime


class ShemaConsentContext(enum.StrEnum):
    """The three destinations a network contact is asked about, widest reach last.

    **Not in** ``app/db/models/shema_enums.py`` **, and the omission is the decision.** That
    file holds the ten of FE-44's twenty frozen vocabularies that a column stores, and its
    docstring scopes itself to Appendix A. This is not one of them: it is BE-13's own
    vocabulary, invented here because the contract records *when* somebody entered the
    network and not *on what basis* (FE-44 §8.5). Putting it beside the frozen ten would
    claim a provenance it does not have. It still goes through that module's ``_enum_type``,
    so it gets ``values_callable`` and the CHECK the suite's dialect needs
    (``docs/shema.md`` §7.3).

    The three are a ladder and each is asked separately, so no answer implies another:

    ``network``
        The floor. The platform may hold this contact and use it to reach the person with
        prayer requests — which is the whole purpose the record exists for. A row without
        this consent is retained personal data with no basis, so
        ``app/services/shema/add_intercessor.py`` refuses to create one and withdrawing it
        deletes the person.

    ``directory``
        Their entry may be listed to signed-in Shemá staff. Being reachable is not being
        listed: a list is a surface that can be read whole, by more people than the one who
        writes, and a person may want the first without the second.

    ``partner-export``
        They may appear in something that leaves the organisation — a partner report, the
        Pulse. FE-44 §8.4's export allowlist carries no person today, so nothing emits this
        yet; the context exists now because the answer has to be recorded at the moment
        somebody asks the person, not at the moment a file is first written.
    """

    NETWORK = "network"
    DIRECTORY = "directory"
    PARTNER_EXPORT = "partner-export"


CONSENT_CONTEXT = _enum_type(ShemaConsentContext, "shema_consent_context_enum")


class ShemaIntercessorConsent(Base):
    """One person's consent to one context, with what it rests on and who recorded it.

    The primary key is the pair, which is the uniqueness the obligation has rather than a
    constraint beside a surrogate id: there is no such thing as two answers to one question,
    and a second row would be two answers with no tie-break.

    ``basis`` is **NOT NULL and non-empty**, and the CHECK is the point of the column rather
    than defensive typing. It is the *evidence* half of §10 item 8 — *verbal, at the 2026
    regional gathering*, *reply on WhatsApp, 03/mar*, *signed form on file* — and a row
    without it is a yes nobody can stand behind, which is the state this table was added to
    make unrepresentable. The service does not interpret the string; a person reads it when
    somebody asks how the platform came to hold a contact.

    ``recorded_by`` is a **foreign key and not a name**, unlike ``ShemaRoleChange.changed_by``
    beside it. FE-44 §5.3 allows exactly two stored copies of a person's name in this product
    and both are frozen wire shapes a screen renders; this one is neither, so it can be the
    better thing — a reference that stays right when the actor is renamed. It is nullable and
    ``SET NULL`` because losing the actor must never be a reason a consent record is deleted:
    between *who recorded this* and *that this was recorded*, the second is the one the
    subject's rights rest on.
    """

    __tablename__ = "shema_intercessor_consents"
    __table_args__ = (CheckConstraint("length(basis) > 0", name="ck_shema_consents_basis_present"),)

    intercessor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("shema_intercessors.id", ondelete="CASCADE"),
        primary_key=True,
    )
    context: Mapped[ShemaConsentContext] = mapped_column(CONSENT_CONTEXT, primary_key=True)
    #: How the consent was obtained and how it is evidenced, as a person wrote it down.
    basis: Mapped[str] = mapped_column(String(300), nullable=False)
    recorded_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    recorded_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now()
    )
