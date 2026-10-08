"""Archiving one submission, exactly once — the half both doors share.

Two doors reach this: a leader answering through the link, and a coordinator filing an answer
that arrived some other way. They differ in who is accountable and in whether the record is
written; they must not differ in what is checked, what is kept or what a second arrival does.
So the shared half is one function, and the two doors are thin.

**Idempotent by the content of what arrived**, on the unique index BE-02 put on
``(project_id, content_hash)``. A leader who forwards the same file twice, a coordinator who
double-taps a slow button on a bad connection, a retry after a timeout that actually landed —
all three are the same event, and *a double import is a no-op* means no second archive, no
second notice and no second progress entry. FE-44 §9.9 makes the reason concrete: it must not
double a chapter count.

**Two requests racing on the same bytes is the one case this does not answer with a 202, and
the honest description is worth more than a clever fix.** The standing-row lookup and the
insert are not one atomic step, so two simultaneous arrivals of an identical submission can
both miss the lookup; the unique index on ``(project_id, content_hash)`` then refuses the
second, which reaches the caller as a 500 and succeeds as a no-op on the retry. **What cannot
happen is the thing the rule is about** — two archives, two notices, or a chapter count
counted twice — because the index is what decides, not the lookup. Closing it would mean a
savepoint around the insert, and the trade is against a window measured in milliseconds for a
form filled once a month; it is named here so the next person weighs it rather than discovers
it.

**Transactional, and the transaction is the caller's.** Nothing here commits. The archive and
its notices are staged together and land together, which is the property that makes *submitted
and never seen* impossible: there is no ordering in which a submission exists and its notice
does not.

**Validated before anything is written, and the payload is kept verbatim.** The bytes are the
request body as it arrived — not a re-serialisation of the parsed answers, which would be the
server's rendering of what the leader said rather than what they said. They are written only
after ``_form_validation.py`` has passed the whole submission, because a store of unvalidated
payloads to clean later is a store nobody ever cleans.

**The standing row is found before the validation runs, and the order is the rule rather than
an optimisation.** A second arrival of bytes this server already accepted is a no-op, and a
no-op cannot be a 400: if the spec has moved since — a field dropped, a vocabulary narrowed —
re-checking the same bytes against today's definition would refuse a submission that is already
archived, which is the opposite of idempotent. It was validated when it arrived; it is not
asked again.

**Verbatim, with one exception the client made** (OBT-561): when the team withdraws the
authorization of its prayer request, the request leaves every archived Pulse of the project that
shared it in the same words (:func:`erase_withdrawn_request`, OBT-576). The rest of the envelope
stays; the content hash stays the hash of the bytes as they arrived, which is what keeps the same
file, sent again, a no-op instead of the way the text would return.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.db.models.auth import User
from app.db.models.shema import ShemaProject
from app.db.models.shema_form import ShemaFormDefinition, ShemaIntakeLink, ShemaSubmission
from app.services.shema._consent import same_request
from app.services.shema._form_validation import record_update, validate_submission
from app.services.shema._submission_notices import notify_submission
from app.utils.shema_forms import (
    PRAYER_FIELD,
    PRAYER_VISIBILITY_FIELD,
    SUBMITTED_BY_FIELD,
    carries_prayer_request,
)

#: The largest submission this server will archive.
#:
#: A ceiling on an **unauthenticated** write and not a product rule: generous against what a
#: team leader types on a phone, small against what a script would send. It is a second line
#: rather than the first — the platform in front of this API caps a request body long before
#: this does, and the per-field limits in ``app/utils/shema_forms.py`` bound the answers
#: themselves. What this one guards is the column and the archive: the sum of legitimate
#: fields, not any one of them.
MAX_PAYLOAD_BYTES = 256 * 1024


def content_hash(payload: bytes) -> str:
    """What makes a second arrival of the same submission the same submission."""
    return hashlib.sha256(payload).hexdigest()


#: The key both doors' request bodies carry the answers under.
#:
#: Named once because the archive is the bytes of the **envelope**, not of the answers alone —
#: which is what *byte-identically* has to mean when the request also carries the project and
#: the version. Reading them back is therefore a fact about the envelope, and a second call
#: site spelling it is how the archive and its reader stop agreeing.
ANSWERS_KEY = "answers"


def archived_answers(submission: ShemaSubmission) -> dict[str, Any]:
    """The answers as they arrived, read back out of the archived request body.

    Read back rather than stored a second time in a column of their own: two copies of one
    payload are two things a migration can edit apart, and the one that matters is the one the
    content hash was taken over.
    """
    body = json.loads(submission.archived_payload)
    answers = body.get(ANSWERS_KEY, {})
    return answers if isinstance(answers, dict) else {}


async def archive_submission(
    db: AsyncSession,
    project: ShemaProject,
    definition: ShemaFormDefinition,
    *,
    payload: bytes,
    answers: dict[str, Any],
    app_key: str,
    link: ShemaIntakeLink | None,
) -> tuple[ShemaSubmission, bool]:
    """Check, keep and announce one submission; answer it and whether it was new.

    Returns the standing row untouched when the same bytes have already been archived for this
    project — no second notice, and nothing re-validated. ``False`` is how the two doors stay
    honest about it: the wire answers the same submission either way, which is what an
    idempotent endpoint means, and neither door has to know how the other spells *again*. A
    caller that then wants to apply it must read the version off **that** row rather than off
    the definition it resolved, because the two can differ by a spec change in between.

    The answers are validated here rather than by either caller, so *rejected whole* is a
    property of the path and not of two call sites that have to stay in step.
    """
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise ValidationError(
            f"The submission is {len(payload)} bytes and this form accepts "
            f"{MAX_PAYLOAD_BYTES}. Nothing was kept."
        )

    digest = content_hash(payload)
    standing = (
        await db.execute(
            select(ShemaSubmission).where(
                ShemaSubmission.project_id == project.id,
                ShemaSubmission.content_hash == digest,
            )
        )
    ).scalar_one_or_none()
    if standing is not None:
        return standing, False

    validate_submission(definition, answers)

    submission = ShemaSubmission(
        project_id=project.id,
        language_name=project.language_name,
        submitted_by=str(answers.get(SUBMITTED_BY_FIELD, "")),
        content_hash=digest,
        definition_id=definition.id,
        intake_link_id=None if link is None else link.id,
        archived_payload=payload.decode("utf-8"),
    )
    db.add(submission)
    await db.flush()

    await notify_submission(
        db,
        project,
        submission,
        app_key=app_key,
        carries_prayer=carries_prayer_request(answers),
        written=record_update(definition, answers),
    )
    return submission, True


async def erase_withdrawn_request(
    db: AsyncSession, project: ShemaProject, text: str, *, user: User
) -> None:
    """Remove ``text`` from every archived Pulse of ``project`` that shared it in those words.

    Karina, via Daniel, 1/out/2026: when the team withdraws the authorization of a prayer
    request, *"o pedido é apagado também do Pulso guardado"* — the other options were keeping
    the Pulse whole for coordination only, or keeping it as it was. **A Pulse that shared is one
    that answered** ``rede``: the team said *share this with the network* in it, and that is
    what the withdrawal takes back. A Pulse that kept its request in coordination never shared
    anything and is left as it arrived.

    **Only the Pulse that carries the withdrawn text** — ``text``, the one that was on the wall
    (``_consent.withdrawn_request``). Karina again, 6/out/2026, asked whether a Pulse that
    shared a wording the team edited since goes too: *"Não, só do Pulso com o texto exatamente
    igual."* That Pulse is the record of an earlier version and stays as it arrived. *Exactly
    equal* is ``_consent.same_request``'s, which compares the text as its reader sees it.

    **The answer is removed, not blanked, and its visibility with it.** An archived Pulse still
    waiting in the inbox is applied from these answers: an empty request would be applied over
    the record's, and a ``rede`` left behind would authorize again, on apply, the very text the
    team just took back. Absent answers write nothing, as for a leader who left both blank.

    The trace is the two columns on the row — when and by whom — and never the text: a log of
    what was erased would be the copy the erasure exists to remove. Staged, like everything in
    this file; the caller's transaction takes it with the write that withdrew the authorization.
    """
    rows = await db.execute(select(ShemaSubmission).where(ShemaSubmission.project_id == project.id))
    at = datetime.now(UTC)
    for submission in rows.scalars():
        body = json.loads(submission.archived_payload)
        answers = body.get(ANSWERS_KEY)
        if not isinstance(answers, dict) or answers.get(PRAYER_VISIBILITY_FIELD) != "rede":
            continue
        carried = answers.get(PRAYER_FIELD)
        if not isinstance(carried, str) or not same_request(carried, text):
            continue
        del answers[PRAYER_FIELD]
        del answers[PRAYER_VISIBILITY_FIELD]
        submission.archived_payload = json.dumps(body, ensure_ascii=False)
        submission.prayer_request_erased_at = at
        submission.prayer_request_erased_by = user.id
