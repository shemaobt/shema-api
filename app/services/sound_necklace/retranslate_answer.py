"""Confirming a corrected transcript, and the English that has to follow it (ENG-394).

The draft pass writes both fields once and never looks at them again. A facilitator then
edits the spoken-language text on screen and confirms it — and the report artifact reads
the English field, so a correction that does not reach `translation_en` never reaches the
report. Nothing else in this API translates on demand, which is why the confirm route
cannot be a plain write: the second field has to be re-derived from the first.

Writing both in one statement is what keeps the pair honest. Two writes could leave the
corrected Portuguese standing next to the English of the sentence it replaced, which reads
as a translation and is not one.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, SessionLockChanged
from app.db.models.sound_necklace import SnAnswerTranscript, TranscriptStatus
from app.services.platform.translation import Translator, translate_to_english
from app.services.platform.voices import language_hint
from app.services.sound_necklace.lock_fence import not_locked_by_other, raise_if_locked_by_other


class TranscriptConfirmConflict(ConflictError):
    """A confirm sent from a draft that is no longer the one in the table.

    The loser is told to reload rather than retried automatically: what it holds is a
    human's edit of superseded text, and merging that blind is how a correction lands on
    the wrong answer.
    """

    def __init__(self) -> None:
        super().__init__(
            "This transcript changed since you opened it. Reload it and confirm again."
        )


async def retranslate_answer(
    db: AsyncSession,
    session_id: str,
    resource_path: str,
    *,
    transcript_source: str,
    expected_generation: int,
    actor_user_id: str,
    translator: Translator | None = None,
) -> SnAnswerTranscript:
    """Store the confirmed spoken text and the English re-derived from it.

    Text identical to what is stored comes straight back untouched, and the check comes
    before the generation guard on purpose. Every translation is billed, facilitators
    re-confirm answers they did not edit, and a retried request has to stay a no-op rather
    than turn into a conflict once the first attempt has already bumped the counter. The
    row that comes back carries the current generation, so a client that reached this by
    holding a stale one is handed the value that heals it.

    That comparison is byte for byte, which is the other half of why the confirmed text is
    stored exactly as it arrived. Normalising it on the way in — trimming the ends, folding
    the whitespace — would leave the stored text unequal to the text the next confirm sends
    for it, and the answer would be re-translated, and billed, every time it is re-confirmed.

    The English switch is spelled here rather than left to the translator's own, so the
    confirm fills the field the same way the draft pass did: for an English interview
    `translation_en` IS the transcript, and the report goes on reading one field.

    ``translator`` is the injected provider seam ``run_pending`` uses, and typing it as the
    Protocol is what makes the default checkable: a signature drifting away from the one
    this calls with is a type error here rather than a 500 in production.

    It resolves to the default inside the body rather than in the signature, which is where
    ``run_pending`` puts it. A default in the signature is bound once at import, so the
    only way to substitute it is to pass one — and unlike ``run_pending`` this has an HTTP
    surface, where nothing can be passed. Reading the name at call time keeps the route
    itself testable against a double, and the route is what the SPA calls.

    The lease is checked before the provider call and again inside the write. The early
    check is about money — a confirm somebody else's lock will refuse must not be paid for
    first — and the predicate in the statement is about correctness, since a takeover
    landing between the two is exactly what a check-then-act cannot see. The generation
    rides in that same WHERE for the same reason: the counter is read before an await long
    enough for another confirm to win, so re-checking it in Python would guard nothing.

    A write that matches nothing was refused by one of those two, and which one is worth
    deciding, on the path that already lost, because the client's three reactions differ.
    Someone still holds the lease: stop writing. The counter moved: the human's text is an
    edit of a superseded sentence, so reload. Neither: the lease refused the write and had
    lapsed by the time we looked, and the confirm the facilitator typed still stands — a
    reload here would ask them to discard it and retype it against identical text. Nothing
    matched, so nothing is pending to roll back.

    The confirmed row comes back out of the statement that wrote it rather than from a
    read afterwards: between a commit and a re-read another confirm can land, and the
    caller would answer 200 carrying somebody else's text as if it were the one just sent.
    """
    draft = await db.get(SnAnswerTranscript, (session_id, resource_path))
    if draft is None:
        raise NotFoundError("This answer has no transcript to confirm")

    await raise_if_locked_by_other(db, session_id, actor_user_id)

    if transcript_source == draft.transcript_source:
        return draft

    if expected_generation != draft.generation:
        raise TranscriptConfirmConflict()

    translate: Translator = translator or translate_to_english
    translation = (
        transcript_source
        if language_hint(draft.language) == "en"
        else await translate(transcript_source, source_language=draft.language)
    )

    confirmed = (
        await db.execute(
            update(SnAnswerTranscript)
            .where(
                SnAnswerTranscript.session_id == session_id,
                SnAnswerTranscript.resource_path == resource_path,
                SnAnswerTranscript.generation == draft.generation,
                not_locked_by_other(session_id, actor_user_id, datetime.now(UTC)),
            )
            .values(
                status=TranscriptStatus.READY,
                transcript_source=transcript_source,
                translation_en=translation,
                error=None,
                generation=SnAnswerTranscript.generation + 1,
            )
            .returning(SnAnswerTranscript)
            .execution_options(synchronize_session=False, populate_existing=True)
        )
    ).scalar_one_or_none()

    if confirmed is None:
        await raise_if_locked_by_other(db, session_id, actor_user_id)
        current_generation = (
            await db.execute(
                select(SnAnswerTranscript.generation).where(
                    SnAnswerTranscript.session_id == session_id,
                    SnAnswerTranscript.resource_path == resource_path,
                )
            )
        ).scalar_one_or_none()
        if current_generation == draft.generation:
            raise SessionLockChanged("The session lock changed hands. Try confirming again.")
        raise TranscriptConfirmConflict()

    await db.commit()
    return confirmed
