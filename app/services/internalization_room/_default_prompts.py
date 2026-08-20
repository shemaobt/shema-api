from __future__ import annotations

from functools import cache, lru_cache
from pathlib import Path

from app.db.models.internalization_room import IRPromptKey

_PROMPTS_DIR = Path(__file__).parent / "prompts"

_FILES: dict[IRPromptKey, str] = {
    IRPromptKey.GUIDE: "guide_system_prompt.md",
    IRPromptKey.VALIDATOR: "validator_system_prompt.md",
    IRPromptKey.COVERAGE_CLASSIFIER: "classifier_system_prompt.md",
    IRPromptKey.BOOK_PANORAMA: "book_overview_system_prompt.md",
    IRPromptKey.DRAFT_SELF_CHECK: "draft_check_system_prompt.md",
    IRPromptKey.BT_ANALYST: "backtranslation_analysis_system_prompt.md",
    IRPromptKey.BT_VERDICT_SPEAKER: "backtranslation_verdict_system_prompt.md",
}

_META: dict[IRPromptKey, tuple[str, str]] = {
    IRPromptKey.GUIDE: (
        "Guide",
        "Conduz a sessão de internalização: enquadra, elicia e manda a equipe ensaiar.",
    ),
    IRPromptKey.VALIDATOR: (
        "Validator",
        "Três portões antes de virar voz: mapa, políticas fixas e coerência com a conversa.",
    ),
    IRPromptKey.COVERAGE_CLASSIFIER: (
        "Coverage Classifier",
        "Quatro estados entre o mencionado e o que a equipe trabalhou. Subconta por desenho.",
    ),
    IRPromptKey.BOOK_PANORAMA: (
        "Book Panorama",
        "Panorama do livro antes de entrar na passagem, sem revelar o que ela guarda.",
    ),
    IRPromptKey.DRAFT_SELF_CHECK: (
        "Draft Self-Check",
        "A conferência do ensaio que o modelo não pode ouvir.",
    ),
    IRPromptKey.BT_ANALYST: (
        "BT Analyst",
        "Achados da retrotradução: missing, addition, unclear. Nunca é falado.",
    ),
    IRPromptKey.BT_VERDICT_SPEAKER: (
        "BT Verdict Speaker",
        "Voz do veredito da retrotradução: um achado por turno, e para.",
    ),
}


@cache
def load_prompt(key: IRPromptKey) -> str:
    return (_PROMPTS_DIR / _FILES[key]).read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def fail_safe_utterances() -> str:
    """App-side strings, not a model call — kept beside the prompts they replace.

    The authored file is concatenated with our Portuguese supplement, which is kept separate
    so the authored one stays byte-identical to the project's own copy. Order matters only in
    that the reader prefers a language-tagged block, and each section has at most one.
    """
    authored = (_PROMPTS_DIR / "fail_safe_utterances.md").read_text(encoding="utf-8")
    supplement = _PROMPTS_DIR / "_fail_safe_pt_supplement.md"
    if not supplement.exists():
        return authored
    return f"{authored}\n\n{supplement.read_text(encoding='utf-8')}"


def default_prompt(key: IRPromptKey) -> dict[str, str]:
    name, description = _META[key]
    return {"name": name, "description": description, "prompt": load_prompt(key)}
