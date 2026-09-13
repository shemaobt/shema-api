"""The coordinator's inbox — the list, and one submission opened.

Without a read the archive is write-only, and *a form that is submitted and never seen is
worse than no form, because the sender believes they have been heard.* The detail read is also
where the answers the import deliberately does not apply — the voice of the field and what is
blocking the team — are actually read by the person who decides what to do about them.

**Scoped like every read in this module**, by joining the submissions to
``visible_projects(scope)`` rather than filtering them afterwards: the predicate is underneath
the query instead of beside it, so a later ``LIMIT`` cannot page past a scope.

**Nothing here is a leaving shape and nothing here names a place.** ``ReceivedSubmission`` is
FE-44's frozen six keys plus two; the detail adds the form and the answers. None of them
declares a field of a place, a base or a contact, so BE-04's route audit has nothing to hold —
which is a fact about the shape rather than an exemption, and it is why this module adds no
line to ``COORDINATION_ROUTES``.

**An answer the import applies is readable on the record, so this read does not serve it — and
that sentence is only true once the import has run.** The rule is the second half, and it is
the half a payload can get wrong in a way nothing notices: what has been applied is on the
record, behind the record's own surface and under the rules that surface already enforces, and
what maps to nothing is readable nowhere else and is the whole reason this read exists. But
between the 202 and the import, an answer that maps to a column is on **no surface at all** —
the record has not been written yet, and this is the only read of the archive.

**So the mapped answers are served exactly in that gap, and only to the caller who closes it.**
Applying a submission writes the chapter counts and the leader's consent level onto the record,
and ``prayerVisibility`` is the sharp one: it arrives through a link with no account behind it,
and applying it is what decides whether the project's prayer request may leave coordination at
all. The whole argument for answering the link with 202 rather than writing the record is that
*a person who can be asked decides* — and showing that person four of the form's seven fields
makes the click a formality instead of a decision. Once ``appliedAt`` is set the gap is closed,
the record is the surface, and this read goes narrow again on its own.

**Going narrow again is not tidiness; it is what keeps withdrawal a withdrawal.** A team that
takes its prayer request back off the record leaves that field empty, and the audit trail
deliberately holds no value for the columns the consent gate owns
(``app/services/shema/_audit.py``). An archive that kept answering with the text would be the
second store the module spends four files refusing, and *consent withdrawn means the text is
erased, not hidden* would be false one route over.

**Every other member reads what maps to nothing, applied or not.** The route is open to **any**
member in the caller's region, because an OBT Lab mentor reads a Pulse as legitimately as a
coordinator does and ``require_role`` cannot say *or* (``app/api/shema/_deps.py`` records why
this module has no capability map). That is also the hole: a ``resourceCircle`` account — the
prayer wall's own audience — must not read an archived prayer request out of this payload for a
team that consented to ``coordenacao`` and nothing more.
``app/services/shema/_consent.py`` guards the **columns**; the archive is a second store and the
gate does not reach into it, so the answer is not to reimplement the gate here but to keep the
archive from answering what the record answers. *An unauthorized prayer request is absent from
all four output paths* stays true of a fifth nobody had counted.

**``may_apply`` is not a second guard and cannot become one.** It is ``coordinator`` — the key
``POST /forms/submissions/{id}/import`` is already guarded on — asked as a value by
``app/api/shema/_deps.py`` and handed down, so the two can never disagree about who applies.
What refuses a caller is still ``CoordinatorUser`` on the route that writes.

**Which answers map to a column is read off the definition**, through
:func:`~app.utils.shema_forms.spec_fields`, so this file names no record column and needs no
allowlist entry in ``tests/test_shema/test_privacy_owners.py``.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.shema import ShemaProject
from app.db.models.shema_form import ShemaFormDefinition, ShemaSubmission
from app.models.shema_forms import ReceivedSubmission, ReceivedSubmissionDetail
from app.services.shema._scope import RegionScope, refuse_out_of_scope, visible_projects
from app.services.shema._submission_archive import archived_answers
from app.services.shema.read_intake_form import form_fields
from app.utils.shema_forms import PULSE_KIND, spec_fields
from app.utils.stored_time import as_utc


def as_received(submission: ShemaSubmission, definition_version: int) -> ReceivedSubmission:
    """One row on the wire — the kind is a constant because only the Pulse is archivable.

    ``kind`` is read off :data:`~app.utils.shema_forms.PULSE_KIND` rather than off a column,
    because there is no column: BE-02 left it out so that a table with one value could not
    invite a second, and a server that archived a ``health`` submission would have landed a
    kind that by definition never travelled (FE-44 §5.7).
    """
    return ReceivedSubmission(
        id=submission.id,
        kind=PULSE_KIND,
        project_id=submission.project_id,
        language_name=submission.language_name,
        submitted_by=submission.submitted_by,
        received_at=as_utc(submission.received_at).date(),
        definition_version=definition_version,
        applied_at=(
            None if submission.applied_at is None else as_utc(submission.applied_at).date()
        ),
    )


def readable_answers(
    definition: ShemaFormDefinition | None,
    answers: dict[str, Any],
    *,
    may_apply: bool,
    pending: bool,
) -> dict[str, Any]:
    """The answers this caller may read — the whole submission only while it is theirs to apply.

    See the module docstring for the argument. In one line: what maps to nothing is for
    everybody, and what maps to a column is for the person about to write it there, for as long
    as the record cannot answer for it.

    **Both conditions, and neither alone.** ``may_apply`` without ``pending`` is an archive
    answering what the record already answers, which is how a withdrawn prayer request stays
    readable one route over; ``pending`` without ``may_apply`` is the prayer wall's own audience
    reading a request nobody consented to share with it.

    A definition that cannot be resolved answers **nothing** rather than everything, which is
    the fail-closed direction and costs a coordinator a click through to the record. It is
    checked first, so an unreadable spec is not a reason to serve the archive whole to the one
    caller who happens to hold the role.
    """
    if definition is None:
        return {}
    if may_apply and pending:
        return answers
    unmapped = {field.key for field in spec_fields(definition.fields) if field.column is None}
    return {key: value for key, value in answers.items() if key in unmapped}


def _scoped(scope: RegionScope) -> Select[tuple[ShemaSubmission, int]]:
    """Submissions joined to their project and their definition, inside the caller's reach."""
    return (
        select(ShemaSubmission, ShemaFormDefinition.version)
        .join(ShemaFormDefinition, ShemaFormDefinition.id == ShemaSubmission.definition_id)
        .join(ShemaProject, ShemaProject.id == ShemaSubmission.project_id)
        .where(ShemaProject.id.in_(select(visible_projects(scope).subquery().c.id)))
    )


