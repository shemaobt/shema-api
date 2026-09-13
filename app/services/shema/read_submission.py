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

**The detail read answers only the answers that map to no record column, and the rule is one
sentence rather than a list of exceptions.** An answer the import applies is readable on the
record, behind the record's own surface and the rules that surface already enforces; an answer
that maps to nothing is readable nowhere else, and it is the whole reason this read exists —
the voice of the field and what is blocking the team.

The rule is principled and it also closes a hole, which is the honest order to state it in.
This route is open to **any** member in the caller's region, because an OBT Lab mentor reads a
Pulse as legitimately as a coordinator does and ``require_role`` cannot say *or*
(``app/api/shema/_deps.py`` records why this module has no capability map). Without the rule,
a ``resourceCircle`` account — the prayer wall's own audience — could read an archived prayer
request out of this payload for a team that consented to ``coordenacao`` and nothing more.
``app/services/shema/_consent.py`` guards the **columns**; the archive is a second store and
the gate does not reach into it, so the answer is not to reimplement the gate here but to stop
serving what the record already serves. *An unauthorized prayer request is absent from all four
output paths* stays true of a fifth nobody had counted.

**Which answers those are is read off the definition**, whose ``column`` field is the mapping,
so this file names no record column and needs no allowlist entry in
``tests/test_shema/test_privacy_owners.py``.
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


def unapplied_answers(
    definition: ShemaFormDefinition | None, answers: dict[str, Any]
) -> dict[str, Any]:
    """The answers this read may serve — the ones the import applies to no record column.

    See the module docstring for the argument. In one line: what was applied is readable on the
    record, and what maps to nothing is what this read is for.

    A definition that cannot be resolved answers **nothing** rather than everything, which is
    the fail-closed direction and costs a coordinator a click through to the record.
    """
    if definition is None:
        return {}
    unmapped = {field["key"] for field in definition.fields if field.get("column") is None}
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
        answers=unapplied_answers(definition, archived_answers(submission)),
    )
