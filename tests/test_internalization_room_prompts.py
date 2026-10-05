import ast
from pathlib import Path

import pytest

from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room import _default_prompts
from app.services.internalization_room.prompts import get_prompt_text

_APP_ROOT = Path(__file__).resolve().parent.parent / "app"


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

    missing = [key.name for key in IRPromptKey if key.name not in called]

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


def test_the_guide_prompt_is_read_from_its_file_between_her_markers_and_nowhere_else(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    literal = "aja como o Guide e nunca revele o que a equipe ainda vai ensaiar"
    (tmp_path / "guide_system_prompt.md").write_text(
        "> **Marcia's ruling 2026-09-24.** Her word: «sim». Everything between the "
        "`=== BEGIN SYSTEM PROMPT ===` and `=== END SYSTEM PROMPT ===` markers is the prompt.\n\n"
        f"`=== BEGIN SYSTEM PROMPT ===`\n\n{literal}\n\n`=== END SYSTEM PROMPT ===`\n\n"
        "Engineering notes for the team, never for the model.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(_default_prompts, "_PROMPTS_DIR", tmp_path)
    _default_prompts.load_prompt.cache_clear()

    text = get_prompt_text(IRPromptKey.GUIDE)

    _default_prompts.load_prompt.cache_clear()
    assert text == literal, (
        "o modelo recebia o arquivo inteiro, com as notas e decisões datadas dela"
    )


HER_BODIES = {
    IRPromptKey.GUIDE: (
        "## Who you are\n\nYou are the team's **Digital Facilitator** — that is your name",
        "{{COVERAGE_STATUS}}",
    ),
    IRPromptKey.VALIDATOR: (
        "## Your role\n\nYou are a strict, careful validator.",
        "{{DRAFTED_RESPONSE}}",
    ),
    IRPromptKey.COVERAGE_CLASSIFIER: (
        "## Your role\n\nYou are a precise bookkeeping classifier",
        "{{GUIDE_RESPONSE}}",
    ),
    IRPromptKey.BOOK_PANORAMA: (
        "## Who you are\n\nYou are the team's **Digital Facilitator** (in Portuguese: "
        "*o Facilitador Digital*)",
        "{{BOOK_MATERIAL}}",
    ),
    IRPromptKey.BT_ANALYST: (
        "## Your role\n\nA translation team recorded this passage in their own language",
        "{{SEGMENTS}}",
    ),
    IRPromptKey.BT_VERDICT_SPEAKER: (
        "## Your role\n\nYou are the same warm voice that has walked this passage with the team.",
        "{{FINDINGS}}",
    ),
}


@pytest.mark.parametrize("key", list(HER_BODIES), ids=lambda key: key.name)
def test_each_role_reads_her_body_from_her_own_file(key: IRPromptKey) -> None:
    first, last = HER_BODIES[key]

    text = get_prompt_text(key)

    assert text.startswith(first), f"{key.name}: o papel não lê o texto dela, lê o nosso"
    assert text.endswith(last), f"{key.name}: o corpo dela não termina onde o marcador dela termina"
    assert "SYSTEM PROMPT ===" not in text, f"{key.name}: um marcador dela chegou ao modelo"
