"""Every site of a forbidden mechanism `check_doctrine.py` already knows about.

Marcia's ruling (04/09) bans six mechanisms from code: word ceilings, probe/station
contracts, memory windows, "say less" notes, a non-frontier model on the voice, and
app-owned conversation modes. Her own guard, `check-doctrine.mjs` in
`Tripod-Internalization`, is green today because the removals it protects have already
happened there. Ours cannot be: every one of the six is still live in
`app/services/internalization_room` and `app/api/internalization_room`, coming out
under a ladder of separate tickets.

So this file is a scan of the sites as they stand *right now* — one entry per file, rule
and offending line's own text, generated from `check_doctrine.scan()` itself run against
that ladder's starting point. An entry names no line number on purpose: eighteen tickets
in that same ladder touch `live_turn.py` alone, and a line-keyed row would go stale on
every edit above it, on a file the ticket never meant to touch. The guard reports every
hit that is not on this list; a hit that is stays silent. Each removal ticket deletes its
rows here in the same commit that deletes the code, and the guard turns fully blocking
the moment the file is empty.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class Rule(enum.StrEnum):
    CEILING = "ceiling"
    PROBE = "probe"
    MEMORY_WINDOW = "memory_window"
    SAY_LESS = "say_less"
    MODEL = "model"
    MODE = "mode"


@dataclass(frozen=True)
class AllowlistEntry:
    file: str
    rule: Rule
    text: str


#: Generated from `check_doctrine.scan()` against the ladder's starting point (2026-09-08),
#: rekeyed to (file, rule, text) after the line-keyed version proved fragile (Fable maestri,
#: 2026-09-08) — an edit above a site must not turn every listed site below it stale. Sorted
#: by file, then rule, then the line the text came from, purely for a readable diff.
ALLOWLIST: list[AllowlistEntry] = [
    AllowlistEntry(
        "app/api/internalization_room/sessions.py",
        Rule.CEILING,
        "budget=room.OPENING_BUDGET if opening else room.TURN_BUDGET,",
    ),
    AllowlistEntry(
        "app/api/internalization_room/sessions.py", Rule.MODE, "resolve_bridge_mode_for_turn,"
    ),
    AllowlistEntry(
        "app/api/internalization_room/sessions.py", Rule.MODE, "bridge_mode=session.bridge_mode,"
    ),
    AllowlistEntry(
        "app/api/internalization_room/sessions.py", Rule.MODE, "bridge_mode=payload.bridge_mode,"
    ),
    AllowlistEntry(
        "app/api/internalization_room/sessions.py", Rule.MODE, "bridge_mode=session.bridge_mode,"
    ),
    AllowlistEntry(
        "app/api/internalization_room/sessions.py", Rule.MODE, "bridge_mode=session.bridge_mode,"
    ),
    AllowlistEntry(
        "app/api/internalization_room/sessions.py",
        Rule.MODE,
        "if not opening and session.bridge_mode == BridgeMode.CALIBRATION_PENDING.value:",
    ),
    AllowlistEntry(
        "app/api/internalization_room/sessions.py",
        Rule.MODE,
        "session = await room.set_bridge_mode(db, session, resolved.mode.value)",
    ),
    AllowlistEntry(
        "app/api/internalization_room/sessions.py",
        Rule.MODE,
        "switched = resolve_bridge_mode_for_turn(BridgeMode(session.bridge_mode), transcript)",
    ),
    AllowlistEntry(
        "app/api/internalization_room/sessions.py",
        Rule.MODE,
        "session = await room.set_bridge_mode(db, session, switched.mode.value)",
    ),
    AllowlistEntry(
        "app/api/internalization_room/sessions.py",
        Rule.MODE,
        "and session.bridge_mode == BridgeMode.CALIBRATION_PENDING.value",
    ),
    AllowlistEntry(
        "app/api/internalization_room/sessions.py",
        Rule.MODE,
        "session = await room.set_bridge_mode(db, session, turn.bridge_mode)",
    ),
    AllowlistEntry(
        "app/api/internalization_room/sessions.py", Rule.MODE, "bridge_mode=session.bridge_mode,"
    ),
    AllowlistEntry(
        "app/db/models/internalization_room.py",
        Rule.MODE,
        "bridge_mode: Mapped[str] = mapped_column(",
    ),
    AllowlistEntry(
        "app/models/internalization_room.py",
        Rule.MODE,
        "bridge_mode: str | None = Field(default=None, max_length=24)",
    ),
    AllowlistEntry(
        "app/models/internalization_room.py", Rule.MODE, 'bridge_mode: str = "calibration_pending"'
    ),
    AllowlistEntry(
        "app/models/internalization_room.py",
        Rule.MODE,
        "#: Said back so the app can see which language it actually got, the way `bridge_mode` is.",
    ),
    AllowlistEntry(
        "app/models/internalization_room.py", Rule.MODE, 'bridge_mode: str = "calibration_pending"'
    ),
    AllowlistEntry(
        "app/services/internalization_room/__init__.py", Rule.CEILING, "OPENING_BUDGET,"
    ),
    AllowlistEntry("app/services/internalization_room/__init__.py", Rule.CEILING, "TURN_BUDGET,"),
    AllowlistEntry(
        "app/services/internalization_room/__init__.py", Rule.CEILING, '"OPENING_BUDGET",'
    ),
    AllowlistEntry("app/services/internalization_room/__init__.py", Rule.CEILING, '"TURN_BUDGET",'),
    AllowlistEntry("app/services/internalization_room/__init__.py", Rule.MODE, "set_bridge_mode,"),
    AllowlistEntry(
        "app/services/internalization_room/__init__.py", Rule.MODE, '"set_bridge_mode",'
    ),
    AllowlistEntry(
        "app/services/internalization_room/calibration.py", Rule.MODE, 'FULL_RETELL = "full_retell"'
    ),
    AllowlistEntry(
        "app/services/internalization_room/calibration.py",
        Rule.MODE,
        'GUIDED_MICROCHECKS = "guided_microchecks"',
    ),
    AllowlistEntry(
        "app/services/internalization_room/calibration.py",
        Rule.MODE,
        "def is_selected_bridge_mode(value: object) -> bool:",
    ),
    AllowlistEntry(
        "app/services/internalization_room/calibration.py",
        Rule.MODE,
        "def resolve_bridge_mode_for_turn(",
    ),
    AllowlistEntry(
        "app/services/internalization_room/calibration.py",
        Rule.MODE,
        "def bridge_mode_status_line(mode: BridgeMode) -> str:",
    ),
    AllowlistEntry(
        "app/services/internalization_room/calibration.py",
        Rule.MODE,
        "def bridge_mode_validator_context(mode: BridgeMode) -> str:",
    ),
    AllowlistEntry(
        "app/services/internalization_room/calibration.py",
        Rule.MODE,
        'return f"[APP-OWNED SESSION STATE — not team speech]\\n{bridge_mode_status_line(mode)}"',
    ),
    AllowlistEntry(
        "app/services/internalization_room/calibration.py",
        Rule.PROBE,
        'return f"BRIDGE MODE: {mode.value}"',
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/assessor.py",
        Rule.MODE,
        '"bridge_mode": mode.value,',
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/no_report.py",
        Rule.PROBE,
        "from app.services.internalization_room.comprehension.probe import ActiveProbe, is_process_only",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/no_report.py",
        Rule.PROBE,
        "or is_process_only(probe)",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/practice.py", Rule.PROBE, "ProbePurpose,"
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/practice.py",
        Rule.PROBE,
        "is_process_only,",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/practice.py",
        Rule.PROBE,
        "if planned_probe is None or planned_probe.purpose is not ProbePurpose.MOTHER_TONGUE_PRACTICE:",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/practice.py",
        Rule.PROBE,
        "if prior_probe is None or prior_probe.purpose is not ProbePurpose.MOTHER_TONGUE_PRACTICE:",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/practice.py",
        Rule.PROBE,
        "and is_process_only(prior_probe)",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/practice.py",
        Rule.PROBE,
        "and prior_probe.purpose is not ProbePurpose.MOTHER_TONGUE_PRACTICE",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe.py",
        Rule.MODE,
        "def process_choice_freezes_bridge_mode(",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe.py",
        Rule.PROBE,
        "class ProbePurpose(enum.StrEnum):",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe.py",
        Rule.PROBE,
        'MOTHER_TONGUE_PRACTICE = "mother_tongue_practice"',
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe.py",
        Rule.PROBE,
        'SCENE_OPENING = "scene_opening"',
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe.py",
        Rule.PROBE,
        "PROCESS_ONLY_PURPOSES = frozenset(",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe.py",
        Rule.PROBE,
        "ProbePurpose.MOTHER_TONGUE_PRACTICE,",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe.py",
        Rule.PROBE,
        "ProbePurpose.SCENE_OPENING,",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe.py",
        Rule.PROBE,
        "ProbePurpose.CARRY_TO_REFINE_CHOICE,",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe.py",
        Rule.PROBE,
        "ProbePurpose.RECORDING_HANDOFF_CONSENT,",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe.py",
        Rule.PROBE,
        "{ProbePurpose.MOTHER_TONGUE_PRACTICE, ProbePurpose.SCENE_OPENING}",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe.py",
        Rule.PROBE,
        "purpose: ProbePurpose",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe.py",
        Rule.PROBE,
        "if purpose in (ProbePurpose.MOTHER_TONGUE_PRACTICE, ProbePurpose.SCENE_OPENING):",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe.py",
        Rule.PROBE,
        "elif purpose is ProbePurpose.RECORDING_HANDOFF_CONSENT:",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe.py",
        Rule.PROBE,
        "elif purpose is ProbePurpose.CARRY_TO_REFINE_CHOICE:",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe.py",
        Rule.PROBE,
        "ProbePurpose.MOTHER_TONGUE_PRACTICE,",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe.py",
        Rule.PROBE,
        "ProbePurpose.SCENE_OPENING,",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe.py",
        Rule.PROBE,
        "ProbePurpose.RECORDING_HANDOFF_CONSENT,",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe.py",
        Rule.PROBE,
        "ProbePurpose.FREE_RETELL,",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe.py",
        Rule.PROBE,
        "purpose is ProbePurpose.FREE_RETELL",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe.py",
        Rule.PROBE,
        "purpose is ProbePurpose.CLARIFY_CONFLICT",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe.py",
        Rule.PROBE,
        "def is_process_only(probe: ActiveProbe) -> bool:",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe.py",
        Rule.PROBE,
        "return probe.purpose in PROCESS_ONLY_PURPOSES",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe.py",
        Rule.PROBE,
        "return probe is not None and probe.purpose in PROCESS_ONLY_PURPOSES",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe.py",
        Rule.PROBE,
        "if prior_probe is not None and is_process_only(prior_probe):",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe.py",
        Rule.PROBE,
        "if probe is None or probe.purpose is not ProbePurpose.CARRY_TO_REFINE_CHOICE:",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py",
        Rule.MODE,
        "returning_to_full_retell: bool = False",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py",
        Rule.MODE,
        "or input_.returning_to_full_retell",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py",
        Rule.PROBE,
        "PROCESS_ONLY_PURPOSES,",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py", Rule.PROBE, "ProbePurpose,"
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py",
        Rule.PROBE,
        "purpose: ProbePurpose,",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py",
        Rule.PROBE,
        "def plan_next_probe(input_: ProbePlanInput) -> ActiveProbe | None:",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py",
        Rule.PROBE,
        "ProbePurpose.INITIAL_CHECK,",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py",
        Rule.PROBE,
        "ProbePurpose.FREE_RETELL,",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py",
        Rule.PROBE,
        "purpose=ProbePurpose.MOTHER_TONGUE_PRACTICE,",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py",
        Rule.PROBE,
        "purpose=ProbePurpose.SCENE_OPENING,",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py",
        Rule.PROBE,
        "input_, [conflict], EvidenceMethod.MICRO_TELLBACK, ProbePurpose.CLARIFY_CONFLICT",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py",
        Rule.PROBE,
        "purpose=ProbePurpose.CARRY_TO_REFINE_CHOICE,",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py",
        Rule.PROBE,
        "input_, comfortable, EvidenceMethod.FREE_BRIDGE_RETELL, ProbePurpose.FREE_RETELL",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py",
        Rule.PROBE,
        "ProbePurpose.INITIAL_CHECK,",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py",
        Rule.PROBE,
        "ProbePurpose.INITIAL_CHECK,",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py",
        Rule.PROBE,
        "ProbePurpose.TRIANGULATE,",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py",
        Rule.PROBE,
        "return _probe(input_, [target], _first_focused_method(target), ProbePurpose.INITIAL_CHECK)",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py",
        Rule.PROBE,
        "_PURPOSE_INSTRUCTION: dict[ProbePurpose, tuple[str, str]] = {",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py",
        Rule.PROBE,
        "ProbePurpose.MOTHER_TONGUE_PRACTICE: (",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py",
        Rule.PROBE,
        "ProbePurpose.SCENE_OPENING: (",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py",
        Rule.PROBE,
        "ProbePurpose.CARRY_TO_REFINE_CHOICE: (",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py",
        Rule.PROBE,
        "ProbePurpose.RECORDING_HANDOFF_CONSENT: (",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py",
        Rule.PROBE,
        "ProbePurpose.FREE_RETELL: (",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py",
        Rule.PROBE,
        "def render_active_probe_contract(",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py",
        Rule.PROBE,
        '"ACTIVE COMPREHENSION PROBE (APP-OWNED): none; recording handoff is paused "',
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py",
        Rule.PROBE,
        '"ACTIVE COMPREHENSION PROBE (APP-OWNED): none for this process turn.\\n"',
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py",
        Rule.PROBE,
        '"ACTIVE COMPREHENSION PROBE (APP-OWNED): none.\\n"',
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py",
        Rule.PROBE,
        '"ACTIVE COMPREHENSION PROBE (APP-OWNED): none.\\n"',
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py",
        Rule.PROBE,
        "process_only = probe.purpose in PROCESS_ONLY_PURPOSES",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe_plan.py",
        Rule.PROBE,
        '"ACTIVE COMPREHENSION PROBE (APP-OWNED; applies to the NEXT team answer):",',
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/state.py",
        Rule.MODE,
        "with the session. ``bridge_mode`` itself lives in its own column so intake validation and",
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py", Rule.CEILING, "OPENING_BUDGET,"
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py", Rule.CEILING, "SCENE_MOVEMENT_BUDGET,"
    ),
    AllowlistEntry("app/services/internalization_room/live_turn.py", Rule.CEILING, "TURN_BUDGET,"),
    AllowlistEntry("app/services/internalization_room/live_turn.py", Rule.CEILING, "SpeechBudget,"),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.CEILING,
        "def speech_budget_for(opening: bool, next_probe: ActiveProbe | None) -> SpeechBudget:",
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py", Rule.CEILING, "return OPENING_BUDGET"
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.CEILING,
        "return SCENE_MOVEMENT_BUDGET",
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py", Rule.CEILING, "return TURN_BUDGET"
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.CEILING,
        "budget=speech_budget_for(opening, next_probe),",
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py", Rule.MODE, "bridge_mode_status_line,"
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.MODE,
        "bridge_mode_validator_context,",
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py", Rule.MODE, "resolve_bridge_mode_for_turn,"
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.MODE,
        "process_choice_freezes_bridge_mode,",
    ),
    AllowlistEntry("app/services/internalization_room/live_turn.py", Rule.MODE, "bridge_mode: str"),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.MODE,
        "freeze = process_choice_freezes_bridge_mode(prior_probe, recovery_choice_pending)",
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.MODE,
        "current_mode = BridgeMode(session.bridge_mode)",
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.MODE,
        "bridge_mode = resolve_one_shot_calibration(choice_speech).mode",
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.MODE,
        "bridge_mode = resolve_bridge_mode_for_turn(current_mode, choice_speech).mode",
    ),
    AllowlistEntry("app/services/internalization_room/live_turn.py", Rule.MODE, "bridge_mode"),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.MODE,
        "if bridge_mode is not BridgeMode.CALIBRATION_PENDING",
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.MODE,
        "semantic_ready = bridge_mode is not BridgeMode.CALIBRATION_PENDING and (",
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.MODE,
        'if opening or bridge_mode is BridgeMode.CALIBRATION_PENDING or consent_decision == "accepted":',
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py", Rule.MODE, "mode=bridge_mode,"
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py", Rule.MODE, "returning_to_full_retell=("
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.MODE,
        "bridge_mode is BridgeMode.FULL_RETELL",
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.MODE,
        "bridge_mode is BridgeMode.ADAPTIVE",
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.MODE,
        "[bridge_mode_status_line(bridge_mode), comprehension_status, contract]",
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.MODE,
        "[bridge_mode_validator_context(bridge_mode), comprehension_status, contract]",
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.MODE,
        "return ComprehensionTurn(outcome=outcome, bridge_mode=bridge_mode.value, state=new_state)",
    ),
    AllowlistEntry("app/services/internalization_room/live_turn.py", Rule.PROBE, "ProbePurpose,"),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py", Rule.PROBE, "is_process_only,"
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py", Rule.PROBE, "plan_next_probe,"
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.PROBE,
        "render_active_probe_contract,",
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.PROBE,
        "if prior_probe is not None and not is_process_only(prior_probe):",
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.PROBE,
        "and not is_process_only(prior_probe)",
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.PROBE,
        "and prior_probe.purpose is ProbePurpose.CARRY_TO_REFINE_CHOICE",
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.PROBE,
        "if prior_probe is not None and prior_probe.purpose is ProbePurpose.CLARIFY_CONFLICT",
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.PROBE,
        "and prior_probe.purpose is ProbePurpose.FREE_RETELL",
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.PROBE,
        "purpose=ProbePurpose.CARRY_TO_REFINE_CHOICE,",
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.PROBE,
        "and prior_probe.purpose is ProbePurpose.CARRY_TO_REFINE_CHOICE",
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.PROBE,
        "planned_probe = plan_next_probe(",
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.PROBE,
        "purpose=ProbePurpose.RECORDING_HANDOFF_CONSENT,",
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.PROBE,
        "and prior_probe.purpose is ProbePurpose.RECORDING_HANDOFF_CONSENT",
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.PROBE,
        "elif next_probe is not None and next_probe.purpose is ProbePurpose.RECORDING_HANDOFF_CONSENT:",
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.PROBE,
        "contract = render_active_probe_contract(",
    ),
    AllowlistEntry(
        "app/services/internalization_room/llm.py", Rule.MODEL, "return settings.gemini_fast_model"
    ),
    AllowlistEntry(
        "app/services/internalization_room/llm.py",
        Rule.MODEL,
        "DELIBERATE = types.ThinkingLevel.LOW",
    ),
    AllowlistEntry(
        "app/services/internalization_room/prepare_opening.py",
        Rule.CEILING,
        "from app.services.internalization_room.run_turn import OPENING_BUDGET, run_turn",
    ),
    AllowlistEntry(
        "app/services/internalization_room/prepare_opening.py",
        Rule.CEILING,
        "budget=OPENING_BUDGET,",
    ),
    AllowlistEntry(
        "app/services/internalization_room/rehearsal_readiness.py",
        Rule.PROBE,
        "from app.services.internalization_room.comprehension.probe import ActiveProbe, ProbePurpose",
    ),
    AllowlistEntry(
        "app/services/internalization_room/rehearsal_readiness.py",
        Rule.PROBE,
        "or probe.purpose is not ProbePurpose.RECORDING_HANDOFF_CONSENT",
    ),
    AllowlistEntry(
        "app/services/internalization_room/release.py",
        Rule.MODE,
        "if session.bridge_mode == BridgeMode.CALIBRATION_PENDING.value:",
    ),
    AllowlistEntry(
        "app/services/internalization_room/release.py",
        Rule.MODE,
        '"bridge_mode": session.bridge_mode,',
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py", Rule.CEILING, "MAX_SPOKEN_TURN_WORDS = 45"
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.CEILING,
        "MAX_SPOKEN_TURN_SENTENCES = 3",
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.CEILING,
        "MAX_SPOKEN_PANORAMA_WORDS = 90",
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.CEILING,
        "MAX_SPOKEN_PANORAMA_SENTENCES = 6",
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.CEILING,
        "MAX_SPOKEN_INVITATION_WORDS = 25",
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.CEILING,
        "MAX_SPOKEN_INVITATION_SENTENCES = 2",
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py", Rule.CEILING, "class SpeechBudget:"
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.CEILING,
        "TURN_BUDGET = SpeechBudget(MAX_SPOKEN_TURN_WORDS, MAX_SPOKEN_TURN_SENTENCES)",
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.CEILING,
        "PANORAMA_BUDGET = SpeechBudget(MAX_SPOKEN_PANORAMA_WORDS, MAX_SPOKEN_PANORAMA_SENTENCES)",
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.CEILING,
        "SCENE_MOVEMENT_BUDGET = SpeechBudget(",
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.CEILING,
        "MAX_SPOKEN_TURN_WORDS + MAX_SPOKEN_INVITATION_WORDS,",
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.CEILING,
        "MAX_SPOKEN_TURN_SENTENCES + MAX_SPOKEN_INVITATION_SENTENCES,",
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.CEILING,
        "OPENING_BUDGET = SpeechBudget(",
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.CEILING,
        "MAX_SPOKEN_PANORAMA_WORDS + SCENE_MOVEMENT_BUDGET.words,",
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.CEILING,
        "MAX_SPOKEN_PANORAMA_SENTENCES + SCENE_MOVEMENT_BUDGET.sentences,",
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.CEILING,
        "return TURN_BUDGET.fits(text)",
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.CEILING,
        "def _broken_ceiling(speech: str, movements: list[str], budget: SpeechBudget) -> SpeechBudget | None:",
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.CEILING,
        "for text, ceiling in zip(movements, (PANORAMA_BUDGET, SCENE_MOVEMENT_BUDGET), strict=True):",
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.CEILING,
        "budget: SpeechBudget | None = None,",
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.CEILING,
        "broken = _broken_ceiling(speech, movements, budget) if speech and budget else None",
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.CEILING,
        'issues = [*issues, {"problem": "over_speech_budget"}]',
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.CEILING,
        '"over_speech_budget", session_id, attempt + 1, f"{len(speech)} characters"',
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.CEILING,
        "budget: SpeechBudget | None = None,",
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.CEILING,
        "budget: SpeechBudget | None = None,",
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.CEILING,
        "_OVER_BUDGET_NOTE: dict[str, str] = {",
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.CEILING,
        "ceiling: SpeechBudget | None = None,",
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.CEILING,
        'if any(issue.get("problem") == "over_speech_budget" for issue in issues):',
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.CEILING,
        "held = ceiling or TURN_BUDGET",
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.CEILING,
        "template = _OVER_BUDGET_NOTE.get(language_code, _OVER_BUDGET_NOTE[FLOOR])",
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py", Rule.MEMORY_WINDOW, "_RECENT_TURNS = 6"
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.MEMORY_WINDOW,
        "for message in messages[-_RECENT_TURNS:]:",
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.SAY_LESS,
        "_OVER_BUDGET_NOTE: dict[str, str] = {",
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.SAY_LESS,
        '"pt": "A resposta anterior não passou na conferência. Refaça, dizendo menos.",',
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.SAY_LESS,
        '"en": "The previous response did not pass review. Redo it, saying less.",',
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.SAY_LESS,
        '"apontados — {described}. Refaça o turno sem essas afirmações, dizendo menos."',
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.SAY_LESS,
        '"{described}. Redo the turn without those claims, saying less."',
    ),
    AllowlistEntry(
        "app/services/internalization_room/run_turn.py",
        Rule.SAY_LESS,
        "template = _OVER_BUDGET_NOTE.get(language_code, _OVER_BUDGET_NOTE[FLOOR])",
    ),
    AllowlistEntry(
        "app/services/internalization_room/sessions.py",
        Rule.MODE,
        "from app.services.internalization_room.calibration import BridgeMode, is_selected_bridge_mode",
    ),
    AllowlistEntry(
        "app/services/internalization_room/sessions.py",
        Rule.MODE,
        "bridge_mode: str | None = None,",
    ),
    AllowlistEntry(
        "app/services/internalization_room/sessions.py",
        Rule.MODE,
        "if bridge_mode is not None and not is_selected_bridge_mode(bridge_mode):",
    ),
    AllowlistEntry(
        "app/services/internalization_room/sessions.py",
        Rule.MODE,
        'raise ValidationError(f"Unknown bridge mode {bridge_mode!r}")',
    ),
    AllowlistEntry(
        "app/services/internalization_room/sessions.py", Rule.MODE, "if bridge_mode is None:"
    ),
    AllowlistEntry("app/services/internalization_room/sessions.py", Rule.MODE, "bridge_mode = ("),
    AllowlistEntry(
        "app/services/internalization_room/sessions.py", Rule.MODE, "bridge_mode=bridge_mode,"
    ),
    AllowlistEntry(
        "app/services/internalization_room/sessions.py",
        Rule.MODE,
        "async def set_bridge_mode(db: AsyncSession, session: IRSession, mode: str) -> IRSession:",
    ),
    AllowlistEntry(
        "app/services/internalization_room/sessions.py",
        Rule.MODE,
        "if not is_selected_bridge_mode(mode) and mode != BridgeMode.CALIBRATION_PENDING.value:",
    ),
    AllowlistEntry(
        "app/services/internalization_room/sessions.py", Rule.MODE, "session.bridge_mode = mode"
    ),
    AllowlistEntry(
        "app/services/internalization_room/sessions.py",
        Rule.MODE,
        "if session.bridge_mode == BridgeMode.CALIBRATION_PENDING.value:",
    ),
]
