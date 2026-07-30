#!/usr/bin/env python3
"""Quality gate: fail if any non-prompt ``app/**/*.py`` file is too long.

Prompt text lives in dedicated ``*_default_prompts.py`` files (data, not logic)
and is exempt. Embedding large prompts inside service/code files is intentionally
NOT exempt, so the gate nudges prompt text into dedicated files.

Phase 0 limit = current worst non-prompt file. Ratchet documented in
``obt/.claude/quality-gates-plan.md``.
"""

from __future__ import annotations

import sys
from pathlib import Path

LINE_LIMIT = 470  # Phase 0 (current worst: context_sections.py, 464). Ratchet -> 400 -> 300.
EXEMPT_SUFFIX = "_default_prompts.py"  # dedicated prompt-text files


def main() -> int:
    offenders: list[tuple[int, Path]] = []
    for path in sorted(Path("app").rglob("*.py")):
        if path.name.endswith(EXEMPT_SUFFIX):
            continue
        lines = sum(1 for _ in path.open(encoding="utf-8"))
        if lines > LINE_LIMIT:
            offenders.append((lines, path))

    for lines, path in sorted(offenders, reverse=True):
        print(f"{path}: {lines} lines (limit {LINE_LIMIT})")

    if offenders:
        print(f"\n{len(offenders)} file(s) exceed the {LINE_LIMIT}-line limit.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
