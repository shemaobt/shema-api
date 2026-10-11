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

**Two commits, in the order that cannot lose anything.** The archive and its arrival notice
commit first, then the record write commits ``applied_at`` with it — and with the prayer notice,
when the write put a request on the wall (OBT-566), so the Resource Circle hears of a request in
the same commit that shares it. A failure between them leaves a submission archived, announced
and unapplied — which is an inbox entry a coordinator can retry. The other order would apply a
Pulse that was never archived.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.auth import User
from app.db.models.shema import ShemaProject
from app.db.models.shema_change_log import ChangeAction, ChangeSubject
from app.db.models.shema_form import ShemaFormDefinition, ShemaIntakeImage, ShemaSubmission
from app.models.shema_forms import ReceivedSubmission, SubmissionImport
from app.services.shema import _trail
from app.services.shema._consent import newly_shared_request, shared_prayer_text
from app.services.shema._form_definitions import definition_at, publish_definition
from app.services.shema._form_validation import record_update
from app.services.shema._media_sharing import pulse_photo
from app.services.shema._progress import ProgressSource
from app.services.shema._scope import (
    Readership,
    RegionScope,
    refuse_out_of_scope,
    visible_projects,
)
from app.services.shema._submission_archive import (
    archive_submission,
    archived_answers,
    bind_intake_image,
)
from app.services.shema._submission_notices import notify_shared_request
from app.services.shema.read_submission import as_received, inbox_name
from app.services.shema.save_project import save_project
from app.utils.shema_forms import (
    IMAGE_AUTHORIZED_FIELD,
    IMAGE_DESCRIPTION_FIELD,
    IMAGE_FIELD,
    PULSE_FORM_TYPE,
    PULSE_KIND,
    carries_prayer_request,
)


async def _resolve_definition(db: AsyncSession, version: int | None) -> ShemaFormDefinition:
    """The version an import answered — the one it named, or the one standing today.

    **Optional here and required on the link**, which is not an inconsistency: the leader was
    *shown* a version and their answer is read against the one they saw, while a coordinator
    typing an answer today is answering today's form. A version that was named and never
    published is still refused; what is absent is not guessed at, it is the current one, and
    whichever it was is what the row records.

    **Publishing here as well as at the link, because this is the other authenticated write.**
    ``_form_definitions.py``'s rule is that the spec is published on an authenticated write and
    never on the public read; minting a link is one such write and this is the other. Without
    it a coordinator filing an answer that arrived on paper would be refused until somebody
    had minted a link for a leader who never used one — a dependency between two unrelated
    acts, and the kind that is discovered in the field. Publishing is by content, so this cuts
    no version when one already stands.
    """
    if version is not None:
        return await definition_at(db, PULSE_KIND, version)
    return await publish_definition(db, PULSE_KIND)


async def _apply(
    db: AsyncSession,
    scope: RegionScope,
    project: ShemaProject,
    submission: ShemaSubmission,
    definition: ShemaFormDefinition,
    answers: dict[str, Any],
    *,
    readership: Readership,
    user: User,
    app_key: str,
    expected_version: int,
    day: date,
) -> None:
    """Write what the answers map to, stamping where they came from.

    ``applied_at`` is staged **before** ``save_project`` so that one commit carries both: the
    record and the mark that this submission produced it land together, and there is no window
    in which the record moved and the inbox still says the entry is waiting. ``save_project``
    only flushes and the commit is this function's, so a submission whose answers moved nothing
    is still applied, and saying so is the difference between *done* and *forgotten*.

    **The prayer notice is staged here, between the write and the commit** (OBT-566). This is the
    moment a request reaches the wall, so the wall's text is read before the write and the
    record is asked after it whether the wall gained one (``_consent.newly_shared_request``) —
    the first share included, which the notice at arrival could never see. Only a Pulse that
    wrote a request announces one: the notice says the Pulse carries it.

    The write goes through ``save_project`` as the caller's own, ``readership`` included: an
    import is a person writing the record, and what that person may write is the record's rule
    and not the form's.
    """
    before = shared_prayer_text(project)
    submission.applied_at = datetime.now(UTC)
    try:
        written = await save_project(
            db,
            scope,
            project.id,
            record_update(definition, answers),
            readership=readership,
            user=user,
            expected_version=expected_version,
            day=day,
            source=ProgressSource(
                from_field=submission.submitted_by or None, form_type=PULSE_FORM_TYPE
            ),
            commit=False,
        )
        await _mint_pulse_photo(db, submission, answers)
        _trail.stage(
            db,
            actor=user,
            subject=ChangeSubject.SUBMISSION,
            action=ChangeAction.IMPORTED,
            subject_id=submission.id,
            project_id=project.id,
            region_key=_trail.region_value(project.region_key),
            fields=("appliedAt",),
        )
        if carries_prayer_request(answers) and newly_shared_request(written, before):
            await notify_shared_request(db, written, app_key=app_key)
    except Exception:
        await db.rollback()
        raise
    await db.commit()


