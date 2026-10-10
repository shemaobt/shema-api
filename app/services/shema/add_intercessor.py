"""Adding a person to the network — with the consent that makes holding them lawful.

**The row and its basis arrive together or neither arrives.** ``docs/shema.md`` §10 item 8
records the three privacy questions this table cannot ship without and says that *shipping the
storage before answering them is how silent retention starts*. The first of them — what
consent was given and how it is evidenced — is answered by making the alternative
unrepresentable: the payload requires a basis, and the two writes are one transaction, so a
crash between them cannot leave a person stored with none.

The other two were answered by the client on 22/sep and built by OBT-531: somebody outside the
platform leaves through an exit link (``leave_intercessor.py``), and a contact nobody has used in
a year is flagged for review (``review_intercessor.py``). This is the function that starts the
clock on both — ``added_at`` is where the year counts from until a review or a send moves it.

**The ``network`` consent is the floor and the other two are not granted here.** A person is
asked three separate questions — may we hold and use this contact, may we list you, may you
appear in something that leaves — and answering one is not answering the others. A create that
quietly granted all three would be the single flag this design exists to refuse, wearing three
names.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.shema_change_log import ChangeAction, ChangeSubject
from app.db.models.shema_consent import ShemaConsentContext
from app.models.shema_intercessor import IntercessorCreate, IntercessorEntry
from app.services.shema import _trail
from app.services.shema._directory import create_person, entry_of, record_consent


async def add_intercessor(
    db: AsyncSession,
    *,
    payload: IntercessorCreate,
    actor: User,
) -> IntercessorEntry:
    """Store one contact and the consent it rests on, in one transaction.

    The payload is already clean — ``app/models/shema_intercessor.py`` uppercases the country,
    checks it against the codes the console offers, and refuses a contact with no usable
    channel, naming the field that failed as FE-44 §9.6 asks. Nothing is re-checked here; what
    this function owns is that the two rows are one act.
    """
    person_id = await create_person(
        db,
        name=payload.name,
        country=payload.country,
        contact=payload.contact,
        sensitive_country=payload.sensitive_country,
    )
    _trail.stage(
        db,
        actor=actor,
        subject=ChangeSubject.INTERCESSOR,
        action=ChangeAction.CREATED,
        subject_id=person_id,
        fields=("name", "country", "contact", "sensitiveCountry"),
    )
    await record_consent(
        db,
        person_id,
        ShemaConsentContext.NETWORK,
        basis=payload.consent_basis,
        recorded_by=actor.id,
        commit=False,
    )
    await db.commit()
    return await entry_of(db, person_id)
