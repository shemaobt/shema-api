"""One round of the telling-back check: from the reading to the words the Speaker says.

The route pressed `terminei` and the text seam plays a round of frases; they are the same
question asked from two places, and this is the one answer. It was the body of the route, so
the seam could only have reached it by writing the flow a second time — and a second
expression of the room's flow is free to drift from the first, which is the one thing the
verdict cannot afford.

Nothing is synthesized here and nothing is written: what comes back is what was decided and
what is to be said. The voice and the record are the caller's, because only the route has a
clip to point at and the ordering of those two is itself a decision — the synthesis runs
first, so a voice that fails leaves no verdict behind claiming to have been spoken.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.db.models.internalization_room import IRPromptKey, IRSegment, IRSession, IRTake
from app.services.internalization_room.back_translation import (
    THE_WHOLE_PASSAGE,
    BackTranslationState,
    CheckRound,
    Finding,
    Nuance,
    VoicedVerdict,
    analyse_telling_back,
    current_findings,
    findings_block,
    findings_on_stretches_that_count,
    findings_remaining,
    is_joined,
    nuances_said,
    passage_numbers,
    said_before,
    segments_block,
    the_finding_that_leads,
)
from app.services.internalization_room.canon.kept import reading_the_canon_of
from app.services.internalization_room.fail_safe import FailSafe, choose
from app.services.internalization_room.languages import LANGUAGE_NAMES, room_language
from app.services.internalization_room.part_names import addresses_for, scene_titles
from app.services.internalization_room.prompts import get_prompt_text
from app.services.internalization_room.segments import final_segments, set_aside_segment_ids
from app.services.internalization_room.segments import told_back as stretches_told_back
from app.services.internalization_room.sessions import (
    append_exchange,
    back_translation_of,
    save_back_translation,
)
from app.services.internalization_room.synthesize_facilitator_speech import (
    in_a_voice_the_room_has,
)
from app.services.internalization_room.takes import current_parts
from app.services.internalization_room.validated_turn import Attempt, TurnOutcome, outcome_tag
from app.services.internalization_room.verdict_turn import run_verdict_turn

UNREADABLE_ANALYSIS_NOTE = "The Analyst's reply could not be read, so there was no verdict."


@dataclass(frozen=True)
class TellingBackVerdict:
    """What one round decided, and what the room is about to say about it.

    `finding` is the half that carries the address — the one finding, or the addition of a
    **Swap** — and `current` is everything this turn is allowed to voice. `said` is the verdict
    the Speaker voiced, so the caller synthesizes it as it stands.
    """

    finding: Finding | None
    current: list[Finding]
    #: What the model answered *this* round. Distinct from the standing list, which carries
    #: findings forward across rounds: a measurement of this round's reply read off the standing
    #: list counts an earlier round's answer again every time.
    read_this_round: list[Finding]
    said: str
    outcome: TurnOutcome
    checked: bool
    findings_remaining: int
    #: The stretches as the Validator was shown them — what the team said this round.
    told_back: str


async def check_the_telling_back(
    session: IRSession,
    *,
    state: BackTranslationState,
    told: list[IRSegment],
    stale: list[IRSegment],
    takes: list[IRTake],
    settings: Settings,
) -> TellingBackVerdict:
    """Read what the team told back, settle the findings, and voice one of them.

    Nothing is saved as a verdict on a reading that could not be made: `checked` strikes the
    passage off the wheel for good, so a passage blessed because the analyst was unreachable
    would be finished by an outage. A reply the analyst gave and the room could not read is
    heard as her first D line and kept as a turn, with no verdict behind it.

    `takes` is the session's recordings in reading order, which is where the address the voice
    says comes from: a finding names a stretch, a stretch is a slice of a **Part**, and only the
    takes say which part that is and where it sits among the current ones. Handed in rather than
    read here, because this module touches no database — the two callers already hold one.

    `state` is mutated in place — the findings, the addresses already read, `checked` and the
    moment it was decided — and writing it is the caller's, in the same transaction as whatever
    else it decides.
    """
    read_this_round: list[Finding] = []
    language = room_language(session.language)
    numbers = passage_numbers(told, stretches_told_back(stale), takes)
    addresses = addresses_for(
        told,
        current_parts(takes),
        scene_titles(session),
        language,
        numbers,
    )
    told_back = segments_block(told, addresses, language, numbers)
    if not state.already_analysed(told):
        read = await analyse_telling_back(
            segments=told,
            numbers=numbers,
            scope=THE_WHOLE_PASSAGE,
            pericope_num=session.pericope,
            analyst_prompt=get_prompt_text(IRPromptKey.BT_ANALYST),
            addresses=addresses,
            session_language=LANGUAGE_NAMES[language],
            language_code=language,
            settings=settings,
            session_id=session.id,
        )
        if read is None:
            line, name = choose(FailSafe.INAUDIBLE, language)
            state.checks.append(
                CheckRound(at=datetime.now(UTC), spoken=line, outcome="fail_safe", conferida=False)
            )
            return TellingBackVerdict(
                finding=None,
                current=[],
                read_this_round=[],
                said=line,
                outcome=TurnOutcome(
                    speech=line,
                    transcript="",
                    used_fail_safe=True,
                    degraded=True,
                    fixed_line=name,
                    attempts=[Attempt(attempt=1, draft="", note=UNREADABLE_ANALYSIS_NOTE).stored()],
                ),
                checked=False,
                findings_remaining=findings_remaining(
                    findings_on_stretches_that_count(state.findings, (one.id for one in told))
                ),
                told_back=told_back,
            )
        read_this_round = read.findings
        state.nuances = sorted(read.nuances, key=lambda one: one.chunk)
        state.findings = read.findings
        state.analysed_segment_ids = [segment.id for segment in told]

    state.findings = findings_on_stretches_that_count(state.findings, (one.id for one in told))

    current = current_findings(state)
    finding = the_finding_that_leads(state)
    at = datetime.now(UTC)
    state.checked_at = at

    async def speak(handed: list[Finding] | list[Nuance]) -> TurnOutcome:
        return await run_verdict_turn(
            findings_text=findings_block(handed, addresses),
            scope=THE_WHOLE_PASSAGE,
            pericope_num=session.pericope,
            messages=session.messages or [],
            telling_back=told_back,
            speaker_prompt=get_prompt_text(IRPromptKey.BT_VERDICT_SPEAKER),
            validator_prompt=get_prompt_text(IRPromptKey.VALIDATOR),
            session_language=LANGUAGE_NAMES[language],
            language_code=language,
            settings=settings,
            session_id=session.id,
            joined=is_joined(current_parts(takes)),
        )

    said_already = nuances_said(state.checks)
    nuances = [
        one.model_copy(
            update={"voiced": "before" if said_before(one, said_already, told) else None}
        )
        for one in state.nuances
    ]
    offered = None if current else next((one for one in nuances if one.voiced is None), None)
    outcome = await speak(current or ([offered] if offered else []))
    if outcome.used_fail_safe and offered is not None:
        outcome = await speak([])
    elif offered is not None and re.search(rf"frase\s+{offered.chunk}(?!\d)", outcome.speech, re.I):
        offered.voiced = "now"

    said = outcome.speech
    state.checked = finding is None and not outcome.used_fail_safe
    state.checks.append(
        CheckRound(
            at=at,
            findings=list(state.findings),
            spoken=said,
            outcome=outcome_tag(outcome),
            conferida=state.checked,
            nuances=nuances,
        )
    )
    return TellingBackVerdict(
        finding=finding,
        current=current,
        read_this_round=read_this_round,
        said=said,
        outcome=outcome,
        checked=state.checked,
        findings_remaining=findings_remaining(state.findings),
        told_back=told_back,
    )


async def save_the_spoken_verdict(
    db: AsyncSession,
    session: IRSession,
    state: BackTranslationState,
    *,
    said: str,
    clip_key: str,
    outcome: TurnOutcome,
    told_back: str,
) -> IRSession:
    """Write the turn the room just spoke: the exchange, the verdict and the state behind it.

    Called once the words exist as audio, or once the caller has decided there will be none.
    A verdict stored before its clip would be served back by the repeat-press guard as a turn
    the team heard, when what they heard was the error.

    A verdict read from stretches that changed while it was being read is not stored as a
    blessing: `checked` strikes the passage off the wheel and the cached verdict would be served
    back for a passage the team has since recorded again. It is stored as the upload left it —
    not checked, no verdict — and carries only findings on stretches that count.
    """
    session_id = session.id
    base = back_translation_of(session)

    async def as_it_stands(read: BackTranslationState) -> None:
        standing = await final_segments(db, session_id)
        aside = await set_aside_segment_ids(db, session_id)
        read.findings = [
            *findings_on_stretches_that_count(read.findings, (one.id for one in standing)),
            *(f for f in base.findings if f.segment_id in aside),
        ]
        if len(read.sentences) > len(base.sentences) or not read.already_analysed(
            stretches_told_back(standing)
        ):
            read.checked = False
            read.verdict = None
        if len(read.superseded) > len(base.superseded):
            stored = BackTranslationState.model_validate(
                await db.scalar(
                    select(IRSession.back_translation).where(IRSession.id == session_id)
                )
                or {}
            )
            ours = {one.at for one in state.checks} - {one.at for one in base.checks}
            archive = read.superseded[len(base.superseded)]
            archive.findings = [
                *archive.findings,
                *(one for one in state.findings if one not in archive.findings),
            ]
            archive.checks = [*archive.checks, *(one for one in state.checks if one.at in ours)]
            read.findings = stored.findings
            read.nuances = stored.nuances
            read.checks = stored.checks
            read.checked = stored.checked
            read.checked_at = stored.checked_at
            read.verdict = stored.verdict
            read.analysed_segment_ids = stored.analysed_segment_ids

    state.verdict = VoicedVerdict(
        clip_key=clip_key, fixed_line=outcome.fixed_line, used_fail_safe=outcome.used_fail_safe
    )
    await as_it_stands(state)
    with reading_the_canon_of(session.canon_pin):
        session = await append_exchange(
            db,
            session,
            team_utterance="",
            guide_response=said,
            outcome=outcome,
            told_back=told_back,
        )
    await save_back_translation(db, session, state, rule=as_it_stands)
    return session


def the_round_is_heard_at_once(state: BackTranslationState) -> None:
    state.checks[-1].heard_at = datetime.now(UTC)


def _to_the_millisecond(moment: datetime) -> datetime:
    return moment.replace(microsecond=moment.microsecond // 1000 * 1000)


async def mark_the_verdict_heard(db: AsyncSession, session: IRSession, at: datetime) -> bool:
    state = back_translation_of(session)
    heard = next(
        (one for one in state.checks if _to_the_millisecond(one.at) == _to_the_millisecond(at)),
        None,
    )
    if heard is None:
        raise NotFoundError("No check round carries this stamp")
    if heard.heard_at is not None:
        return False
    heard.heard_at = datetime.now(UTC)
    await save_back_translation(db, session, state)
    return True


async def the_stored_verdicts_clip(session: IRSession, verdict: VoicedVerdict) -> str:
    """The clip a repeat press hands back: the stored one, in a voice the room still has.

    The verdict keeps its clip and not its words. The words are the guide's side of the
    conversation's last telling-back exchange, which `save_the_spoken_verdict` wrote with it.
    A row written before that exchange carried its `told_back` stamp keeps no words this can
    find, and is answered with its stored clip as before: one clip the tablet cannot play is a
    lesser harm than a press that fails every time and never says `checked` again.
    """
    if not verdict.clip_key:
        return ""
    said = next(
        (
            message.get("text", "")
            for message in reversed(session.messages or [])
            if message.get("role") == "guide" and message.get("told_back")
        ),
        "",
    )
    if not said:
        return verdict.clip_key
    return await in_a_voice_the_room_has(verdict.clip_key, said, language=session.language)
