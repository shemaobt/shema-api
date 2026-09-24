from __future__ import annotations

import re

_BEGIN = re.compile(r"^`?=== BEGIN SYSTEM PROMPT ===`?\s*$", re.M)
_END = re.compile(r"^`?=== END SYSTEM PROMPT ===`?\s*$", re.M)


def extract_prompt_body(text: str, source: str) -> str:
    begin = _BEGIN.search(text)
    end = _END.search(text)
    if begin is None or end is None or end.start() <= begin.start():
        raise ValueError(f"{source}: missing standalone BEGIN/END SYSTEM PROMPT marker lines")
    body = text[begin.end() : end.start()].strip()
    if not body:
        raise ValueError(f"{source}: empty system prompt body")
    return body
