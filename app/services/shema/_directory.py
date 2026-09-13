"""The people half of the module's privacy seam: consent, contact, and a person's country.

``docs/shema.md`` §6.4 gives BE-04 three owners — ``_redaction.py`` for the sensitive country,
``_consent.py`` for the three prayer columns, ``_media_sharing.py`` for per-item authorization
— each the **sole reader of what it guards**, because *a rule applied per endpoint is a rule
the next endpoint forgets*. This is the fourth, and it exists for the same reason on a
different subject: those three guard facts about a project, and the intercessor network is a
table of people who are in no project and will never sign in.

**This is the only file in** ``app/services/shema/`` **and** ``app/api/shema/`` **that names**
``ShemaIntercessor`` **or** ``ShemaIntercessorConsent``, and
``tests/test_shema/test_people_privacy.py`` globs both packages and fails on a second one. One
token, checked by a glob, is the mechanism — the sibling's
``test_the_app_key_is_named_once_in_the_module`` applied to a table instead of a literal. The
services beside this one take ids and payloads and get shapes back, so a query that reads a
contact is not a thing any of them can write.

That is why the whole small lifecycle lives here rather than only the reads. Splitting it —
the guarded reads here, the writes next door — would have given the glob two files to allow,
and a rule with an exception list is the rule the next exception joins.

**Three rules this file is the whole of.**

*Consent is per context and absence is refusal.* A row exists only while the consent stands
(``app/db/models/shema_consent.py`` carries the argument), so every question here is *is there
a row*, never *is the flag true*. Withdrawal deletes, which is FE-44 §8.2's *"deleted from that
store, never flagged and retained"* on a person instead of on a request.

*A contact is for contacting, and a list is not contacting.* The issue's own sentence is that
an endpoint returning every phone number in one call is a data-loss incident waiting for one
compromised session. So a collection never carries a contact: :func:`entry_of` builds the
masked pair, and :func:`revealed_contact` is one person at a time, with
``reveal_intercessor_contact.py`` logging every call.

*A country leaves the way a project's location leaves.* ``docs/shema.md`` §6.4 states the split
once — *redact in the payload on every path that leaves; never on the record read* — and
:func:`leaving_person` is this side of it. The shape is FE-44 §9.6's own, verbatim:
``country: ""`` with the withheld marker beside it, so the redaction travels in the payload and
a renderer downstream cannot leak what the payload does not hold.

The two string rules — what an e-mail is, what a phone is, how much of either a hint keeps —
are in ``app/utils/shema_contacts.py`` and re-exported here, because ``app/models/`` needs the
first to refuse a payload and may not import ``app/services/``. **Reading a contact off a row
is the guarded act**; deciding whether a string looks like a phone number is not.

**Reconciliation with BE-04, which runs beside this issue on the same base.** That issue builds
``_redaction.py`` as the sensitive-country owner for projects. The two do not overlap in code —
no column, no function, no test is touched twice — and the mechanism here is that section's,
not a second one: the same flag, the same withheld marker, the same *never on the record read*
split. Whoever the user merges second folds :func:`leaving_person` into ``_redaction.py`` if
the shapes want to be one function, and the glob moves with it. Nothing here has to change for
that to be a rename.

**A residual this file deliberately does not close.** A withheld person's *name* still travels,
because §6.4's rule withholds a location and FE-44 §9.6 freezes a withheld entry as one that
keeps its other fields. Whether a person's name is itself a location in a dangerous place is
the fourth client gate — ``docs/shema.md`` §9.4, *what devida cautela means per output* — whose
own instruction is to raise it rather than invent it surface by surface. Raised in BE-13's pull
request; not invented here.
"""

from __future__ import annotations

from typing import Any, NamedTuple

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.shema_consent import ShemaConsentContext, ShemaIntercessorConsent
from app.db.models.shema_intercessor import ShemaIntercessor
from app.models.shema_intercessor import Consent, IntercessorEntry
from app.utils.shema_contacts import contact_channel, contact_hint
from app.utils.stored_time import as_utc

