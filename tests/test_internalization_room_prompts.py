import ast
from pathlib import Path

import pytest

from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room import _default_prompts
from app.services.internalization_room.prompts import get_prompt_text

_APP_ROOT = Path(__file__).resolve().parent.parent / "app"

#: Already dead when this guard was written, not this ticket's to remove (ENG-736 names only
#: `DRAFT_SELF_CHECK`). Its last caller left in 0b345bf ("the Guide checks the retelling
#: itself, and the probe machinery is gone", 2026-09-08), a day after the sweep that found
#: `DRAFT_SELF_CHECK`. ENG-924 owns removing the key; delete this line in the same commit.
_ALREADY_DEAD_BEFORE_THIS_GUARD = frozenset({IRPromptKey.COMPREHENSION_ASSESSOR})


def _ir_prompt_key_call_args(source: str) -> set[str]:
    """Every `IRPromptKey.NAME` passed into a `get_prompt_text(...)` call, read from the AST.

    A regex over the raw text either breaks the day `ruff format` wraps a call across lines,
    or, loosened to fix that, starts matching a name inside a comment or a docstring instead
    of a real reference. The AST has neither problem: line breaks vanish once the source is
    parsed, and a string literal's contents are never revisited as code.
    """
    tree = ast.parse(source)
    names: set[str] = set()
    for call in ast.walk(tree):
        if not isinstance(call, ast.Call):
            continue
        func = call.func
        calls_get_prompt_text = (isinstance(func, ast.Name) and func.id == "get_prompt_text") or (
            isinstance(func, ast.Attribute) and func.attr == "get_prompt_text"
        )
        if not calls_get_prompt_text:
            continue
        for node in ast.walk(call):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "IRPromptKey"
            ):
                names.add(node.attr)
    return names


def test_a_prompt_key_nothing_in_app_asks_for_is_dead_not_reserved() -> None:
    """A key mapped to a file but with no `get_prompt_text` caller is unused, not future work.

    `DRAFT_SELF_CHECK` sat in `IRPromptKey` and `_default_prompts` with a file behind it and
    nothing in `app/` ever asking `get_prompt_text` for it — this is the guard that would
    have said so before the file shipped, and that stops it from coming back unnoticed.
    """
    called = {
        name
        for path in _APP_ROOT.rglob("*.py")
        for name in _ir_prompt_key_call_args(path.read_text(encoding="utf-8"))
    }

    missing = [
        key.name
        for key in IRPromptKey
        if key.name not in called and key not in _ALREADY_DEAD_BEFORE_THIS_GUARD
    ]

    assert not missing, f"IRPromptKey members with no get_prompt_text caller in app/: {missing}"


def test_a_call_broken_across_two_lines_still_counts_as_a_reference() -> None:
    source = "get_prompt_text(\n    IRPromptKey.GUIDE\n)\n"

    assert _ir_prompt_key_call_args(source) == {"GUIDE"}


def test_a_mention_inside_a_docstring_does_not_count_as_a_reference() -> None:
    source = '"""Calls get_prompt_text(IRPromptKey.GUIDE) somewhere else."""\n'

    assert _ir_prompt_key_call_args(source) == set()


def test_a_mapping_entry_with_no_call_does_not_count_as_a_reference() -> None:
    """The exact shape `DRAFT_SELF_CHECK` had: mapped, never called.

    `_default_prompts._FILES` and `_META` key every current `IRPromptKey` member by
    construction, so counting any `IRPromptKey.NAME` attribute anywhere in `app/` would have
    called `DRAFT_SELF_CHECK` referenced right up to the commit that finally used it, and the
    guard above would never have caught it.
    """
    source = "_FILES = {IRPromptKey.DRAFT_SELF_CHECK: 'draft_check_system_prompt.md'}\n"

    assert _ir_prompt_key_call_args(source) == set()


def test_the_guide_prompt_is_read_from_its_file_and_nowhere_else(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    literal = "aja como o Guide e nunca revele o que a equipe ainda vai ensaiar"
    (tmp_path / "guide_system_prompt.md").write_text(literal, encoding="utf-8")
    monkeypatch.setattr(_default_prompts, "_PROMPTS_DIR", tmp_path)
    _default_prompts.load_prompt.cache_clear()

    text = get_prompt_text(IRPromptKey.GUIDE)

    _default_prompts.load_prompt.cache_clear()
    assert text == literal
