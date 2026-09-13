"""What the leader's link serves — and the shortest list in this module of what it does not.

**Write-mostly, enforced by the SELECT list.** The query reads one column:
``shema_projects.language_name``. Not a row with fields left out of a response model, not a
record filtered on the way to the wire — one column, so there is nothing else in memory for a
later edit to reach for and nothing else for a serialiser to be talked into emitting. OBT-401's
sentence is that *a submission link that also reads the project record turns a forwarded
WhatsApp message into a disclosure*; the narrowest place to make that true is the statement,
and this is it.

**Why the language name is the one thing.** *If it must show context, show the minimum that
makes the form answerable* — and a leader who holds links for two projects has to be able to
tell which form they are filling before they fill it. It is not a guarded field:
``app/models/shema_privacy.py``'s list is places, bases and contacts, and
``shema_submissions`` already snapshots this same value for the same reason.

**There is no scope here and that is not an omission.** The token is the authorization, and it
is project-scoped in the column: the statement can only return the project the link names. That
is the same *predicate underneath rather than beside* property ``visible_projects`` gives a
signed-in caller, reached through the one credential in this module that has no account behind
it.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.shema import ShemaProject
from app.db.models.shema_form import ShemaFormDefinition
from app.models.shema_forms import IntakeField, IntakeForm
from app.services.shema._intake_tokens import expires_on, verify_intake_token


def form_fields(definition: ShemaFormDefinition) -> list[IntakeField]:
    """The stored spec as the form renders it, with the column mapping dropped.

    Shared with the coordinator's own read of a submission, so that *the form this answered*
    is one shape wherever it is shown rather than two that drift.
    """
    return [
        IntakeField(
            key=field["key"],
            type=field["type"],
            required=field["required"],
            label_key=field["labelKey"],
            max_length=field.get("maxLength"),
            options=list(field.get("options") or []),
        )
        for field in definition.fields
    ]


async def read_intake_form(db: AsyncSession, raw_token: str) -> IntakeForm:
    """The form behind one live link, and nothing of the project but its language.

    The definition is the one the link was **minted with**, not the newest: a leader opens the
    form, drives out to where the team is and answers days later, and a definition edited in
    that window must not turn their answer into a mismatch.
    """
    link = await verify_intake_token(db, raw_token)

    definition = await db.get(ShemaFormDefinition, link.definition_id)
    if definition is None:
        raise NotFoundError("The form this link was issued for is no longer published.")

    language_name = (
        await db.execute(
            select(ShemaProject.language_name).where(ShemaProject.id == link.project_id)
        )
    ).scalar_one_or_none()
    if language_name is None:
        raise NotFoundError("The project this link was issued for no longer exists.")

    return IntakeForm(
        kind=definition.kind,
        definition_version=definition.version,
        language_name=language_name,
        expires_at=expires_on(link),
        fields=form_fields(definition),
    )
