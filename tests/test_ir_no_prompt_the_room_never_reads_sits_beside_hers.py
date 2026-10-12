"""ENG-1303 — no prompt the room never reads sits beside hers.

The old comprehension assessor's instructions stayed in the prompts directory for a month
after the last code that loaded them was deleted, still telling a model to carry open points
to Refine. A text that looks live beside her eight is read as one of them by whoever opens the
directory next, so the directory holds her prompts and the three files of ours the room reads:
the passage names, and the Portuguese fail-safe supplement with its provenance.
"""

from __future__ import annotations

from pathlib import Path

import app.services.internalization_room as room_package

PROMPTS = Path(room_package.__file__).parent / "prompts"

HERS = {
    "backtranslation_analysis_system_prompt.md",
    "backtranslation_verdict_system_prompt.md",
    "book_overview_system_prompt.md",
    "classifier_system_prompt.md",
    "fail_safe_utterances.md",
    "golden_judge_system_prompt.md",
    "guide_system_prompt.md",
    "validator_system_prompt.md",
}
OURS = {
    "passage_lines.md",
    "_fail_safe_pt_supplement.md",
    "_fail_safe_pt_supplement_provenance.md",
}


def test_the_prompts_directory_holds_her_eight_and_the_three_files_of_ours_the_room_reads() -> None:
    on_disk = {path.name for path in PROMPTS.iterdir() if path.is_file()}

    assert on_disk == HERS | OURS, (
        f"um texto que a sala não lê estava ao lado dos dela: {sorted(on_disk - HERS - OURS)}"
    )