__all__ = [
    "LeavingPerson",
    "contact_channel",
    "contact_hint",
    "count_people",
    "create_person",
    "edit_person",
    "entries_of",
    "entry_of",
    "erase_person",
    "leaving_directory",
    "leaving_person",
    "listable_ids",
    "record_consent",
    "revealed_contact",
    "with_consent",
    "withdraw_consent",
]


class LeavingPerson(NamedTuple):
    """A network contact as it may appear in something that leaves coordination.

    **There is no contact field, and that is the shape rather than an omission.** FE-44 §8.4's
    export allowlist carries no personal contact at all, and an allowlist is only a guarantee
    while the thing it protects cannot be reached another way. A leaving shape that *could*
    carry a contact is one edit from carrying one.
    """

    name: str
    #: ``""`` when withheld — FE-44 §9.6's own spelling for a withheld entry.
    country: str
    country_withheld: bool


async def _person(db: AsyncSession, intercessor_id: str) -> ShemaIntercessor:
    """The row, or the refusal. Every operation below starts here so the 404 has one spelling."""
    person = await db.get(ShemaIntercessor, intercessor_id)
    if person is None:
        raise NotFoundError("Intercessor not found")
    return person


# --- consent -------------------------------------------------------------------------


async def with_consent(
    db: AsyncSession,
    context: ShemaConsentContext,
    *,
    ids: list[str] | None = None,
) -> set[str]:
    """Which of these people consented to ``context``. ``ids=None`` asks about everybody.

    A set rather than a filtered query, so a caller already holding rows does not read them
    twice and the gate composes the same way over one person or over a page of them.
    """
    stmt = select(ShemaIntercessorConsent.intercessor_id).where(
        ShemaIntercessorConsent.context == context
    )
    if ids is not None:
        if not ids:
            return set()
        stmt = stmt.where(ShemaIntercessorConsent.intercessor_id.in_(ids))
    return set((await db.execute(stmt)).scalars())


async def record_consent(
    db: AsyncSession,
    intercessor_id: str,
    context: ShemaConsentContext,
    *,
    basis: str,
    recorded_by: str | None,
    commit: bool = True,
) -> None:
    """State one consent, replacing whatever stood for that context before.

    Re-stating a consent **restamps** it, which is the deliberate opposite of
    ``set_region_scope``'s *rows already present keep their* ``granted_at``. The two are
    different facts: a region scope that did not change was not re-granted, while a question
    asked again and answered again is a fresh answer, and *when it was last given* is what a
    retention review actually needs.

    ``commit=False`` is for a caller that owns its transaction — the create path, where the
    person and their first consent arrive together or not at all. The rule is
    ``create_notification``'s and holds here: whoever passes ``False`` owns the commit.

    The subject is read before anything is written, so a consent recorded for somebody who
    does not exist is a 404 naming the thing that is missing. The foreign key would refuse it
    either way — the suite turns SQLite's enforcement on — but it refuses inside a flush,
    which escapes as a 500 for the caller's own bad id. That is the same failure
    :class:`~app.core.exceptions.UnknownReferenceError` exists to prevent, met from the other
    side.
    """
    await _person(db, intercessor_id)
    await db.execute(
        delete(ShemaIntercessorConsent).where(
            ShemaIntercessorConsent.intercessor_id == intercessor_id,
            ShemaIntercessorConsent.context == context,
        )
    )
    db.add(
        ShemaIntercessorConsent(
            intercessor_id=intercessor_id,
            context=context,
            basis=basis.strip(),
            recorded_by=recorded_by,
        )
    )
    if commit:
        await db.commit()
    else:
        await db.flush()


