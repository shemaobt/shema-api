"""The intercessor network — FE-44 §9.6's paths, owned by this issue rather than by BE-09.

**The boundary ``docs/shema.md`` §10 item 5 left open, settled.** FE-44 §9.6 groups these
routes with the prayer wall under BE-09; the Linear titles give *"BE-13 · Equipe e
intercessores"* the network, and the design recorded the disagreement instead of picking for
both. The evidence that decides it is in the graph rather than in either document: **INT-10,
*Integrar Equipe e Intercessores*, is blocked by this issue and not by BE-09** — the screen
that consumes this waits on BE-13 — and every line of this issue's Context section is about
this table: contact details, consent, removal, sensitive countries. BE-09 keeps the wall, the
authorization of requests and the Pulse, which is what its own title says.

**The frozen paths stay, the file does not.** These routes live at
``/api/shema/prayer/intercessors``, which is where the console's ``prayerAPI`` namespace
already points, because ownership moved and the contract did not. ``app/api/shema/prayer.py``
stays BE-09's for the wall — the wave's collision rule is *create your own file*, and a router
file is not a URL prefix.

**Read access is narrower than authentication, and it is one role.** Everything here is
``resourceCircle`` — *Intercessor*, the role whose stated responsibility (``CLAUDE.md`` §5.7)
is *pedidos de oração, ora e compartilha com a rede*. ``obtLab``, ``coordinator`` and
``globalStrategist`` are refused, and that is a real consequence rather than an oversight: a
global strategist who needs the network is granted ``resourceCircle`` beside their own role,
which this module explicitly supports — ``docs/shema.md`` §4.2 names a regional coordinator
who is also ``resourceCircle`` as the ordinary case, and it is why grants go through
``grant_app_role`` and never through ``scripts/grant_app_role.py``. An OR guard over two roles
would be the capability map ``_deps.py`` spends four paragraphs refusing, for an OR this
product has not asked for.

A platform admin passes, as they pass every guard in this repository. The cost lands on the
tests and is stated there.

**No region scope.** The network is people around the world with no project and no region
(``docs/shema.md`` §5.7); giving it one would be the ``regionKey`` *"added for convenience"*
that FE-44 §5.5 says a format check would not survive.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.shema._deps import Db, ResourceCircleUser
from app.db.models.shema_consent import ShemaConsentContext
from app.models.shema_intercessor import (
    ConsentGrant,
    IntercessorContact,
    IntercessorCreate,
    IntercessorDirectory,
    IntercessorEntry,
    IntercessorUpdate,
)
from app.services.shema import (
    add_intercessor,
    list_intercessors,
    remove_intercessor,
    reveal_intercessor_contact,
    set_intercessor_consent,
    update_intercessor,
    withdraw_intercessor_consent,
)

router = APIRouter()

_PEOPLE = "/prayer/intercessors"


@router.get(_PEOPLE, response_model=IntercessorDirectory)
async def read_intercessors(user: ResourceCircleUser, db: Db) -> IntercessorDirectory:
    """Everyone who consented to be listed — **with no contact string in the response**.

    The DoD's last line, as a property of the shape rather than of this handler: the
    collection model has no field for a contact, so no future edit to this route can put one
    back by widening a query. Each entry carries the channel and a hint, and
    ``GET {id}/contact`` is how a real one is read, one person at a time.

    ``withheldCount`` says how many people the consent gate removed. FE-44 §8.1 rule 2 makes
    the map announce its withholding for the reason that holds here: a silently incomplete
    list is its own hazard.
    """
    return await list_intercessors(db)


@router.post(_PEOPLE, response_model=IntercessorEntry, status_code=status.HTTP_201_CREATED)
async def create_intercessor(
    payload: IntercessorCreate, user: ResourceCircleUser, db: Db
) -> IntercessorEntry:
    """Add a contact together with the consent that lets the platform hold them.

    ``consentBasis`` is required by the payload, so a person cannot be stored without a
    recorded basis — ``docs/shema.md`` §10 item 8's first question, answered by making the
    alternative unrepresentable rather than by a rule somebody has to follow.
    """
    return await add_intercessor(db, payload=payload, actor=user)


@router.patch(_PEOPLE + "/{intercessor_id}", response_model=IntercessorEntry)
async def edit_intercessor(
    intercessor_id: str, payload: IntercessorUpdate, user: ResourceCircleUser, db: Db
) -> IntercessorEntry:
    """Edit a contact. ``addedAt`` has no field here and survives (FE-44 §9.6)."""
    return await update_intercessor(db, intercessor_id, payload=payload)


@router.delete(
    _PEOPLE + "/{intercessor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def erase_intercessor(intercessor_id: str, user: ResourceCircleUser, db: Db) -> None:
    """**Erase**, not hide: the row and its consents leave storage (``docs/shema.md`` §5.7).

    ``response_model=None`` is not decoration. This module carries
    ``from __future__ import annotations``, so ``-> None`` reaches FastAPI as the string
    ``"None"``, resolves to ``NoneType`` — a truthy class — and the route then asserts that a
    204 must not have a response body. Stating it removes the inference entirely.
    """
    await remove_intercessor(db, intercessor_id, actor=user)


@router.get(_PEOPLE + "/{intercessor_id}/contact", response_model=IntercessorContact)
async def read_intercessor_contact(
    intercessor_id: str, user: ResourceCircleUser, db: Db
) -> IntercessorContact:
    """One contact, for one person. The service logs the read.

    Its own route rather than a query parameter on the collection, because the distinction it
    carries is the point: a bulk read and a single read are different acts with different
    risk, and a flag on one endpoint makes them look like the same act with an option.
    """
    return await reveal_intercessor_contact(db, intercessor_id, actor=user)


@router.put(
    _PEOPLE + "/{intercessor_id}/consents/{context}",
    response_model=IntercessorEntry,
)
async def grant_consent(
    intercessor_id: str,
    context: ShemaConsentContext,
    payload: ConsentGrant,
    user: ResourceCircleUser,
    db: Db,
) -> IntercessorEntry:
    """Record that this person consented to one context, on a stated basis.

    One context per call, because a person is asked one question at a time and an endpoint
    that took three answers at once is a single flag with three fields.
    """
    return await set_intercessor_consent(
        db, intercessor_id, context, basis=payload.basis, actor=user
    )


@router.delete(
    _PEOPLE + "/{intercessor_id}/consents/{context}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def revoke_consent(
    intercessor_id: str,
    context: ShemaConsentContext,
    user: ResourceCircleUser,
    db: Db,
) -> None:
    """Withdraw one consent. Withdrawing ``network`` **erases the person**.

    That is not this route being clever: ``network`` is the consent to being held at all, so
    withdrawing it removes the basis the row exists on, and a contact held with no basis is
    retained personal data. Withdrawing either of the other two narrows and nothing else —
    somebody who leaves the internal directory is still reachable, which is exactly the
    distinction a single flag cannot express.

    **204 either way, and no body.** The alternative was to answer with the updated entry when
    one survives and with nothing when it does not, which is two shapes on one route and, in
    the erasing case, a response describing somebody the request just removed. The caller
    re-reads the directory, which is one request and no ambiguity.
    """
    await withdraw_intercessor_consent(db, intercessor_id, context, actor=user)
