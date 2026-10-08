"""The people half of the module's privacy seam: consent, contact, and a person's country.

``docs/shema.md`` §6.4 gives BE-04 three owners — ``_redaction.py`` for the sensitive country,
``_consent.py`` for the three prayer columns, ``_media_sharing.py`` for per-item authorization
— each the **sole reader of what it guards**, because *a rule applied per endpoint is a rule
the next endpoint forgets*. This is the fourth, and it exists for the same reason on a
different subject: those three guard facts about a project, and the intercessor network is a
table of people who are in no project and will never sign in.

**This is the only file in** ``app/services/shema/`` **and** ``app/api/shema/`` **that names**
``ShemaIntercessor``, ``ShemaIntercessorConsent`` **or** ``ShemaIntercessorExitLink``, and
``tests/test_shema/test_people_privacy.py`` globs both packages and fails on a second one. One
token, checked by a glob, is the mechanism — the sibling's
``test_the_app_key_is_named_once_in_the_module`` applied to a table instead of a literal. The
services beside this one take ids and payloads and get shapes back, so a query that reads a
contact is not a thing any of them can write.

That is why the whole small lifecycle lives here rather than only the reads. Splitting it —
the guarded reads here, the writes next door — would have given the glob two files to allow,
and a rule with an exception list is the rule the next exception joins.

**Four rules this file is the whole of.**

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

*A contact is reviewed after a year, and a person may leave without an account* (OBT-531, the
client's answers of 22/sep to ``docs/shema.md`` §10 item 8). :func:`review_due` is the one
reading of the year — the latest of entry, review and send — and the exit link's rows are
stored and read here by their **digest only**: ``leave_intercessor.py`` mints the token and
hands this file ``tokens.digest(raw)``, so the owner of the tables never holds a raw token.
Leaving is :func:`_erase`, the same statement removal is, and every link that does not open
anything is refused with **one** sentence, whatever the reason — a forwarded link must not tell
whoever holds it whether the person is still in the network.

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

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Final, NamedTuple

from sqlalchemy import Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError
from app.db.models.shema_consent import ShemaConsentContext, ShemaIntercessorConsent
from app.db.models.shema_exit_link import ShemaIntercessorExitLink
from app.db.models.shema_intercessor import ShemaIntercessor
from app.models.shema_intercessor import Consent, IntercessorEntry
from app.services.common import tokens
from app.services.shema._scope import ADMIN_ROLE, COORDINATOR_ROLE, RESOURCE_CIRCLE_ROLE
from app.utils.shema_contacts import contact_channel, contact_hint
from app.utils.stored_time import as_utc

__all__ = [
    "DEAD_EXIT_LINK",
    "REVIEW_AFTER",
    "LeavingPerson",
    "check_exit_link",
    "contact_channel",
    "contact_hint",
    "count_review_due",
    "count_withheld",
    "create_person",
    "edit_person",
    "entries_of",
    "entry_of",
    "erase_person",
    "leave_through_exit_link",
    "leaving_directory",
    "leaving_person",
    "listable_ids",
    "mark_reviewed",
    "people_lacking",
    "record_consent",
    "record_where_missing",
    "revealed_contact",
    "review_due",
    "store_exit_link",
    "with_consent",
    "withdraw_consent",
]

#: Who writes the network — adds, edits, erases, marks a review, records or withdraws a
#: consent (OBT-574). Karina, via Daniel, 6/out/2026, question 4a: *"Somente a coordenação tem
#: acesso editar e apagar o contato do intercessor. O Resource Circle pode ver, mas não edita."*
#: Coordination and the Admin; *não edita* is read whole for the Circle, as Daniel read *só não
#: podem editar* on OBT-571 — no write, on no route.
NETWORK_WRITERS: Final = frozenset({COORDINATOR_ROLE, ADMIN_ROLE})

#: Who reads it — the list and one contact at a time: the writers, who read what they edit, and
#: the Resource Circle. The network has no region (``docs/shema.md`` §5.7), so each of them reads
#: all of it. Written as the writers plus one, as ``_health_audience.HEALTH_READERS`` is.
NETWORK_READERS: Final = NETWORK_WRITERS | {RESOURCE_CIRCLE_ROLE}

#: How long a contact may go unused before it is due for review — the client's answer of
#: 22/sep (4.3), *revisar depois de um ano*. Strictly more than this, measured from the latest
#: of entry, review and send.
REVIEW_AFTER: Final = timedelta(days=365)

#: The one answer to an exit link that opens nothing — unknown, expired, or its person already
#: gone. One sentence on purpose: telling *expired* from *already left* would tell whoever holds
#: a forwarded link whether the person is still in the network.
DEAD_EXIT_LINK: Final = (
    "This link is no longer active. If you have already left the network, there is nothing "
    "more to do; otherwise use the link in the most recent message you received."
)


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
    person reviewing the record reads. It does not move the one-year clock, which is
    :func:`review_due`'s and is reset only by an explicit review (OBT-531).

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
    """Delete the row. The consents and the exit links go with it by ``ON DELETE CASCADE``."""
    await _erase(db, await _person(db, intercessor_id))


async def _erase(db: AsyncSession, person: ShemaIntercessor) -> None:
    """**The** erasure of the module — removal, withdrawal of ``network`` and leaving by link.

    One statement: every table that holds anything about the person hangs off this row by
    ``ON DELETE CASCADE``, so nothing is swept and nothing can be forgotten.
    """
    await db.delete(person)
    await db.commit()


def _in_the_network() -> Select[tuple[str]]:
    """The people in the network: those holding the ``network`` consent, the ladder's floor.

    **Not every row.** ``add_intercessor`` stores nobody without the consent and withdrawing it
    erases the person, but a network imported in bulk arrives without one — the rows OBT-531's
    batch-consent script exists for, and nothing has run it. A row with no basis is retained
    data and not a member, so the counts the directory announces leave it out (OBT-556):
    telling the Resource Circle that somebody exists who never agreed even to be reached is the
    announcement the consent was meant to make impossible.
    """
    return select(ShemaIntercessorConsent.intercessor_id).where(
        ShemaIntercessorConsent.context == ShemaConsentContext.NETWORK
    )


async def count_withheld(db: AsyncSession, *, excluding: Sequence[str]) -> int:
    """How many people in the network the directory does not list — **a number, never a name**.

    The directory's caller passes the ids it lists, so this counts the members it withholds: the
    people holding ``network`` and not ``directory``. Counted in the database, so nothing that
    identifies one of them is loaded into the process.
    """
    stmt = (
        select(func.count())
        .select_from(ShemaIntercessor)
        .where(ShemaIntercessor.id.in_(_in_the_network()))
    )
    if excluding:
        stmt = stmt.where(ShemaIntercessor.id.not_in(excluding))
    return int((await db.execute(stmt)).scalar_one())


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


async def entry_of(
    db: AsyncSession, intercessor_id: str, *, now: datetime | None = None
) -> IntercessorEntry:
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
    return _entry(person, list(rows), now=now or datetime.now(UTC))


async def entries_of(
    db: AsyncSession, ids: list[str], *, now: datetime | None = None
) -> list[IntercessorEntry]:
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
    moment = now or datetime.now(UTC)
    return [
        _entry(people[person_id], consents.get(person_id, []), now=moment)
        for person_id in ids
        if person_id in people
    ]


def _entry(
    person: ShemaIntercessor, rows: list[ShemaIntercessorConsent], *, now: datetime
) -> IntercessorEntry:
    """The one assembly of a collection entry, shared by the single and the batched read."""
    return IntercessorEntry(
        id=person.id,
        name=person.name,
        country=person.country,
        contactChannel=contact_channel(person.contact),
        contactHint=contact_hint(person.contact),
        sensitiveCountry=person.sensitive_country,
        addedAt=as_utc(person.added_at).date(),
        reviewedAt=_day(person.reviewed_at),
        lastSentAt=_day(person.last_sent_at),
        reviewDue=review_due(person.added_at, person.reviewed_at, person.last_sent_at, now=now),
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
    """The real string, for one person, one call — and only for somebody in the directory.

    Deliberately a **named act** with one call site rather than an attribute access that reads
    like any other. The audit line is ``reveal_intercessor_contact.py``'s, at the call, where
    the caller and the reason are in hand; logging here would record a read that a future
    in-process caller has no user for.

    **The gate is here, with the read** (OBT-574), as :func:`listable_ids` is the list's: Karina,
    via Daniel, 6/out/2026, question 4b — the contact is shown only to somebody who *"precisa ter
    aceitado aparecer no diretório"*. ``network`` is the consent to being held and reached by the
    Pulse; ``directory`` is the consent to being looked up by the people who read the network,
    and reading one contact is looking it up. So a person who only receives the Pulse has their
    contact shown to nobody, whoever asks. **And ``network`` is still asked**, beside it: it is
    the consent to being held at all, and nothing in the consent table makes ``directory`` imply
    it — :func:`record_consent` reads only that the person exists, so a row that came in by any
    path but :func:`create_person` could hold ``directory`` alone. Both, so the gate does not
    rest on a convention about who writes the rows. The 404 for an unknown id comes first, so
    the refusals cannot disagree about whether the row exists.
    """
    person = await _person(db, intercessor_id)
    if not await with_consent(db, ShemaConsentContext.NETWORK, ids=[intercessor_id]):
        raise AuthorizationError(
            "This contact has no standing consent to be held and reached by the network."
        )
    if not await with_consent(db, ShemaConsentContext.DIRECTORY, ids=[intercessor_id]):
        raise AuthorizationError(
            "This person has not consented to appear in the directory, so their contact is "
            "shown to nobody."
        )
    return person.contact


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


# --- the one-year review (OBT-531) ------------------------------------------------------


def _day(moment: datetime | None) -> date | None:
    """A stored moment as the UTC day the wire carries, or ``None``."""
    return None if moment is None else as_utc(moment).date()


def review_due(
    added_at: datetime,
    reviewed_at: datetime | None,
    last_sent_at: datetime | None,
    *,
    now: datetime,
) -> bool:
    """Whether more than :data:`REVIEW_AFTER` has passed since the latest of the three moments.

    **The one reading of the year**, for the entry a list carries and for the count of the
    people no list may show. *More than* is strict: a contact entered exactly a year ago is not
    due yet, and one second later it is. ``None`` is not a moment — a contact nobody reviewed
    and nothing was sent to counts from its entry, which is when the platform began holding it.
    """
    latest = max(as_utc(moment) for moment in (added_at, reviewed_at, last_sent_at) if moment)
    return now - latest > REVIEW_AFTER


async def mark_reviewed(db: AsyncSession, intercessor_id: str, *, now: datetime) -> None:
    """Stamp that a Resource Circle member confirmed this person still belongs.

    Only the stamp moves: not ``added_at``, which is when the platform began holding the person,
    and not a consent, which is what they agreed to and not whether somebody checked.
    """
    person = await _person(db, intercessor_id)
    person.reviewed_at = now
    await db.commit()


async def count_review_due(db: AsyncSession, *, excluding: Sequence[str], now: datetime) -> int:
    """How many people outside ``excluding`` are past their year — **a number, never a name**.

    The directory's caller passes the ids it lists, so this counts the people it withholds —
    among the members of the network, the same people :func:`count_withheld` counts, so the
    second number is always a part of the first. It reads three dates per person and nothing
    else: not an id, a name, a country or a contact reaches the process, and the dates are
    counted through :func:`review_due` and discarded.
    """
    stmt = select(
        ShemaIntercessor.added_at, ShemaIntercessor.reviewed_at, ShemaIntercessor.last_sent_at
    ).where(ShemaIntercessor.id.in_(_in_the_network()))
    if excluding:
        stmt = stmt.where(ShemaIntercessor.id.not_in(excluding))
    return sum(
        review_due(added, reviewed, sent, now=now)
        for added, reviewed, sent in (await db.execute(stmt)).all()
    )


# --- the exit link (OBT-531) --------------------------------------------------------------


@dataclass
class _ExitLinkState:
    """What ``tokens.status`` reads, for a link that is never revoked and never used-and-kept.

    ``app/db/models/shema_exit_link.py`` carries why the two columns do not exist; stating them
    as ``None`` here keeps the one reading of a token's state in the token module rather than a
    clock comparison written again in this file. A plain, mutable dataclass because the
    protocol's members are settable attributes.
    """

    expires_at: datetime
    revoked_at: datetime | None = None
    used_at: datetime | None = None


def _alive(link: ShemaIntercessorExitLink, now: datetime) -> bool:
    return tokens.status(_ExitLinkState(expires_at=link.expires_at), now) == "pending"


async def store_exit_link(
    db: AsyncSession,
    intercessor_id: str,
    *,
    token_hash: str,
    expires_at: datetime,
    now: datetime,
    commit: bool = True,
) -> None:
    """Keep one freshly minted link's digest, and prune the person's links that already died.

    The person is read first, so a link for somebody who does not exist is a 404 naming what
    is missing rather than an ``IntegrityError`` escaping a flush. **No earlier link is
    revoked**: a person may still hold the message it came in, and it keeps working until its
    own clock runs out. The person's links whose clock has run out are deleted here, at their
    next send, so rows do not pile up one per send for ever; a link that expires after the last
    send stays until the person leaves or is removed, and opens nothing meanwhile.

    ``commit=False`` is for a caller minting a whole send in one transaction; whoever passes it
    owns the commit, as ``create_notification``'s flag says.
    """
    await _person(db, intercessor_id)
    held = (
        await db.execute(
            select(ShemaIntercessorExitLink).where(
                ShemaIntercessorExitLink.intercessor_id == intercessor_id
            )
        )
    ).scalars()
    for link in held:
        if not _alive(link, now):
            await db.delete(link)
    db.add(
        ShemaIntercessorExitLink(
            intercessor_id=intercessor_id, token_hash=token_hash, expires_at=expires_at
        )
    )
    if commit:
        await db.commit()
    else:
        await db.flush()


async def _live_exit_link(
    db: AsyncSession, token_hash: str, now: datetime
) -> ShemaIntercessorExitLink:
    """The link this digest names while it still opens something, or the one refusal."""
    link = (
        await db.execute(
            select(ShemaIntercessorExitLink).where(
                ShemaIntercessorExitLink.token_hash == token_hash
            )
        )
    ).scalar_one_or_none()
    if link is None or not _alive(link, now):
        raise NotFoundError(DEAD_EXIT_LINK)
    return link


async def check_exit_link(db: AsyncSession, token_hash: str, *, now: datetime) -> None:
    """Whether this link still lets somebody leave. **Reads only** — changes nothing.

    A link previewer opens every URL it is sent, so the read that backs the confirmation page
    must never be the act; the act is :func:`leave_through_exit_link`.
    """
    await _live_exit_link(db, token_hash, now)


async def leave_through_exit_link(db: AsyncSession, token_hash: str, *, now: datetime) -> str:
    """Erase the person this link belongs to, and answer whose id it was, for the log line.

    Checking and erasing are one function so that the answer is one sentence whichever step
    finds nothing: a second confirmation that arrives after the first erased the person meets a
    missing row, and it is told exactly what an unknown link is told.
    """
    link = await _live_exit_link(db, token_hash, now)
    intercessor_id = link.intercessor_id
    person = await db.get(ShemaIntercessor, intercessor_id)
    if person is None:
        raise NotFoundError(DEAD_EXIT_LINK)
    await _erase(db, person)
    return intercessor_id


# --- consent in a batch (OBT-531) ---------------------------------------------------------


async def people_lacking(db: AsyncSession, context: ShemaConsentContext) -> list[str]:
    """The ids of everybody with no row for ``context``, oldest entry first."""
    has_it = select(ShemaIntercessorConsent.intercessor_id).where(
        ShemaIntercessorConsent.context == context
    )
    stmt = (
        select(ShemaIntercessor.id)
        .where(ShemaIntercessor.id.not_in(has_it))
        .order_by(ShemaIntercessor.added_at, ShemaIntercessor.id)
    )
    return list((await db.execute(stmt)).scalars())


async def record_where_missing(
    db: AsyncSession,
    context: ShemaConsentContext,
    *,
    basis: str,
    recorded_by: str,
) -> int:
    """Record ``context`` for everybody who lacks it, in one transaction, and answer how many.

    **Only inserts.** A consent that already stands keeps its basis and its date — which is the
    opposite of :func:`record_consent`, and it is what makes a batch safe to run twice: the
    second run finds nobody and writes nothing. A batch is one basis stated for many people at
    once, and restamping somebody who answered on their own would overwrite their answer with
    the batch's.
    """
    lacking = await people_lacking(db, context)
    db.add_all(
        ShemaIntercessorConsent(
            intercessor_id=person_id,
            context=context,
            basis=basis.strip(),
            recorded_by=recorded_by,
        )
        for person_id in lacking
    )
    await db.commit()
    return len(lacking)
