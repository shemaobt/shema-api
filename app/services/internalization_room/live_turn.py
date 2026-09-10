"""The comprehension-aware passage turn.

Order matters — this is the state machine the handoff document calls "app-owned": resolve
the bridge mode (explicit switches only), resolve the recording-handoff consent bound to
the prior persisted question, read what the team's telling settles about practice, and
only then let the Guide speak — or bypass it entirely with exact app-owned speech where
safety demands fixed wording. The consent question becomes state only after it was
actually voiced, so an answer is never bound to an unvoiced prompt.

The Guide checks the retelling itself, item by item against the pinned map, with the whole
conversation in context. Nothing here tells it what it may say next.

The opening turn always belongs to the Guide, because the Voice must open the passage
before anything is asked of the team — frame first, elicit second.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.internalization_room import IRSession
from app.services.internalization_room.canon.elements import elements_for
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.comprehension.checkpoints import (
    checkpoints_for,
    scene_ids_for,
)
from app.services.internalization_room.comprehension.practice import (
    scenes_practiced_by_the_telling_the_guide_invited,
)
from app.services.internalization_room.comprehension.probe import (
    ActiveProbe,
    ProbePurpose,
    select_probe_after_oral_turn,
)
from app.services.internalization_room.comprehension.session_readiness import (
    evaluate_session_comprehension,
    render_comprehension_status,
)
from app.services.internalization_room.comprehension.state import ComprehensionState
from app.services.internalization_room.coverage import (
    CoverageStatus,
    engaged_scene_ids,
    floor_met,
)
from app.services.internalization_room.fail_safe import FailSafe, choose
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.languages import LANGUAGE_NAMES
from app.services.internalization_room.rehearsal_readiness import (
    explicitly_requests_recording_handoff,
    rehearsal_consent_declined_line,
    rehearsal_consent_question,
    rehearsal_readiness_cue,
    resolve_rehearsal_consent,
    should_offer_recording_consent,
)
from app.services.internalization_room.run_turn import (
    TurnOutcome,
    detects_peer_cue,
    run_turn,
)
from app.services.internalization_room.sessions import comprehension_of


@dataclass
class ComprehensionTurn:
    outcome: TurnOutcome
    state: ComprehensionState


def current_scene_id(coverage_state: dict[str, Any], pericope: str) -> str | None:
    """The first scene whose own coverage is not fully engaged.

    It is what the rehearsal the Guide invites is read against: the Guide opens the scene
    the pointer names, and it never selects a scene itself.
    """
    by_scene: dict[int, bool] = {}
    for element in elements_for(pericope):
        if element.scene is None:
            continue
        engaged = coverage_state.get(element.key) == CoverageStatus.ENGAGED.value
        by_scene[element.scene] = by_scene.get(element.scene, True) and engaged
    for scene in sorted(by_scene):
        if not by_scene[scene]:
            return f"S{scene}"
    return None


async def run_comprehension_turn(
    db: AsyncSession,
    session: IRSession,
    *,
    speech: HeardSpeech,
    opening: bool,
    guide_prompt: str,
    validator_prompt: str,
    settings: Settings,
) -> ComprehensionTurn:
    """One comprehension turn: what was heard, what it settles, and what the room says back.

    Only the session's very first line is told in two movements. A file-less POST on a session
    that has already spoken is a re-open, and repeating the panorama there would say the whole
    passage twice and pull the necklace apart again.
    """
    pericope = session.pericope
    book = load_map(pericope).book
    checkpoints = list(checkpoints_for(pericope, book))
    scene_ids = scene_ids_for(pericope)
    messages: list[dict[str, Any]] = list(session.messages or [])
    last_guide = next(
        (m.get("text", "") for m in reversed(messages) if m.get("role") == "guide"), ""
    )
    state = comprehension_of(session)
    prior_probe = state.active_probe

    transcript = speech.text
    uncertain = speech.uncertain
    mother_tongue = speech.mother_tongue
    empty = not transcript.strip()
    reliable = not uncertain and not mother_tongue

    consent_decision = resolve_rehearsal_consent(
        probe=prior_probe,
        previous_guide_utterance=last_guide,
        team_utterance=transcript,
        reliable_bridge_speech=reliable,
    )

    scene_pointer = current_scene_id(session.coverage_state or {}, pericope)
    practiced_now = scenes_practiced_by_the_telling_the_guide_invited(
        prior_probe, last_guide, transcript, reliable, scene_pointer
    )
    projected_practice = list(dict.fromkeys([*state.practiced_scene_ids, *practiced_now]))
    engaged_scenes = engaged_scene_ids(session.coverage_state or {}, pericope)

    comprehension_status = render_comprehension_status(
        checkpoints=checkpoints,
        scene_ids=scene_ids,
        ledger=state.ledger,
        practiced_scene_ids=projected_practice,
        engaged_scene_ids=engaged_scenes,
        current_scene=scene_pointer,
    )

    coverage_complete = floor_met(session.coverage_state or {}, pericope)
    semantic_ready = (
        evaluate_session_comprehension(
            checkpoints=checkpoints,
            scene_ids=scene_ids,
            ledger=state.ledger,
            practiced_scene_ids=projected_practice,
            engaged_scene_ids=engaged_scenes,
        ).evaluation.outcome.value
        != "needs_more_work"
    )
    eligible = coverage_complete and semantic_ready
    resume_requested = (
        state.recording_handoff_paused
        and reliable
        and explicitly_requests_recording_handoff(transcript)
    )

    next_probe: ActiveProbe | None = None
    if not opening and should_offer_recording_consent(
        eligible=eligible,
        paused=state.recording_handoff_paused,
        paused_turns=state.recording_handoff_paused_turns,
        explicit_resume_requested=resume_requested,
        prior_decision=consent_decision,
        reliable_bridge_speech=reliable,
    ):
        next_probe = ActiveProbe(
            id=str(uuid.uuid4()), purpose=ProbePurpose.RECORDING_HANDOFF_CONSENT
        )

    app_owned_line: str | None = None
    if not opening and eligible and consent_decision == "accepted":
        app_owned_line = rehearsal_readiness_cue(session.language)
    elif prior_probe is not None and consent_decision == "declined":
        app_owned_line = rehearsal_consent_declined_line(session.language)
    elif next_probe is not None:
        app_owned_line = rehearsal_consent_question(session.language)

    app_context = comprehension_status

    if mother_tongue:
        line, fixed = choose(FailSafe.OFF_BRIDGE_LANGUAGE, session.language, turn=len(messages))
        outcome = TurnOutcome(
            speech=line, transcript=transcript, used_fail_safe=True, fixed_line=fixed
        )
    elif not opening and (empty or uncertain):
        line, fixed = choose(FailSafe.INAUDIBLE, session.language, turn=len(messages))
        outcome = TurnOutcome(
            speech=line,
            transcript=transcript,
            used_fail_safe=True,
            degraded=True,
            fixed_line=fixed,
        )
    elif app_owned_line is not None:
        outcome = TurnOutcome(
            speech=app_owned_line,
            transcript=transcript,
            peer_cue=detects_peer_cue(app_owned_line),
        )
    else:
        outcome = await run_turn(
            transcript=transcript,
            coverage_state=session.coverage_state or {},
            messages=messages,
            session_language=LANGUAGE_NAMES[session.language],
            language_code=session.language,
            guide_prompt=guide_prompt,
            validator_prompt=validator_prompt,
            pericope_num=pericope,
            book=book,
            opening=opening,
            already_met=session.after_panorama,
            settings=settings,
            session_id=session.id,
            app_context=app_context,
            ask_for_movements=opening and not messages,
        )

    final_probe = select_probe_after_oral_turn(
        outcome="fail_safe" if outcome.used_fail_safe else "pass",
        prior_probe=prior_probe,
        next_probe=next_probe,
        transcript_uncertain=uncertain,
        transcript_was_mother_tongue=mother_tongue,
        transcript_empty=empty,
    )

    new_state = ComprehensionState(
        ledger=state.ledger,
        active_probe=final_probe,
        practiced_scene_ids=projected_practice,
        recording_consent_given=(
            state.recording_consent_given or (eligible and consent_decision == "accepted")
        ),
        recording_handoff_paused=(
            True
            if consent_decision == "declined"
            else False
            if consent_decision == "accepted" or resume_requested
            else state.recording_handoff_paused
        ),
        recording_handoff_paused_turns=(
            0
            if consent_decision in ("accepted", "declined") or resume_requested
            else state.recording_handoff_paused_turns + 1
            if state.recording_handoff_paused and reliable and not empty
            else state.recording_handoff_paused_turns
        ),
    )
    return ComprehensionTurn(outcome=outcome, state=new_state)
