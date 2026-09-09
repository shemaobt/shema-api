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


#: Generated from `check_doctrine.scan()`, keyed on (file, rule, text) rather than line
#: (Fable maestri, 2026-09-08) so an edit above a site cannot turn every listed site below
#: it stale. Refreshed 2026-09-09 against `main` after ENG-831 (Assessor/planner/
#: stt_recovery/no_report/render_active_probe_contract deleted), ENG-793's ceiling ticket
#: (word ceilings and "dizendo menos" deleted), and ENG-793's split of run_turn.py into
#: nine modules — 198 sites down to 65: the memory window now lives in validated_turn.py,
#: `gemini_*`/`ThinkingLevel.LOW` in llm.py stay for ENG-747, `bridge_mode` in
#: calibration.py/sessions.py/the model files stays for ENG-800. Sorted by file, then
#: rule, then the line the text came from, purely for a readable diff.
ALLOWLIST: list[AllowlistEntry] = [
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
        "app/services/internalization_room/comprehension/probe.py",
        Rule.MODE,
        "def process_choice_freezes_bridge_mode(probe: ActiveProbe | None) -> bool:",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe.py",
        Rule.PROBE,
        "class ProbePurpose(enum.StrEnum):",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/probe.py",
        Rule.PROBE,
        "purpose: ProbePurpose",
    ),
    AllowlistEntry(
        "app/services/internalization_room/comprehension/state.py",
        Rule.MODE,
        "with the session. ``bridge_mode`` itself lives in its own column so intake validation and",
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
        "freeze = process_choice_freezes_bridge_mode(prior_probe)",
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
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.MODE,
        "semantic_ready = bridge_mode is not BridgeMode.CALIBRATION_PENDING and (",
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.MODE,
        'app_context = "\\n\\n".join([bridge_mode_status_line(bridge_mode), comprehension_status])',
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.MODE,
        "[bridge_mode_validator_context(bridge_mode), comprehension_status]",
    ),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.MODE,
        "return ComprehensionTurn(outcome=outcome, bridge_mode=bridge_mode.value, state=new_state)",
    ),
    AllowlistEntry("app/services/internalization_room/live_turn.py", Rule.PROBE, "ProbePurpose,"),
    AllowlistEntry(
        "app/services/internalization_room/live_turn.py",
        Rule.PROBE,
        "id=str(uuid.uuid4()), purpose=ProbePurpose.RECORDING_HANDOFF_CONSENT",
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
    AllowlistEntry(
        "app/services/internalization_room/validated_turn.py",
        Rule.MEMORY_WINDOW,
        "_RECENT_TURNS = 6",
    ),
    AllowlistEntry(
        "app/services/internalization_room/validated_turn.py",
        Rule.MEMORY_WINDOW,
        "for message in messages[-_RECENT_TURNS:]:",
    ),
]
