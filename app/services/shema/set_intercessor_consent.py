"""Stating and withdrawing one consent — the two halves of *per context, not a single flag*.

The DoD's second line asks that consent be recorded per context, and the issue gives the
example it has to survive: *somebody who consented to appear in an internal directory has not
consented to appear in an exported report shared with partners*. These two functions are the
whole of how that is written and unwritten, one question at a time.

**Withdrawing ``network`` erases the person.** It is the consent to being held at all, so its
withdrawal is not a narrowing — it removes the basis on which the row exists, and a contact
held with no basis is retained personal data. Doing it here rather than asking the caller to
make two calls is what makes it true for every caller: a withdrawal that left the row behind
is the *flag-and-retain* FE-44 §8.2 refuses, reached by a different route than a boolean.

**Withdrawing either of the other two narrows and nothing else.** Somebody who leaves the
internal directory is still reachable, which is exactly the distinction a single flag cannot
express; the row goes and the person stays.

The removal path is ``remove_intercessor.py``'s and is not duplicated here — this calls it, so
there is one erasure in the module and one log line for it.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.shema_consent import ShemaConsentContext
from app.models.shema_intercessor import IntercessorEntry
from app.services.shema._directory import entry_of, record_consent, withdraw_consent
from app.services.shema.remove_intercessor import remove_intercessor


async def set_intercessor_consent(
    db: AsyncSession,
    intercessor_id: str,
    context: ShemaConsentContext,
    *,
    basis: str,
    actor: User,
) -> IntercessorEntry:
    """Record that this person consented to this context, on this basis.

    Stating a consent that already stands **restamps** it, because a question asked again and
    answered again is a fresh answer and *when it was last given* is what a retention review
    needs. ``set_region_scope`` deliberately does the opposite for a region grant; the two are
    different facts and the divergence is argued in both docstrings.
    """
    await record_consent(
        db, intercessor_id, context, basis=basis, recorded_by=actor.id, commit=True
    )
    return await entry_of(db, intercessor_id)


async def withdraw_intercessor_consent(
    db: AsyncSession,
    intercessor_id: str,
    context: ShemaConsentContext,
    *,
    actor: User,
) -> None:
    """Delete the consent row — or, for ``network``, the person.

    Answers nothing on either branch. The route is a 204 both ways (its docstring carries the
    argument: two shapes on one route, and in the erasing case a body describing somebody the
    request just removed), so an entry assembled here would be two statements for a value
    nobody reads. A caller that wants the person after a narrowing re-reads the directory.
    """
    if context is ShemaConsentContext.NETWORK:
        await remove_intercessor(db, intercessor_id, actor=actor)
        return

    await withdraw_consent(db, intercessor_id, context, commit=True)
