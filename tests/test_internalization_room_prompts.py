import re
from pathlib import Path

import pytest

from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room import _default_prompts
from app.services.internalization_room.prompts import get_prompt_text

_APP_ROOT = Path(__file__).resolve().parent.parent / "app"
_CALLER_PATTERN = re.compile(r"get_prompt_text\(IRPromptKey\.([A-Z_]+)\)")

#: Already dead when this guard was written, not this ticket's to remove (ENG-736 names only
#: `DRAFT_SELF_CHECK`). Its last caller left in 0b345bf ("the Guide checks the retelling
#: itself, and the probe machinery is gone", 2026-09-08), a day after the sweep that found
#: `DRAFT_SELF_CHECK`. ENG-924 owns removing the key; delete this line in the same commit.
_ALREADY_DEAD_BEFORE_THIS_GUARD = frozenset({IRPromptKey.COMPREHENSION_ASSESSOR})


def test_a_prompt_key_nothing_in_app_asks_for_is_dead_not_reserved() -> None:
    """A key mapped to a file but with no `get_prompt_text` caller is unused, not future work.

    `DRAFT_SELF_CHECK` sat in `IRPromptKey` and `_default_prompts` with a file behind it and
    nothing in `app/` ever asking `get_prompt_text` for it — this is the guard that would
    have said so before the file shipped, and that stops it from coming back unnoticed.
    """
    called = {
        name
        for path in _APP_ROOT.rglob("*.py")
        for name in _CALLER_PATTERN.findall(path.read_text(encoding="utf-8"))
    }

    missing = [
        key.name
        for key in IRPromptKey
        if key.name not in called and key not in _ALREADY_DEAD_BEFORE_THIS_GUARD
    ]

    assert not missing, f"IRPromptKey members with no get_prompt_text caller in app/: {missing}"


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