async def _mint_pulse_photo(
    db: AsyncSession, submission: ShemaSubmission, answers: dict[str, Any]
) -> None:
    """The Pulse's image becomes the record's photo — OBT-578, in the import's own transaction.

    The ``image`` answer names the upload the link made (``store_intake_image``); here, and only
    here, it becomes a ``shema_media_items`` row the ficha, the card and every output path
    already read, with the description as its caption and the leader's answer to the box as
    its authorization (``_media_sharing.pulse_photo``). Nothing is minted for an answer that
    names no image, an image this submission does not own, or one already minted — a second
    apply is a no-op on this too.
    """
    image_id = answers.get(IMAGE_FIELD)
    if not image_id:
        return
    image = await db.get(ShemaIntakeImage, str(image_id))
    if image is None or image.submission_id != submission.id or image.media_item_id is not None:
        return
    photo = pulse_photo(
        image,
        caption=str(answers.get(IMAGE_DESCRIPTION_FIELD) or ""),
        authorized=answers.get(IMAGE_AUTHORIZED_FIELD) is True,
        by=submission.submitted_by,
        at=submission.received_at,
    )
    db.add(photo)
    await db.flush()
    image.media_item_id = photo.id


async def _answered_definition(
    db: AsyncSession, submission: ShemaSubmission
) -> ShemaFormDefinition:
    """The version a **stored** submission answered, which is not always the one just resolved.

    Re-filing bytes this server already has is a no-op, and the row it answers with is the one
    that was archived — possibly under an older spec, if the definition has been cut since and
    the body named no version. Reporting today's version for it would say the submission
    answered words it never saw, which is the exact failure the version column exists to
    prevent, arriving through the idempotency path instead of through an edit.
    """
    definition = await db.get(ShemaFormDefinition, submission.definition_id)
    if definition is None:
        raise NotFoundError("The form this submission answered is no longer published.")
    return definition


async def import_submission(
    db: AsyncSession,
    scope: RegionScope,
    payload_in: SubmissionImport,
    *,
    payload_bytes: bytes,
    readership: Readership,
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
    # An image reaches a Pulse only through the team's own link (OBT-578): with no link there
    # is no upload for the answer to name, and the refusal says so before anything is archived.
    await bind_intake_image(db, payload_in.answers, link=None)
    submission, created = await archive_submission(
        db,
        project,
        definition,
        payload=payload_bytes,
        answers=payload_in.answers,
        app_key=app_key,
        link=None,
    )
    await db.commit()

    answered = definition if created else await _answered_definition(db, submission)
    if submission.applied_at is None:
        await _apply(
            db,
            scope,
            project,
            submission,
            answered,
            archived_answers(submission),
            readership=readership,
            user=user,
            app_key=app_key,
            expected_version=expected_version,
            day=day,
        )
    return as_received(submission, answered.version, inbox_name(project, readership))


async def apply_submission(
    db: AsyncSession,
    scope: RegionScope,
    submission_id: str,
    *,
    readership: Readership,
    user: User,
    app_key: str,
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
            readership=readership,
            user=user,
            app_key=app_key,
            expected_version=expected_version,
            day=day,
        )
    return as_received(submission, definition.version, inbox_name(project, readership))
