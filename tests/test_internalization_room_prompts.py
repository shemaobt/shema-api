from pathlib import Path

import pytest

from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room import _default_prompts
from app.services.internalization_room.prompts import get_prompt_text


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