async def list_submissions(
    db: AsyncSession, scope: RegionScope, *, project_id: str | None = None
) -> list[ReceivedSubmission]:
    """Everything received for the projects the caller reaches, newest first.

    Ordered by the stored moment and not by the day on the wire: ``receivedAt`` is a calendar
    day because FE-44 §9.0 makes every date on this wire one, and two Pulses that arrive on the
    same day still have an order the inbox should show them in.
    """
    stmt = _scoped(scope).order_by(ShemaSubmission.received_at.desc())
    if project_id is not None:
        stmt = stmt.where(ShemaSubmission.project_id == project_id)
    return [
        as_received(submission, version) for submission, version in (await db.execute(stmt)).all()
    ]


async def read_submission(
    db: AsyncSession,
    scope: RegionScope,
    submission_id: str,
    *,
    user: User,
    may_apply: bool = False,
) -> ReceivedSubmissionDetail:
    """One submission, with the answers as they arrived and the form they answered.

    The form travels beside the answers rather than being looked up by the client, and that is
    the DoD's first line arriving where it can be seen: the questions shown are the ones this
    submission was given, not today's, so an answer stays readable after the form has moved on.

    ``may_apply`` **defaults to false**, which is the narrow payload. A caller that forgets to
    pass it shows less than it could rather than more than it should, and the one caller that
    passes it is the router, from the role dependency beside the guard on the write. *Pending*
    is not a parameter for the same reason in reverse: it is a fact about the row this function
    has just read, so there is nothing for a caller to get wrong about it.
    """
    row = (await db.execute(_scoped(scope).where(ShemaSubmission.id == submission_id))).first()
    if row is None:
        raise refuse_out_of_scope(
            scope, user=user, operation="read_submission", project_id=submission_id
        )

    submission, version = row
    definition = await db.get(ShemaFormDefinition, submission.definition_id)
    received = as_received(submission, version)
    return ReceivedSubmissionDetail(
        **received.model_dump(),
        fields=[] if definition is None else form_fields(definition),
        answers=readable_answers(
            definition,
            archived_answers(submission),
            may_apply=may_apply,
            pending=submission.applied_at is None,
        ),
    )