async def withdraw_consent(
    db: AsyncSession,
    intercessor_id: str,
    context: ShemaConsentContext,
    *,
    commit: bool = True,
) -> bool:
    """Delete the row, and answer whether there was one. **No flag is written.**

    The subject is read first for the reason :func:`record_consent` gives: a withdrawal for
    somebody who does not exist is a 404 naming what is missing, and not a 204 about a row
    that was never there.
    """
    await _person(db, intercessor_id)
    result = await db.execute(
        delete(ShemaIntercessorConsent).where(
            ShemaIntercessorConsent.intercessor_id == intercessor_id,
            ShemaIntercessorConsent.context == context,
        )
    )
    if commit:
        await db.commit()
    return bool(result.rowcount)


# --- the rows ------------------------------------------------------------------------


async def create_person(
    db: AsyncSession,
    *,
    name: str,
    country: str,
    contact: str,
    sensitive_country: bool,
    commit: bool = False,
) -> str:
    """Store one contact and answer its id. Defaults to **not** committing.

    The default is the unusual half and it is chosen: the only caller is ``add_intercessor``,
    whose whole point is that the person and their consent are one transaction, and a default
    that committed would make the safe call the longer one.
    """
    person = ShemaIntercessor(
        name=name, country=country, contact=contact, sensitive_country=sensitive_country
    )
    db.add(person)
    await db.flush()
    if commit:
        await db.commit()
    return person.id


async def edit_person(db: AsyncSession, intercessor_id: str, changes: dict[str, Any]) -> None:
    """Apply the fields a partial payload carried; an absent field is not in ``changes``.

    The caller sends ``model_dump(exclude_unset=True)`` rather than a filtered dictionary of
    its own, so *not sent* and *sent as null* stay different answers all the way down —
    ``sensitiveCountry`` is where the difference bites, since a partial edit of a name must
    not silently unflag somebody.
    """
    person = await _person(db, intercessor_id)
    for field, value in changes.items():
        setattr(person, field, value)
    await db.commit()


async def erase_person(db: AsyncSession, intercessor_id: str) -> None:
    """Delete the row. The consents go with it by ``ON DELETE CASCADE``."""
    await db.delete(await _person(db, intercessor_id))
    await db.commit()


async def count_people(db: AsyncSession) -> int:
    """How many are in the network at all — the number a withheld count is taken from."""
    return int((await db.execute(select(func.count()).select_from(ShemaIntercessor))).scalar_one())


async def listable_ids(db: AsyncSession) -> list[str]:
    """The ids a directory read may show, in the order it shows them.

    **The consent gate is the query and not the caller** (FE-44 §8.2's third rule, on a
    person): somebody with no ``directory`` row is absent from the statement, so an endpoint
    cannot forget to filter and a second endpoint cannot filter differently. Ordered by
    country then name, which is how the console groups the network.
    """
    listable = await with_consent(db, ShemaConsentContext.DIRECTORY)
    if not listable:
        return []
    stmt = (
        select(ShemaIntercessor.id)
        .where(ShemaIntercessor.id.in_(sorted(listable)))
        .order_by(ShemaIntercessor.country, ShemaIntercessor.name, ShemaIntercessor.id)
    )
    return list((await db.execute(stmt)).scalars())


# --- what leaves this file -----------------------------------------------------------


async def entry_of(db: AsyncSession, intercessor_id: str) -> IntercessorEntry:
    """One person's **coordination** shape: masked contact, and the consents that stand.

    Coordination, so the country is verbatim — ``docs/shema.md`` §6.4's split says redaction
    belongs to paths that leave and that hiding the truth from the person working the record
    is data loss rather than privacy. The masking of the contact is a different rule and is
    not that split: it is about the *plural*, and it applies here because this shape is what a
    collection is made of.

    The consents ride along because the screen's whole job on this data is to show what
    somebody agreed to. A directory that lists a person without saying on what basis is the
    state ``docs/shema.md`` §10 item 8 calls silent retention, rendered.
    """
    person = await _person(db, intercessor_id)
    rows = (
        await db.execute(
            select(ShemaIntercessorConsent)
            .where(ShemaIntercessorConsent.intercessor_id == intercessor_id)
            .order_by(ShemaIntercessorConsent.recorded_at, ShemaIntercessorConsent.context)
        )
    ).scalars()
    return _entry(person, list(rows))


