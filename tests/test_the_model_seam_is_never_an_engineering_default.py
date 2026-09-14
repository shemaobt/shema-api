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


def _fixture_tree(tmp_path: Path, fallback: str, calls: str) -> Path:
    config = tmp_path / "app/core/config.py"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        "class Settings:\n    tripod_voice_model: str = 'claude-fable-5-1'\n", encoding="utf-8"
    )
    room = tmp_path / "app/services/internalization_room"
    room.mkdir(parents=True, exist_ok=True)
    (room / "llm.py").write_text(
        "async def call_agent(\n"
        "    *,\n"
        "    ladder: list[str] | None = None,\n"
        "    max_output_tokens: int = 2000,\n"
        "    effort: str = 'high',\n"
        "    thinks: bool = True,\n"
        ") -> str:\n"
        f"    rungs = ladder or {fallback}\n"
        "    return ''\n",
        encoding="utf-8",
    )
    (room / "room.py").write_text(calls, encoding="utf-8")
    (tmp_path / "app/api/internalization_room").mkdir(parents=True, exist_ok=True)
    return tmp_path


def test_the_ladder_a_site_inherits_is_read_from_the_code_and_never_written_here(
    tmp_path: Path,
) -> None:
    """A site passing no ladder runs on whatever `call_agent` falls back to, and that moves.

    The first version of this reader wrote the words `voice_ladder(settings)` into the row itself
    when a site named no ladder, so the rung the team hears could be changed in `llm.py` with the
    record still agreeing — the one thing §5.1 exists to stop. The fallback is read off the
    assignment now, the way the other three governed parameters are read off the signature.
    """
    root = _fixture_tree(
        tmp_path,
        "panorama_ladder(settings)",
        "async def _draft() -> str:\n    return await call_agent(max_output_tokens=4096)\n",
    )

    seam = model_seam(root)

    assert seam["app/services/internalization_room/room.py::_draft"] == (
        "ladder=panorama_ladder(settings) max_output_tokens=4096 effort='high' thinks=True"
    ), f"the row does not carry the ladder this tree actually falls back to: {seam}"


def test_two_model_calls_in_one_function_are_not_one_row(tmp_path: Path) -> None:
    """Keyed by the function, so the second call used to land on the first one's row.

    It does not fire in today's tree — five sites in five functions — but a second call added to
    `_draft` would have been reported as one `moved:` naming the wrong site, and updating that row
    to match would leave the first call's budget, effort and thinking ungoverned from then on.
    """
    root = _fixture_tree(
        tmp_path,
        "voice_ladder(settings)",
        "async def _draft() -> str:\n"
        "    first = await call_agent(max_output_tokens=4096)\n"
        "    return await call_agent(max_output_tokens=512, thinks=False)\n",
    )

    seam = model_seam(root)

    assert sorted(seam) == [
        "app/core/config.py::tripod_voice_model",
        "app/services/internalization_room/room.py::_draft",
        "app/services/internalization_room/room.py::_draft#2",
    ], f"the second call in the function did not get a row of its own: {sorted(seam)}"
    assert "max_output_tokens=512" in seam["app/services/internalization_room/room.py::_draft#2"]
