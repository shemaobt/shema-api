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
"""

from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.shema import ShemaProject
from app.db.models.shema_form import ShemaFormDefinition, ShemaSubmission
from app.models.shema_forms import ReceivedSubmission, ReceivedSubmissionDetail
from app.services.shema._scope import RegionScope, refuse_out_of_scope, visible_projects
from app.services.shema._submission_archive import archived_answers
from app.services.shema.read_intake_form import form_fields
from app.utils.shema_forms import PULSE_KIND
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
    db: AsyncSession, scope: RegionScope, submission_id: str, *, user: User
) -> ReceivedSubmissionDetail:
    """One submission, with the answers as they arrived and the form they answered.

    The form travels beside the answers rather than being looked up by the client, and that is
    the DoD's first line arriving where it can be seen: the questions shown are the ones this
    submission was given, not today's, so an answer stays readable after the form has moved on.
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
        answers=archived_answers(submission),
    )