async def entries_of(db: AsyncSession, ids: list[str]) -> list[IntercessorEntry]:
    """Many people's coordination shape, in the order the ids came — two statements, not 2N.

    The directory is the caller. :func:`listable_ids` answers ids as scalars, so nothing is in
    the identity map and a per-person :func:`entry_of` is a ``db.get`` plus a consent
    ``select`` each — the right cost for one person after a write, and 2N round trips on the
    Resource Circle's network screen, which is the whole consumer of that route. So the rows
    come in one ``select`` over the ids and the consents in one more, grouped by person here;
    :func:`_entry` builds the shape for both paths, so the two cannot drift.

    An id with no row by the time the second statement runs is skipped rather than raised:
    the list was true when it was made, and a person erased in between is exactly somebody
    the directory must not name.
    """
    if not ids:
        return []
    people = {
        person.id: person
        for person in (
            await db.execute(select(ShemaIntercessor).where(ShemaIntercessor.id.in_(ids)))
        ).scalars()
    }
    consents: dict[str, list[ShemaIntercessorConsent]] = {}
    stmt = (
        select(ShemaIntercessorConsent)
        .where(ShemaIntercessorConsent.intercessor_id.in_(ids))
        .order_by(ShemaIntercessorConsent.recorded_at, ShemaIntercessorConsent.context)
    )
    for row in (await db.execute(stmt)).scalars():
        consents.setdefault(row.intercessor_id, []).append(row)
    return [
        _entry(people[person_id], consents.get(person_id, []))
        for person_id in ids
        if person_id in people
    ]


def _entry(person: ShemaIntercessor, rows: list[ShemaIntercessorConsent]) -> IntercessorEntry:
    """The one assembly of a collection entry, shared by the single and the batched read."""
    return IntercessorEntry(
        id=person.id,
        name=person.name,
        country=person.country,
        contactChannel=contact_channel(person.contact),
        contactHint=contact_hint(person.contact),
        sensitiveCountry=person.sensitive_country,
        addedAt=as_utc(person.added_at).date(),
        consents=[
            Consent(
                context=row.context.value,
                basis=row.basis,
                recordedAt=as_utc(row.recorded_at).date(),
            )
            for row in rows
        ],
    )


async def revealed_contact(db: AsyncSession, intercessor_id: str) -> str:
    """The real string, for one person, one call.

    Deliberately a **named act** with one call site rather than an attribute access that reads
    like any other. The audit line is ``reveal_intercessor_contact.py``'s, at the call, where
    the caller and the reason are in hand; logging here would record a read that a future
    in-process caller has no user for.
    """
    return (await _person(db, intercessor_id)).contact


def leaving_person(person: ShemaIntercessor) -> LeavingPerson:
    """One row as a shape that may leave coordination — the country withheld if flagged.

    It does **not** apply the ``partner-export`` gate, which is :func:`leaving_directory`'s.
    Composing the two here would let a caller holding one person skip the gate by reaching for
    the singular.
    """
    if person.sensitive_country:
        return LeavingPerson(name=person.name, country="", country_withheld=True)
    return LeavingPerson(name=person.name, country=person.country, country_withheld=False)


async def leaving_directory(db: AsyncSession) -> list[LeavingPerson]:
    """Everyone who may appear in a file that leaves, redacted — the gate and the shape.

    Nothing calls this yet: no wave-1 output carries a person, and FE-44 §8.4's export
    allowlist has 24 project fields and no people at all. It ships now because the day one
    does, the right thing has to already be the easy thing — the same reason ``docs/shema.md``
    §6.4 schedules BE-04 before anything that emits data.
    """
    allowed = await with_consent(db, ShemaConsentContext.PARTNER_EXPORT)
    if not allowed:
        return []
    stmt = (
        select(ShemaIntercessor)
        .where(ShemaIntercessor.id.in_(sorted(allowed)))
        .order_by(ShemaIntercessor.name, ShemaIntercessor.id)
    )
    return [leaving_person(person) for person in (await db.execute(stmt)).scalars()]
