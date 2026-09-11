"""Applying a submission to the record — the coordinator's half, and the only writer of it.

Two doors reach this file and both are a signed-in coordinator: one files an answer that
arrived some other way (paper, a voice note, read out over a bad line) and applies it in the
same call; the other applies one already sitting in the inbox from a link. They share
everything but where the submission came from.

**An imported progress change goes through the same write path as a typed one.** FE-44 §9.9
asks for it and BE-06 built the seam: ``save_project`` takes a ``ProgressSource`` that the
ficha's own ``PATCH`` never fills, so an import stamps ``fromField`` and ``formType`` and is
otherwise indistinguishable afterwards — which is the requirement. There is no second write
path here and there must not be one: a second writer of ``shema_progress_history`` is a second
reading of *what counts as a change*.

**Only what maps to a column is applied**, and ``app/utils/shema_forms.py`` holds the mapping.
The voice and the blockers are archived, shown in the submission's own read, and left to a
person. A Pulse that quietly replaced a coordinator's status comments with a leader's free text
would be the record being edited through the weakest credential in the system, and FE-44 §9.9
asks nothing of the record but the progress.

**Idempotent twice over.** ``applied_at`` stops a second apply of the same row, and underneath
it the data agrees: the progress a Pulse carries is **absolute**, not a delta, so re-applying
the same numbers moves nothing — ``save_project``'s *a save that changed nothing stops here*
is the second net, and it is the one that holds even if the first is ever wrong.

**Two commits, in the order that cannot lose anything.** The archive and its notices commit
first, then the record write commits ``applied_at`` with it. A failure between them leaves a
submission archived, announced and unapplied — which is an inbox entry a coordinator can
retry. The other order would apply a Pulse that was never archived.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.auth import User
from app.db.models.shema import ShemaProject
from app.db.models.shema_form import ShemaFormDefinition, ShemaSubmission
from app.models.shema_forms import ReceivedSubmission, SubmissionImport
from app.services.shema._form_definitions import current_definition, definition_at
from app.services.shema._form_validation import record_update
from app.services.shema._progress import ProgressSource
from app.services.shema._scope import RegionScope, refuse_out_of_scope, visible_projects
from app.services.shema._submission_archive import archive_submission, archived_answers
from app.services.shema.read_submission import as_received
from app.services.shema.save_project import save_project
from app.utils.shema_forms import PULSE_FORM_TYPE, PULSE_KIND


async def _resolve_definition(db: AsyncSession, version: int | None) -> ShemaFormDefinition:
    """The version an import answered — the one it named, or the one standing today.

    **Optional here and required on the link**, which is not an inconsistency: the leader was
    *shown* a version and their answer is read against the one they saw, while a coordinator
    typing an answer today is answering today's form. A version that was named and never
    published is still refused; what is absent is not guessed at, it is the current one, and
    whichever it was is what the row records.
    """
    if version is not None:
        return await definition_at(db, PULSE_KIND, version)
    definition = await current_definition(db, PULSE_KIND)
    if definition is None:
        raise NotFoundError(
            f"No version of the {PULSE_KIND} form is published yet. Mint an intake link first."
        )
    return definition


async def _apply(
    db: AsyncSession,
    scope: RegionScope,
    project: ShemaProject,
    submission: ShemaSubmission,
    definition: ShemaFormDefinition,
    answers: dict[str, Any],
    *,
    user: User,
    expected_version: int,
    day: date,
) -> None:
    """Write what the answers map to, stamping where they came from.

    ``applied_at`` is staged **before** ``save_project`` so that its commit carries both: the
    record and the mark that this submission produced it land together, and there is no window
    in which the record moved and the inbox still says the entry is waiting. The explicit
    commit afterwards is for the case ``save_project`` returns without one — a submission whose
    answers moved nothing is still applied, and saying so is the difference between *done* and
    *forgotten*.
    """
    submission.applied_at = datetime.now(UTC)
    try:
        await save_project(
            db,
            scope,
            project.id,
            record_update(definition, answers),
            user=user,
            expected_version=expected_version,
            day=day,
            source=ProgressSource(
                from_field=submission.submitted_by or None, form_type=PULSE_FORM_TYPE
            ),
        )
    except Exception:
        await db.rollback()
        raise
    await db.commit()


async def import_submission(
    db: AsyncSession,
    scope: RegionScope,
    payload_in: SubmissionImport,
    *,
    payload_bytes: bytes,
    user: User,
    app_key: str,
    expected_version: int,
    day: date,
) -> ReceivedSubmission:
    """File an answer a coordinator holds, and apply it in the same call.

    A second call with the same bytes for the same project answers the same submission and
    applies nothing — the archive is already there and ``applied_at`` is already set, which is
    *a double import is a no-op* on both halves rather than only on the archive.
    """
    project = (
        await db.execute(visible_projects(scope).where(ShemaProject.id == payload_in.project_id))
    ).scalar_one_or_none()
    if project is None:
        raise refuse_out_of_scope(
            scope, user=user, operation="import_submission", project_id=payload_in.project_id
        )

    definition = await _resolve_definition(db, payload_in.definition_version)
    submission, _created = await archive_submission(
        db,
        project,
        definition,
        payload=payload_bytes,
        answers=payload_in.answers,
        app_key=app_key,
        link=None,
    )
    await db.commit()

    if submission.applied_at is None:
        await _apply(
            db,
            scope,
            project,
            submission,
            definition,
            payload_in.answers,
            user=user,
            expected_version=expected_version,
            day=day,
        )
    return as_received(submission, definition.version)


async def apply_submission(
    db: AsyncSession,
    scope: RegionScope,
    submission_id: str,
    *,
    user: User,
    expected_version: int,
    day: date,
) -> ReceivedSubmission:
    """Apply one submission already in the inbox — the leader-link answer's second half.

    The answers come out of the archive rather than off the wire, which is the point: what is
    applied is what arrived, byte for byte, read back against the version it answered. They are
    re-validated on the way through ``record_update``, so a definition this server can no
    longer satisfy fails here rather than landing half of itself on the record.
    """
    row = (
        await db.execute(
            select(ShemaSubmission, ShemaProject, ShemaFormDefinition)
            .join(ShemaProject, ShemaProject.id == ShemaSubmission.project_id)
            .join(ShemaFormDefinition, ShemaFormDefinition.id == ShemaSubmission.definition_id)
            .where(ShemaSubmission.id == submission_id)
            .where(ShemaProject.id.in_(select(visible_projects(scope).subquery().c.id)))
        )
    ).first()
    if row is None:
        raise refuse_out_of_scope(
            scope, user=user, operation="apply_submission", project_id=submission_id
        )

    submission, project, definition = row
    if submission.applied_at is None:
        await _apply(
            db,
            scope,
            project,
            submission,
            definition,
            archived_answers(submission),
            user=user,
            expected_version=expected_version,
            day=day,
        )
    return as_received(submission, definition.version)
