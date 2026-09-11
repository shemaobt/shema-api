"""One round of the telling-back check: from the correction to the words the Speaker says.

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

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import UnreadableReply, UpstreamServiceError
from app.db.models.internalization_room import IRPromptKey, IRSegment, IRSession
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    CorrectionCheck,
    Finding,
    VoicedVerdict,
    analyse_telling_back,
    closing_block,
    correction_to_verify,
    current_findings,
    findings_after_correction,
    findings_block,
    findings_remaining,
    segments_block,
    the_finding_that_leads,
    verify_correction,
    with_the_whole_stretch_asked_for,
)
from app.services.internalization_room.languages import LANGUAGE_NAMES
from app.services.internalization_room.prompts import get_prompt_text
from app.services.internalization_room.sessions import append_exchange, save_back_translation
from app.services.internalization_room.validated_turn import TurnOutcome
from app.services.internalization_room.verdict_turn import run_verdict_turn


@dataclass(frozen=True)
class TellingBackVerdict:
    """What one round decided, and what the room is about to say about it.

    `finding` is the half that carries the address — the one finding, or the addition of a
    **Swap** — and `current` is everything this turn is allowed to voice. `said` already
    carries the request for the whole stretch where there is one, so the caller synthesizes
    it as it stands.
    """

    finding: Finding | None
    current: list[Finding]
    #: What the model answered *this* round — the whole reading, or what the Correction check
    #: raised. Distinct from the standing list, which carries findings forward across rounds:
    #: a measurement of this round's reply read off the standing list counts an earlier round's
    #: answer again every time.
    read_this_round: list[Finding]
    said: str
    outcome: TurnOutcome
    checked: bool
    findings_remaining: int
    verified: CorrectionCheck | None


async def check_the_telling_back(
    session: IRSession,
    *,
    state: BackTranslationState,
    told: list[IRSegment],
    retired: list[IRSegment],
    settings: Settings,
) -> TellingBackVerdict:
    """Read what the team told back, settle the findings, and voice one of them.

    Three readings are possible and exactly one runs. A retelling that answers the standing
    finding is a **Correction check** about one stretch. A telling-back with something new in
    it is a whole reading. And a list the verifications alone emptied gets the closing reading
    that decides `checked`, because a verification answers the finding it was shown and has
    never measured the set.

    Nothing is saved on a reading that could not be made: `checked` strikes the passage off
    the wheel for good, so a passage blessed because the analyst was unreachable would be
    finished by an outage.

    `state` is mutated in place — the findings, the addresses already read and `checked` — and
    writing it is the caller's, in the same transaction as whatever else it decides.
    """
    verified: CorrectionCheck | None = None
    read_this_round: list[Finding] = []
    correction = correction_to_verify(state, told, retired)
    if correction is not None:
        verified = await verify_correction(
            findings=correction.findings,
            earlier=correction.earlier,
            corrected=correction.corrected,
            chunk=correction.chunk,
            scope=state.scope or session.pericope,
            pericope_num=session.pericope,
            correction_prompt=get_prompt_text(IRPromptKey.BT_CORRECTION),
            session_language=LANGUAGE_NAMES[session.language],
            settings=settings,
            session_id=session.id,
        )
        if verified is None:
            raise UpstreamServiceError("a verificação da correção não pôde ser feita agora")
        read_this_round = verified.findings
        state.findings = findings_after_correction(state.findings, verified, correction.corrected)
        state.analysed_segment_ids = [segment.id for segment in told]
        state.verified_since_whole_reading = True
    elif not state.already_analysed(told):
        read = await analyse_telling_back(
            segments=told,
            scope=state.scope or session.pericope,
            pericope_num=session.pericope,
            analyst_prompt=get_prompt_text(IRPromptKey.BT_ANALYST),
            session_language=LANGUAGE_NAMES[session.language],
            language_code=session.language,
            settings=settings,
            session_id=session.id,
        )
        if read is None:
            raise UnreadableReply("a resposta do analista não pôde ser lida")
        read_this_round = read.findings
        state.findings = read.findings
        state.analysed_segment_ids = [segment.id for segment in told]
        state.verified_since_whole_reading = False

    if not state.findings and state.verified_since_whole_reading:
        closing = await analyse_telling_back(
            segments=told,
            scope=state.scope or session.pericope,
            pericope_num=session.pericope,
            analyst_prompt=get_prompt_text(IRPromptKey.BT_ANALYST),
            session_language=LANGUAGE_NAMES[session.language],
            settings=settings,
            session_id=session.id,
        )
        if closing is None:
            raise UpstreamServiceError("a leitura final da tradução não pôde ser feita agora")
        read_this_round = closing.findings
        state.findings = closing.findings
        state.analysed_segment_ids = [segment.id for segment in told]
        state.verified_since_whole_reading = False

    current = current_findings(state)
    finding = the_finding_that_leads(state)
    state.checked = finding is None

    outcome = await run_verdict_turn(
        findings_text=findings_block(current),
        closing=closing_block(finding, checked=state.checked),
        scope=state.scope or session.pericope,
        pericope_num=session.pericope,
        messages=session.messages or [],
        telling_back=segments_block(told),
        speaker_prompt=get_prompt_text(IRPromptKey.BT_VERDICT_SPEAKER),
        validator_prompt=get_prompt_text(IRPromptKey.VALIDATOR),
        session_language=LANGUAGE_NAMES[session.language],
        language_code=session.language,
        settings=settings,
        session_id=session.id,
    )

    said = with_the_whole_stretch_asked_for(
        outcome.speech,
        finding,
        session.language,
        used_fail_safe=outcome.used_fail_safe,
    )
    return TellingBackVerdict(
        finding=finding,
        current=current,
        read_this_round=read_this_round,
        said=said,
        outcome=outcome,
        checked=state.checked,
        findings_remaining=findings_remaining(state.findings),
        verified=verified,
    )


async def save_the_spoken_verdict(
    db: AsyncSession,
    session: IRSession,
    state: BackTranslationState,
    *,
    said: str,
    clip_key: str,
    used_fail_safe: bool,
    fixed_line: str,
) -> IRSession:
    """Write the turn the room just spoke: the exchange, the verdict and the state behind it.

    Called once the words exist as audio, or once the caller has decided there will be none.
    A verdict stored before its clip would be served back by the repeat-press guard as a turn
    the team heard, when what they heard was the error.
    """
    session = await append_exchange(db, session, team_utterance="", guide_response=said)
    state.verdict = VoicedVerdict(
        clip_key=clip_key, fixed_line=fixed_line, used_fail_safe=used_fail_safe
    )
    await save_back_translation(db, session, state)
    return session
