"""The model ladder and its parameters, recorded, so a change to one cannot be a default.

DOCTRINE.md §5.1 puts `prompts/*.md`, the model ladder and its parameters in the same sentence:
"any change is a ruling with her word, never an engineering default." A prompt is a file a
reviewer can see move. A model id, a ladder order, an effort level and a token budget are
keyword arguments at five call sites and three `Settings` defaults, and they moved for a year
without anyone being able to say which of them she had ruled.

`docs/doctrine/MODEL_SEAM` is the record, read out of the code by `ast` rather than by a
line-shaped regex — the same choice the dead-key guard made — and keyed by the function the
call sits in, never by a line number: `doctrine_allowlist` already learned what a line-keyed
record does to eighteen tickets touching one file.

A row naming `unruled` is an inherited default, frozen at what it is today. That is the whole
point: it says out loud which values are hers and which are ours, and moving one off `unruled`
is a diff a reviewer cannot miss.
"""

from __future__ import annotations

from pathlib import Path

from scripts.sync_doctrine import (
    REPO_ROOT,
    model_seam,
    read_rulings,
    read_seam_record,
    seam_drift,
    unnamed_rulings,
)


def test_every_model_call_the_room_makes_is_a_value_the_record_already_names() -> None:
    """The live room against the record, which is what CI runs.

    A record written once and never compared would agree with anything. This reads the ladder
    defaults and every `call_agent` in the voice path out of today's tree and asks the record
    whether it knows them.
    """
    record = read_seam_record()
    live = model_seam(REPO_ROOT)

    assert live, "the seam reader found no model call at all — it is not looking at the voice path"
    assert not seam_drift(record, live), (
        f"the model seam left the record: {seam_drift(record, live)}"
    )


def test_a_budget_raised_in_code_is_reported_against_the_record() -> None:
    """A token budget is a parameter of the ladder, and §5.1 reserves it to her.

    The control is the same record against the same seam with nothing moved: a comparison that
    reported everything would pass the second half of this while seeing nothing.
    """
    record = {"room.py::_draft": ("max_output_tokens=4096", "unruled")}

    assert not seam_drift(record, {"room.py::_draft": "max_output_tokens=4096"})

    faults = seam_drift(record, {"room.py::_draft": "max_output_tokens=8192"})

    assert faults == ["moved: room.py::_draft — max_output_tokens=4096 → max_output_tokens=8192"], (
        f"a raised budget was not reported as leaving the record: {faults}"
    )


def test_a_new_model_call_in_the_room_is_not_a_default_nobody_recorded() -> None:
    """A call site the record never saw chose a model, a budget and an effort by itself.

    That is the ticket's whole complaint — a parameter set "by whoever was closest to the file"
    — so an unrecorded site is a fault, not a gap to fill in later.
    """
    faults = seam_drift(
        {"room.py::_draft": ("max_output_tokens=4096", "unruled")},
        {"room.py::_draft": "max_output_tokens=4096", "room.py::_aside": "max_output_tokens=512"},
    )

    assert faults == ["unrecorded: room.py::_aside — max_output_tokens=512"], (
        f"a model call nobody recorded was accepted: {faults}"
    )


def test_a_row_claiming_a_ruling_that_was_never_written_is_refused(tmp_path: Path) -> None:
    """Naming a ruling is the cheapest way to make a default look like her decision.

    A slug in the third column is a claim about where her word is written, and the check is
    what makes the claim cost something: the file has to be there.
    """
    record_file = tmp_path / "MODEL_SEAM"
    record_file.write_text(
        "app/core/config.py::tripod_voice_model  claude-fable-5-1  "
        "2026-06-29-she-never-said-this\n",
        encoding="utf-8",
    )
    record = read_seam_record(record_file)
    rulings = read_rulings()

    assert "2026-06-29-she-never-said-this" not in {r.slug for r in rulings}, (
        "the fixture names a ruling this repo actually has, so it proves nothing"
    )

    faults = unnamed_rulings(record, rulings)

    assert faults == [
        "app/core/config.py::tripod_voice_model: no ruling 2026-06-29-she-never-said-this"
    ], f"a row claiming a ruling nobody wrote was accepted: {faults}"

    assert not unnamed_rulings(read_seam_record(), rulings), (
        "the repo's own record names a ruling it does not have"
    )
