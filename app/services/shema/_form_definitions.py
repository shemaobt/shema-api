"""Publishing a field spec as a version, and reading back the version an answer was given to.

**A definition edited in place rewrites the meaning of every past answer.** The words the
answers were given to are gone, nothing records that they moved, and a submission filed under
*"how many chapters this month"* is read a year later under *"how many chapters in total"*.
That is the failure this file exists to prevent, and the shape of the fix is that a version is
**cut, never edited**: ``publish_definition`` inserts a new row when the spec's content has
moved and reuses the standing one when it has not.

**The spec is authored in** ``app/utils/shema_forms.py``, **not here and not in a table.**
OBT-401 puts a form builder out of scope in its own words — *definitions are configured, not
designed in-app* — so there is no endpoint that writes this table and no migration that seeds
it. What there is instead is a file somebody edits in a pull request, and this, which notices.

**Publishing happens on the authenticated write and never on the public read.** A link is
minted by a coordinator, and that is where the current spec is published and pinned; ``GET
/api/shema/intake/{token}`` then only reads. The alternative — publish on first use — would
put an ``INSERT`` on the module's one unauthenticated route, which is the route that will be
found.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.shema_form import ShemaFormDefinition
from app.utils.shema_forms import field_specs, spec_hash


async def publish_definition(db: AsyncSession, kind: str) -> ShemaFormDefinition:
    """The standing version of ``kind``'s spec, cutting a new one if the file has moved.

    **Staged, not committed.** The caller owns the transaction — minting a link writes the
    definition and the link together or neither, which is what keeps a link from pointing at a
    version that rolled back. ``flush`` is what gives the new row its id without closing the
    transaction, and it is also what makes the unique index on ``(kind, content_hash)`` fire
    here rather than at somebody else's commit.

    ``ValueError`` on an unknown kind rather than a business exception: the argument is a
    module constant, never a client's string, so reaching this line is a programming error and
    an HTTP status would be dressing one up as a user's mistake.
    """
    spec = field_specs(kind)
    if not spec:
        raise ValueError(f"{kind}: no field spec is published for this kind")

    content = spec_hash(spec)
    standing = (
        await db.execute(
            select(ShemaFormDefinition)
            .where(ShemaFormDefinition.kind == kind)
            .order_by(ShemaFormDefinition.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if standing is not None and standing.content_hash == content:
        return standing

    definition = ShemaFormDefinition(
        kind=kind,
        version=1 if standing is None else standing.version + 1,
        fields=spec,
        content_hash=content,
    )
    db.add(definition)
    await db.flush()
    return definition


async def current_definition(db: AsyncSession, kind: str) -> ShemaFormDefinition | None:
    """The newest published version of ``kind``, or ``None`` when nothing is published yet.

    A read, with no side effect: a caller that wants the spec published asks
    :func:`publish_definition`, and the two are separate so that no read path can write.
    """
    return (
        await db.execute(
            select(ShemaFormDefinition)
            .where(ShemaFormDefinition.kind == kind)
            .order_by(ShemaFormDefinition.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


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
