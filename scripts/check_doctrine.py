"""The doctrine guard, a Python translation of `check-doctrine.mjs` (2026-09).

The Digital Facilitator's behaviour lives in the prompt, the model, and the whole
conversation. It is lost the moment code starts scripting the pedagogy: speech ceilings,
probe/station contracts that forbid content, memory windows, "say less" redraft notes,
a smaller model on the voice, app-owned conversation modes. Marcia's ruling (04/09) bans
all six from code, and `Tripod-Internalization`'s guard already fails that repo's build
if any returns. This guard carries the same six rules and the same message per rule,
in the Python spellings our voice path actually uses.

Two of her design decisions carry over deliberately. The scan covers code, not prompts —
the prompt files under `internalization_room/prompts/` are Marcia's artifacts, reviewed
by her, not by a grep, so only `.py` is scanned. And it fails loudly, printing the file,
the line, and the doctrine sentence the rule protects, so the message teaches rather than
blocks.

`SCAN_ROOTS` is narrower than her `src`/`app`/`scripts`: ours is the voice path alone —
`app/services/internalization_room`, `app/api/internalization_room`, and the two model
files the session's state lives in. A model none of the six mechanisms touch — the low
thinking budget's identifier is `gemini_*`, and that same substring names a model choice
in nine other parts of the system (ENG-747) that this guard has no business flagging.

The six mechanisms are being deleted under a ladder of separate tickets, not this one, so
the guard cannot be green against an empty allowlist yet. Until the ladder lands,
`doctrine_allowlist.ALLOWLIST` names every site the guard finds today; a hit not on that
list is a violation, and an allowlist entry the scan can no longer confirm is a stale
line nobody deleted. Run as a script:

    uv run python scripts/check_doctrine.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from scripts.doctrine_allowlist import ALLOWLIST, AllowlistEntry, Rule

REPO_ROOT = Path(__file__).resolve().parent.parent

SCAN_ROOTS = (
    REPO_ROOT / "app" / "services" / "internalization_room",
    REPO_ROOT / "app" / "api" / "internalization_room",
    REPO_ROOT / "app" / "models" / "internalization_room.py",
    REPO_ROOT / "app" / "db" / "models" / "internalization_room.py",
)


@dataclass(frozen=True)
class DoctrineRule:
    id: Rule
    pattern: re.Pattern[str]
    message: str


RULES: list[DoctrineRule] = [
    DoctrineRule(
        id=Rule.CEILING,
        pattern=re.compile(
            r"MAX_SPOKEN_[A-Z_]*|SpeechBudget|over_speech_budget|_broken_ceiling"
            r"|speech_budget_for|[A-Z][A-Z_]*_BUDGET"
        ),
        message="no speech ceilings in code — length is prompt style, never a reject",
    ),
    DoctrineRule(
        id=Rule.PROBE,
        pattern=re.compile(
            r"PROCESS_ONLY|ProbePurpose|MOTHER_TONGUE_PRACTICE|SCENE_OPENING"
            r"|plan_next_probe|render_active_probe_contract|is_process_only"
            r"|ACTIVE COMPREHENSION PROBE|BRIDGE MODE"
        ),
        message="no probe/station contracts that forbid the Guide content",
    ),
    DoctrineRule(
        id=Rule.MEMORY_WINDOW,
        pattern=re.compile(r"_RECENT_TURNS|MAX_MESSAGES|messages\[-"),
        message="whole conversation in context — no memory window",
    ),
    DoctrineRule(
        id=Rule.SAY_LESS,
        pattern=re.compile(
            r"say less|saying less|dizendo menos|diga menos|_OVER_BUDGET_NOTE",
            re.IGNORECASE,
        ),
        message="no 'say less' notes — a request to understand is answered fully",
    ),
    DoctrineRule(
        id=Rule.MODEL,
        pattern=re.compile(r"gemini_\w+|ThinkingLevel\.LOW"),
        message="frontier Claude with adaptive thinking on the voice",
    ),
    DoctrineRule(
        id=Rule.MODE,
        pattern=re.compile(r"guided_microchecks|full_retell|bridge_mode"),
        message="no app-owned bridge-language modes",
    ),
]


@dataclass(frozen=True)
class Hit:
    file: str
    line: int
    rule: Rule
    message: str


def _py_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix == ".py" else []
    return sorted(p for p in root.rglob("*.py"))


def scan(roots: tuple[Path, ...] = SCAN_ROOTS, base: Path = REPO_ROOT) -> list[Hit]:
    """Every (file, line, rule) where a forbidden mechanism's Python spelling appears.

    `file` is reported relative to `base`, which is the repo root for a real run and an
    isolated directory for a test that scans a fixture nowhere under the repo.
    """
    hits: list[Hit] = []
    for root in roots:
        for path in _py_files(root):
            rel = path.relative_to(base).as_posix()
            lines = path.read_text().split("\n")
            for rule in RULES:
                for lineno, text in enumerate(lines, start=1):
                    if rule.pattern.search(text):
                        hits.append(Hit(file=rel, line=lineno, rule=rule.id, message=rule.message))
    return hits


def evaluate(
    hits: list[Hit], allowlist: list[AllowlistEntry]
) -> tuple[list[Hit], list[AllowlistEntry]]:
    """Hits the allowlist does not cover, and allowlist entries no hit confirms any more."""
    allowed = {(e.file, e.line, e.rule) for e in allowlist}
    found = {(h.file, h.line, h.rule) for h in hits}

    violations = [h for h in hits if (h.file, h.line, h.rule) not in allowed]
    stale = [e for e in allowlist if (e.file, e.line, e.rule) not in found]
    return violations, stale


def main() -> int:
    violations, stale = evaluate(scan(), ALLOWLIST)

    if not violations and not stale:
        print("doctrine guard passed — every hit is on the allowlist, every entry still matches")
        return 0

    for hit in violations:
        print(f"✗ {hit.file}:{hit.line}  [{hit.rule}] {hit.message}")
    for entry in stale:
        print(
            f"✗ {entry.file}:{entry.line}  [{entry.rule}] allowlist entry no longer matches "
            "any hit — remove it or the mechanism it named moved without the list updating"
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
