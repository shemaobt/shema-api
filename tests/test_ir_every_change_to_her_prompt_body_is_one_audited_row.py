"""What the room changes in her prompt body is a list of rows, and a row that stops matching fails.

Her target is her current prompts whole, with only the sentences that describe a screen adapted,
each one with her word (r4:11). A key that reads her body can differ from it only by a row in
`prompt_adaptations.ADAPTATIONS`: her exact text, ours (empty for a removal), and where her word
for it is written, or PENDING. A row whose sentence no longer occurs exactly once is her text
having moved under us, and it goes back to her instead of being patched to match.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.services.internalization_room.prompt_adaptations import Adaptation, adapt, faults
from scripts import sync_doctrine
from scripts.sync_doctrine import REPO_ROOT, adaptation_faults

BODY = "Speak plainly. Tap the orange dot. Never say the map."


def test_a_row_replaces_her_exact_sentence_once_and_rows_apply_in_order() -> None:
    rows = (
        Adaptation("guide", "Tap the orange dot.", "Tap the green button.", "r4:76"),
        Adaptation("guide", "the green button", "the green microphone button", "r5:23"),
    )

    assert adapt("guide", BODY, rows) == (
        "Speak plainly. Tap the green microphone button. Never say the map."
    )


def test_a_removal_row_takes_her_sentence_out_and_a_row_for_another_key_is_not_applied() -> None:
    rows = (
        Adaptation("guide", " Tap the orange dot.", "", "PENDING — r6 §2"),
        Adaptation("validator", "Speak plainly.", "", "r4:76"),
    )

    assert adapt("guide", BODY, rows) == "Speak plainly. Never say the map."


@pytest.mark.parametrize(("hers", "found"), [("Tap the red microphone.", 0), (". ", 2)])
def test_a_sentence_of_hers_that_moved_is_refused_not_patched(hers: str, found: int) -> None:
    rows = (Adaptation("guide", hers, "", "r4:76"),)

    with pytest.raises(ValueError, match=f"guide: her text occurs {found} times"):
        adapt("guide", BODY, rows)


def test_the_check_names_every_row_that_would_not_apply_or_names_no_source() -> None:
    rows = (
        Adaptation("guide", "Tap the orange dot.", "", ""),
        Adaptation("guide", "Tap the red microphone.", "", "r4:76"),
        Adaptation("panorama", "Speak plainly.", "", "r4:76"),
    )

    assert faults({"guide": BODY}, rows) == [
        "guide: a row names no source: 'Tap the orange dot.'",
        "panorama: a row for a prompt that does not read her body: 'Speak plainly.'",
        "guide: her text occurs 0 times, not once: 'Tap the red microphone.'",
    ]
    assert faults({"guide": BODY}, (Adaptation("guide", "Speak plainly.", "", "r4:76"),)) == []


def test_the_doctrine_check_reads_the_table_and_her_vendored_body_without_booting_the_app(
    tmp_path: Path,
) -> None:
    """CI runs `sync_doctrine.py --check` with no settings, so it loads both modules by path.

    The copy of the real extractor is the point: a check that only exercised a fake would pass
    with the path-loading broken. The live tree is the control.
    """
    room = tmp_path / "app/services/internalization_room"
    (room / "prompts/vendor").mkdir(parents=True)
    shutil.copy(REPO_ROOT / "app/services/internalization_room/prompt_body.py", room)
    (room / "prompts/vendor/classifier_system_prompt.md").write_text(
        "notes\n`=== BEGIN SYSTEM PROMPT ===`\nClassify the exchange.\n"
        "`=== END SYSTEM PROMPT ===`\n",
        encoding="utf-8",
    )
    table = (REPO_ROOT / "app/services/internalization_room/prompt_adaptations.py").read_text()
    (room / "prompt_adaptations.py").write_text(
        table
        + '\nHER_FILES = {"coverage_classifier": "classifier_system_prompt.md"}\n'
        + 'ADAPTATIONS = (Adaptation("coverage_classifier", "Classify the turn.", "", "r4:76"),)\n',
        encoding="utf-8",
    )

    assert adaptation_faults(tmp_path) == [
        "coverage_classifier: her text occurs 0 times, not once: 'Classify the turn.'"
    ]
    assert adaptation_faults(REPO_ROOT) == []


def test_a_row_that_would_not_apply_fails_the_doctrine_check_ci_runs(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    moved = "coverage_classifier: her text occurs 0 times, not once: 'Classify the turn.'"
    monkeypatch.setattr(sync_doctrine, "adaptation_faults", lambda: [moved])

    assert sync_doctrine.check() == 1, "uma frase dela que mudou passava o CI em silêncio"
    assert moved in capsys.readouterr().err
