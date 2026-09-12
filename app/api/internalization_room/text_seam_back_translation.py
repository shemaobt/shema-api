"""The text seam's second door: her frases as text, the real back-translation check out.

The first door opens the Guide's conversation (`text_seam.py`); this one opens the check the
Speaker voices a verdict on. One call declares the session over her draft clips, one call
plays a round of frases, and what comes back is what her `checkRound` is written against: the
findings with their frase numbers, the spoken turn, the outcome tag and `conferida`.

The path is the room's own, not a retelling of it: the frases are captured with the same
service the tablet's chunks are, and the verdict is the one `terminei` reaches. Only the
microphone and the synthesiser sit outside. Like the first door it exists only where a runner
key is configured, which production never sets.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room.text_seam import (
    _collecting_model_calls,
    _language_code,
    _outcome_tag,
    runner_dep,
)
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.internalization_room import IRSession, IRTake
from app.models.internalization_room import PlayedTake
from app.models.internalization_room_text_seam import (
    DeclareBackTranslationSessionRequest,
    DeclaredBackTranslationSessionResponse,
    DeclaredPart,
    RoundFinding,
    TextFrase,
    TextRoundRequest,
    TextRoundResponse,
)
from app.services import internalization_room as room
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    Finding,
    FindingKind,
)
from app.services.internalization_room.takes import declare_rehearsal_parts, declared_parts_by_key

router = APIRouter()


def _in_milliseconds(seconds: float) -> int:
    return round(seconds * 1000)


def _the_round_findings(current: list[Finding], all_of_them: list[Finding]) -> list[Finding]:
    """The turn's **Swap** at the front, led by its addition, then everything else it found.

    Her `no_kinds` and `no_finding` sweep every note the reading produced, so serving only
    what the Speaker voices would let the seam swallow a finding and read to her judge as a
    round the room found nothing wrong with — which is the failure her negative checks exist
    to catch.

    By identity, and it has to be: a finding is a pydantic model, so `in` compares values and
    two byte-identical findings — one kind, one note, one frase — would collapse into one and
    leave the second out of the list her checks sweep.
    """
    voiced = {id(finding) for finding in current}
    return [*current, *(one for one in all_of_them if id(one) not in voiced)]


@router.post(
    "/text-seam/back-translation/session",
    response_model=DeclaredBackTranslationSessionResponse,
    dependencies=[runner_dep],
    include_in_schema=False,
)
async def declare_back_translation_session(
    payload: DeclareBackTranslationSessionRequest, db: AsyncSession = Depends(get_db)
) -> DeclaredBackTranslationSessionResponse:
    """Open a session over her draft and report every part as heard through.

    Her runner marks each clip fully listened to before round one, because the rehearsal a
    team never heard cannot be checked and the passage would never close. The report is the
    real one: one entry per part, each in that part's own milliseconds, which is what
    `playback_confirms_rehearsal` reads (ADR 0017).
    """
    keys = [clip.key for clip in payload.clips]
    if len(set(keys)) != len(keys):
        raise ValidationError("two clips share one key, and a part is addressed by its key")
    session = await room.create_session(
        db, pericope=payload.pericopeId, language=_language_code(payload.language)
    )
    parts = await declare_rehearsal_parts(db, session, keys)
    await room.report_playback(
        db,
        session,
        room.back_translation_of(session),
        played_by_take=[
            PlayedTake(
                take_id=take.id,
                played_ranges=[[0, clip.durationMs]],
                clip_duration_ms=clip.durationMs,
            )
            for take, clip in zip(parts, payload.clips, strict=True)
        ],
        played_ranges=[],
        clip_duration_ms=None,
    )
    return DeclaredBackTranslationSessionResponse(
        sessionId=session.id,
        parts=[
            DeclaredPart(key=clip.key, takeId=take.id)
            for take, clip in zip(parts, payload.clips, strict=True)
        ],
    )


@router.post(
    "/text-seam/back-translation/round",
    response_model=TextRoundResponse,
    dependencies=[runner_dep],
    include_in_schema=False,
)
async def play_a_round(
    payload: TextRoundRequest, db: AsyncSession = Depends(get_db)
) -> TextRoundResponse:
    """One round of her script: the frases captured in listening order, then the verdict.

    Each frase is captured exactly as a chunk from a tablet is, minus the upload: the part it
    covers, the slice inside that part, and the words. A frase carrying `supersedes` is a
    retelling, so it replaces the stretch standing at that slice and is told a second time;
    the standing stretch is found by the address, not by her index, because the address is
    what the room has always addressed by.

    The verdict is the one `terminei` reaches, from the Correction check to the Speaker's
    words, and it is voiced as text: the seam synthesizes nothing, so the clip key it records
    is empty and only the words are kept. What it does not carry are the three answers
    `terminei` gives before that point — the untold-stretch halt, the empty telling-back and
    the cached verdict of a second press — because they are about a tablet and a team. A round
    with no frases is refused here instead: read as a telling-back, it would ask the analyst to
    compare nothing against the map, get no findings back, and report a golden round as
    `conferida` that nobody ever told.
    """
    if not payload.frases:
        raise ValidationError("a round with no frases is not a round")
    session = await room.get_session(db, payload.sessionId)
    started = time.monotonic()
    with _collecting_model_calls() as calls:
        parts = await declared_parts_by_key(db, session.id)
        state = room.back_translation_of(session)
        for number, frase in enumerate(payload.frases, start=1):
            state = await _capture(db, session, state, frase, number=number, parts=parts)

        told = room.told_back(await room.final_segments(db, session.id))
        verdict = await room.check_the_telling_back(
            session,
            state=state,
            told=told,
            retired=await room.retired_segments(db, session.id),
            settings=get_settings(),
        )
        await room.save_the_spoken_verdict(
            db,
            session,
            state,
            said=verdict.said,
            clip_key="",
            used_fail_safe=verdict.outcome.used_fail_safe,
            fixed_line=verdict.outcome.fixed_line,
        )

    return TextRoundResponse(
        sessionId=session.id,
        findings=[
            RoundFinding(
                kind=finding.kind.value,
                note=finding.note,
                frase=finding.chunk,
                stretchId=finding.segment_id,
            )
            for finding in _the_round_findings(verdict.current, state.findings)
        ],
        spoken=verdict.said,
        outcome=_outcome_tag(verdict.outcome),
        conferida=verdict.checked,
        findingsRemaining=verdict.findings_remaining,
        missingWithoutFrase=sum(
            1
            for finding in verdict.read_this_round
            if finding.kind is FindingKind.MISSING and finding.chunk is None
        ),
        usage=calls,
        roundMs=round((time.monotonic() - started) * 1000),
    )


async def _capture(
    db: AsyncSession,
    session: IRSession,
    state: BackTranslationState,
    frase: TextFrase,
    *,
    number: int,
    parts: dict[str, IRTake],
) -> BackTranslationState:
    part = parts.get(frase.clipKey)
    if part is None:
        raise NotFoundError(f"frase {number} names clip {frase.clipKey!r}, which was not declared")
    starts_ms = _in_milliseconds(frase.coversFrom)
    ends_ms = _in_milliseconds(frase.coversTo)
    retold = None
    if frase.supersedes is not None:
        retold = await room.current_stretch_at(
            db, session.id, take_id=part.id, starts_ms=starts_ms, ends_ms=ends_ms
        )
        if retold is None:
            raise ValidationError(
                f"frase {number} supersedes a telling, and no stretch stands at "
                f"{frase.clipKey} {frase.coversFrom}-{frase.coversTo}s"
            )
    state.scope = state.scope or session.pericope
    await room.capture_and_note_a_hard_stretch(
        db,
        session,
        take_id=part.id,
        starts_ms=starts_ms,
        ends_ms=ends_ms,
        bridge_take_id=None,
        transcript=frase.text,
        pass_number=2 if retold is not None else 1,
        replaces=retold,
        state=state,
    )
    return state
