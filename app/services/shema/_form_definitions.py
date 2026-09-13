"""Publishing a field spec as a version, and reading back the version an answer was given to.

**A definition edited in place rewrites the meaning of every past answer.** The words the
answers were given to are gone, nothing records that they moved, and a submission filed under
*"how many chapters this month"* is read a year later under *"how many chapters in total"*.
That is the failure this file exists to prevent, and the shape of the fix is that a version is
**cut, never edited**: ``publish_definition`` inserts a new row for content this table has
never held and hands back the version that already published it otherwise.

**The spec is authored in** ``app/utils/shema_forms.py``, **not here and not in a table.**
OBT-401 puts a form builder out of scope in its own words — *definitions are configured, not
designed in-app* — so there is no endpoint that writes this table and no migration that seeds
it. What there is instead is a file somebody edits in a pull request, and this, which notices.

**Publishing happens on the authenticated write and never on the public read.** A link is
minted by a coordinator, and that is where the current spec is published and pinned; ``GET
/api/shema/intake/{token}`` then only reads. The alternative — publish on first use — would
put an ``INSERT`` on the module's one unauthenticated route, which is the route that will be
found.

**A version is identified by its content and not by being the newest, and the difference is a
revert.** A label key that changes and then changes back — the ordinary shape of reverting a
pull request — leaves the file saying exactly what version *n-1* published. The unique index on
``(kind, content_hash)`` is what says such a spec is that version rather than a new one, so the
lookup here asks *which version published this content*, not *what is the newest row*. Asking
the second question and inserting on a miss is how this file used to answer 500 to every
``POST /intake-links`` — and to every ``POST /forms/submissions`` that names no version, which
is the half that publishes — from the first revert until somebody edited the spec again,
because the index refused the insert at the ``flush``.

**What follows from that: the newest row is not always the standing one.** After a revert the
file's spec is published as the earlier version and the higher number is history, which is why
:func:`current_definition` asks the content question too. Nothing is renumbered — a version is
cut, never edited, and that holds for the numbers as much as for the words.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.shema_form import ShemaFormDefinition
from app.utils.shema_forms import field_specs, spec_hash


async def publish_definition(db: AsyncSession, kind: str) -> ShemaFormDefinition:
    """The standing version of ``kind``'s spec, cutting a new one if the file has moved.

    **Idempotent by content, which is what makes a revert a version this table already has.**
    The lookup is on ``(kind, content_hash)`` — the unique index itself — so a spec that goes
    back to words it published before is answered with the row that published them, whatever
    has been cut since. Looking at the newest row instead cut a version the index then refused,
    and the refusal landed at the ``flush`` below as a 500 on every mint, and on every import
    that named no version, until the file moved again.

    **Staged, not committed.** The caller owns the transaction — minting a link writes the
    definition and the link together or neither, which is what keeps a link from pointing at a
    version that rolled back. ``flush`` is what gives the new row its id without closing the
    transaction.

    **Two publishes racing on a spec nobody has published yet still meet the index**, exactly as
    two arrivals of the same bytes meet ``shema_submissions``'s — the lookup and the insert are
    not one atomic step, and the loser reaches the caller as a 500 that succeeds on the retry,
    because by then the winner's row is what the lookup finds. The trade is
    ``_submission_archive.py``'s, written down there: a savepoint
    against a window of milliseconds, on a spec edited by a pull request. What is *not* left to
    the race is the deterministic case, which is the one above.

    ``ValueError`` on an unknown kind rather than a business exception: the argument is a
    module constant, never a client's string, so reaching this line is a programming error and
    an HTTP status would be dressing one up as a user's mistake.
    """
    spec = field_specs(kind)
    if not spec:
        raise ValueError(f"{kind}: no field spec is published for this kind")

    content = spec_hash(spec)
    standing = await _published_as(db, kind, content)
    if standing is not None:
        return standing

    newest = (
        await db.execute(
            select(func.max(ShemaFormDefinition.version)).where(ShemaFormDefinition.kind == kind)
        )
    ).scalar_one()
    definition = ShemaFormDefinition(
        kind=kind,
        version=1 if newest is None else newest + 1,
        fields=spec,
        content_hash=content,
    )
    db.add(definition)
    await db.flush()
    return definition


async def _published_as(db: AsyncSession, kind: str, content: str) -> ShemaFormDefinition | None:
    """The version of ``kind`` that published exactly this content, or ``None``.

    One function because the publish and the read must ask the index the same question. Two
    call sites spelling the ``(kind, content_hash)`` lookup themselves is how *the standing
    version* comes to mean one thing on the write path and another on the read.
    """
    return (
        await db.execute(
            select(ShemaFormDefinition).where(
                ShemaFormDefinition.kind == kind,
                ShemaFormDefinition.content_hash == content,
            )
        )
    ).scalar_one_or_none()


async def current_definition(db: AsyncSession, kind: str) -> ShemaFormDefinition | None:
    """The version ``kind``'s spec stands as today, or ``None`` when it is not published yet.

    **The content question and not the newest row**, for the reason the module docstring gives:
    after a revert the file says what an earlier version said, and that earlier row is the one
    :func:`publish_definition` hands out. A reader answering *the highest number* would name a
    version the server is no longer publishing and would disagree with every link minted since.

    A read, with no side effect: a caller that wants the spec published asks
    :func:`publish_definition`, and the two are separate so that no read path can write.
    """
    spec = field_specs(kind)
    if not spec:
        return None
    return await _published_as(db, kind, spec_hash(spec))


async def definition_at(db: AsyncSession, kind: str, version: int) -> ShemaFormDefinition:
    """The exact version an answer was given to, or a refusal naming it.

    Refused rather than resolved to the newest, which is the whole of the DoD's first line: a
    submission quoting a version that was never published is a submission nobody can read, and
    reading it against today's spec would be inventing the words it answered.
    """
    definition = (
        await db.execute(
            select(ShemaFormDefinition).where(
                ShemaFormDefinition.kind == kind, ShemaFormDefinition.version == version
            )
        )
    ).scalar_one_or_none()
    if definition is None:
        raise NotFoundError(f"{kind}: there is no published version {version} of this form")
    return definition
