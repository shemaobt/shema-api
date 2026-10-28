from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any

from app.core.config import Settings, get_settings
from app.services.internalization_room.canon.accepted_readings import (
    AcceptedItem,
    accepted_ids_for,
    accepted_readings_block,
    accepted_readings_of,
)
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.canon.scene_ids import scene_ids_for
from app.services.internalization_room.classify_coverage import Retelling
from app.services.internalization_room.fail_safe import inaudible_ladder
from app.services.internalization_room.hearing import SentSceneRehearsal
from app.services.internalization_room.languages import AUTHORED, LANGUAGE_NAMES
from app.services.internalization_room.llm import cache_break_before
from app.services.internalization_room.moment import moment_fact
from app.services.internalization_room.prompt_blocks import (
    RoomFact,
    coverage_status_block,
    earlier_passages_line,
    kept_rehearsals_line,
    meaning_map_block,
    room_facts_block,
    scene_rehearsals_line,
    sent_scene_ids,
    validator_map_block,
)
from app.services.internalization_room.render import render
from app.services.internalization_room.turn_instructions import opening_note
from app.services.internalization_room.validated_turn import TurnOutcome, _voiced_after_validation

logger = logging.getLogger(__name__)


def _kept_scopes(retellings: dict[str, Any] | None) -> list[str]:
    told = [Retelling.model_validate(entry) for entry in (retellings or {}).values()]
    return [retelling.scope for retelling in told if retelling.kept is not None]


def _readings_for(
    pericope_num: str, checked: str | None, session_id: str
) -> tuple[AcceptedItem, ...]:
    if checked is None:
        return ()
    try:
        return accepted_readings_of(pericope_num).items
    except Exception as error:
        logger.warning(
            "[accepted] session=%s scene=%s: no accepted readings reach the Guide (%s)",
            session_id,
            checked,
            type(error).__name__,
        )
        return ()


def accepted_send_backs(attempts: list[dict[str, Any]], ids: list[str]) -> list[dict[str, Any]]:
    if not ids:
        return []
    return [attempt for attempt in attempts if attempt.get("verdict") == "regenerate"]


def _report_send_backs(outcome: TurnOutcome, ids: list[str], checked: str, session_id: str) -> None:
    for attempt in accepted_send_backs(outcome.attempts, ids):
        logger.warning(
            "[accepted-sendback] session=%s scene=%s ids=%s attempt=%s issues=%s",
            session_id,
            checked,
            ids,
            attempt["attempt"],
            attempt["issues"],
        )


async def run_turn(
    *,
    transcript: str,
    coverage_state: dict[str, str],
    messages: list[dict[str, Any]],
    guide_prompt: str,
    validator_prompt: str,
    pericope_num: str,
    session_language: str = LANGUAGE_NAMES[AUTHORED],
    language_code: str = AUTHORED,
    opening: bool = False,
    settings: Settings | None = None,
    session_id: str = "?",
    prepared_pericope: str | None = None,
    earlier_passages: dict[str, str] | None = None,
    scene_rehearsal: SentSceneRehearsal | None = None,
    scene_rehearsals: list[str] | None = None,
    retellings: dict[str, Any] | None = None,
) -> TurnOutcome:
    """One exchange of a passage session: the Guide drafts, the Validator gates.

    `opening` is the session's first turn, where the Guide speaks before the team has.
    The coverage block is the whole of what the app tells the Guide, and the Validator is
    handed none of it — it judges the draft against the map and the team's own words, or, on
    a take in the mother tongue, the room's note that stands for them.

    `prepared_pericope` names this call as `prepare_opening`'s own background run, so the
    `[llm-turn]` line can say which pericope it wrote ahead for. It is set nowhere else:
    a live turn's `session_id` is that session's own, but a prepared one runs under the
    panorama's, and without the tag the two are indistinguishable in the log (ENG-968,
    ENG-1107).

    `earlier_passages` is the session's stamp of this team's status on the earlier passages;
    its fact line rides beside the coverage block, after the cache break, as in her app.

    `scene_rehearsals` is a golden turn's carried list of reached scenes; without one, the
    reached scenes are the labels the session's rehearsals carried when sent, this one's too.
    """
    cfg = settings or get_settings()

    if not opening and not transcript.strip():
        speech, line = inaudible_ladder(language_code)
        return TurnOutcome(
            speech=speech,
            transcript="",
            used_fail_safe=True,
            degraded=True,
            fixed_line=line,
        )

    book = load_map(pericope_num).book
    map_block = meaning_map_block(pericope_num, book, earlier_passages)
    earlier = earlier_passages_line(pericope_num, book, earlier_passages)
    checked = scene_rehearsal.scene if scene_rehearsal else None
    items = _readings_for(pericope_num, checked, session_id)
    accepted = accepted_readings_block(items, checked) if checked else ""
    reached = (
        scene_rehearsals
        if scene_rehearsals is not None
        else sent_scene_ids(messages, scene_rehearsal.scene if scene_rehearsal else None)
    )
    coverage_status = "\n\n".join(
        block
        for block in (
            coverage_status_block(coverage_state, pericope_num),
            room_facts_block(
                {
                    RoomFact.SCENE_REHEARSALS: scene_rehearsals_line(
                        scene_ids_for(pericope_num), reached
                    ),
                    RoomFact.KEPT_REHEARSALS: kept_rehearsals_line(
                        scene_ids_for(pericope_num), _kept_scopes(retellings)
                    ),
                    RoomFact.EARLIER_PASSAGES: earlier,
                    RoomFact.MOMENT: moment_fact(messages, pericope_num, reached, scene_rehearsal),
                    RoomFact.ACCEPTED_READINGS: accepted,
                }
            ),
        )
        if block
    )
    outcome = await _voiced_after_validation(
        speaker_system=render(
            cache_break_before(guide_prompt, "{{COVERAGE_STATUS}}"),
            SESSION_LANGUAGE=session_language,
            MEANING_MAP=map_block,
            COVERAGE_STATUS=coverage_status,
        ),
        validator_prompt=validator_prompt,
        standard_of_truth=validator_map_block(pericope_num, book, earlier_passages),
        transcript=transcript,
        messages=messages,
        session_language=session_language,
        language_code=language_code,
        opening=opening,
        opening_instruction=opening_note(pericope_num, language_code),
        settings=cfg,
        session_id=session_id,
        prepared_pericope=prepared_pericope,
        earlier_passages=earlier,
        first_scene=load_map(pericope_num).scenes[0].title,
    )
    if not checked:
        return outcome
    ids = accepted_ids_for(items, checked)
    _report_send_backs(outcome, ids, checked, session_id)
    return replace(outcome, accepted_ids=ids)
