"""Adding a person to the network — with the consent that makes holding them lawful.

**The row and its basis arrive together or neither arrives.** ``docs/shema.md`` §10 item 8
records the three privacy questions this table cannot ship without and says that *shipping the
storage before answering them is how silent retention starts*. The first of them — what
consent was given and how it is evidenced — is answered by making the alternative
unrepresentable: the payload requires a basis, and the two writes are one transaction, so a
crash between them cannot leave a person stored with none.

The other two are still owed and neither is engineering's: how somebody outside the platform
asks to be removed when they cannot log in, and what happens to a contact nobody has used in a
year. Named again here because this is the function that starts the clock on both.

**The ``network`` consent is the floor and the other two are not granted here.** A person is
asked three separate questions — may we hold and use this contact, may we list you, may you
appear in something that leaves — and answering one is not answering the others. A create that
quietly granted all three would be the single flag this design exists to refuse, wearing three
names.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.shema_consent import ShemaConsentContext
from app.models.shema_intercessor import IntercessorCreate, IntercessorEntry
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
