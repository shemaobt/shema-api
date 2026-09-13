"""The unauthenticated door — a leader answering the form their link opened.

**It does not write** ``shema_projects``, **and that is the decision this file exists to
hold.** FE-44 §9.9 answers this route with ``202`` and the neighbouring one with a
``ReceivedSubmission``, which is the contract saying *accepted, not applied*; and the machinery
underneath agrees, for reasons that are not about the status code:

* ``save_project`` takes an actor. ``shema_projects.updated_by`` and every row of
  ``shema_record_edits`` name a ``users.id``, and BE-06's whole argument is that *the trail is
  where the author of every write lives*. A link has no author. Writing one would mean either
  a nullable author in the trail or a synthetic system account — the first weakens the
  invariant for every writer, the second invents an account nobody can be asked about.
* ``save_project`` takes a version. There is no version an anonymous caller read, so the
  concurrency guard would have to be skipped for exactly this writer — the one writer whose
  input is least trusted.
* And the product's own loop says so: ``PULSE_LOOP`` in the console's ``src/constants/forms.ts``
  has **five steps**, and ``import`` is the coordinator's. The leader answers; a person imports.

So the link deposits into an inbox and a coordinator applies it
(``app/services/shema/import_submission.py``). The cost is one click by somebody who was going
to look at it anyway. What it buys is that the weakest credential in the system cannot move
the numbers the ETEN year-end report is reconstructed from without a person who can be asked
about it.

**What it does write**: the archive, the notices, and ``used_at`` on the link. The notices are
the half that makes the deposit honest — *a form that is submitted and never seen is worse
than no form* — and they are staged in the same transaction as the archive, so there is no
ordering in which the submission exists and the notice does not.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.shema import ShemaProject
from app.db.models.shema_form import ShemaFormDefinition
from app.models.shema_forms import IntakeSubmission
from app.services.shema._intake_tokens import verify_intake_token
from app.services.shema._submission_archive import archive_submission


async def receive_submission(
    db: AsyncSession,
    raw_token: str,
    submission: IntakeSubmission,
    *,
    payload_bytes: bytes,
    app_key: str,
) -> None:
    """Take one answer through one link, or refuse it whole. Nothing is returned.

    **The answer names no project and no version of its own choosing.** Both come off the link:
    the project it was minted for and the definition it was minted with. The client's
    ``definitionVersion`` is checked against that rather than used to select one — a submission
    that quotes a version the link was not issued against is answering a different form, and
    reading it against today's would be inventing which words it answered.

    A second arrival of the same bytes is accepted and changes nothing, which is what makes a
    leader on a bad connection safe to tap twice. The wire cannot tell the two apart, and the
    point of ``202`` is that it does not have to.
    """
    link = await verify_intake_token(db, raw_token)

    definition = await db.get(ShemaFormDefinition, link.definition_id)
    if definition is None:
        raise NotFoundError("The form this link was issued for is no longer published.")
    if submission.definition_version != definition.version:
        raise ValidationError(
            f"definitionVersion: this link answers version {definition.version} of the "
            f"{definition.kind} form, not {submission.definition_version}. Reload the form."
        )

    project = (
        await db.execute(select(ShemaProject).where(ShemaProject.id == link.project_id))
    ).scalar_one_or_none()
    if project is None:
        raise NotFoundError("The project this link was issued for no longer exists.")

    _row, created = await archive_submission(
        db,
        project,
        definition,
        payload=payload_bytes,
        answers=submission.answers,
        app_key=app_key,
        link=link,
    )
    if created and link.used_at is None:
        link.used_at = datetime.now(UTC)
    await db.commit()
