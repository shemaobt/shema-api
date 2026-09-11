from __future__ import annotations

from functools import cache, lru_cache
from pathlib import Path

from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room.languages import ROOM_LANGUAGES

_PROMPTS_DIR = Path(__file__).parent / "prompts"

_FILES: dict[IRPromptKey, str] = {
    IRPromptKey.GUIDE: "guide_system_prompt.md",
    IRPromptKey.VALIDATOR: "validator_system_prompt.md",
    IRPromptKey.COVERAGE_CLASSIFIER: "classifier_system_prompt.md",
    IRPromptKey.BOOK_PANORAMA: "book_overview_system_prompt.md",
    IRPromptKey.BT_ANALYST: "backtranslation_analysis_system_prompt.md",
    IRPromptKey.BT_CORRECTION: "backtranslation_correction_system_prompt.md",
    IRPromptKey.BT_VERDICT_SPEAKER: "backtranslation_verdict_system_prompt.md",
    IRPromptKey.COMPREHENSION_ASSESSOR: "comprehension_evidence_system_prompt.md",
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
    IRPromptKey.BT_ANALYST: (
        "BT Analyst",
        "Achados da tradução: missing, addition, unclear. Nunca é falado.",
    ),
    IRPromptKey.BT_CORRECTION: (
        "BT Correction",
        "Verifica uma correção contra o achado que ela responde. Forma varia, conteúdo não.",
    ),
    IRPromptKey.BT_VERDICT_SPEAKER: (
        "BT Verdict Speaker",
        "Voz do veredito da tradução: um achado por turno, e para.",
    ),
    IRPromptKey.COMPREHENSION_ASSESSOR: (
        "Comprehension Evidence Assessor",
        "Classifica evidência semântica da resposta ao probe autorizado. Nunca é falado.",
    ),
}


@cache
def load_prompt(key: IRPromptKey) -> str:
    return (_PROMPTS_DIR / _FILES[key]).read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def fail_safe_utterances() -> str:
    """App-side strings, not a model call — kept beside the prompts they replace.

    The authored file is concatenated with our own supplements, one per language, which are
    kept separate so the authored one stays byte-identical to the project's own copy. Order
    matters only in that the reader prefers a language-tagged block, and each section has at
    most one per language.

    **Named off the languages the room claims, never globbed.** A glob made being read the
    default: the Spanish draft sat beside the authored file marked "nothing here has been
    approved to be spoken to a team" and was spoken anyway, to anyone who asked for the
    language. Claiming a language is the deliberate act, and this follows it — a draft for a
    language the room does not offer stays in the repository and reaches no mouth.
    """
    parts = [(_PROMPTS_DIR / "fail_safe_utterances.md").read_text(encoding="utf-8")]
    for language_code in ROOM_LANGUAGES:
        supplement = _PROMPTS_DIR / f"_fail_safe_{language_code}_supplement.md"
        if supplement.exists():
            parts.append(supplement.read_text(encoding="utf-8"))
    return "\n\n".join(parts)


def default_prompt(key: IRPromptKey) -> dict[str, str]:
    name, description = _META[key]
    return {"name": name, "description": description, "prompt": load_prompt(key)}
