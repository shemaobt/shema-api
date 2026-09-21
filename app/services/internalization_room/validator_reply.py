from __future__ import annotations

import json
import re
from typing import Any

_FENCED = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def _parse_verdict(raw: str) -> tuple[dict[str, Any], str | None]:
    """The Validator's reply as a verdict, and the condition that refused it when one did.

    The object is looked for three ways — the whole reply, a fenced block, the outermost
    braces — before the reply is given up on. A refused reply is handed back as whatever
    was read of it, never as a verdict of its own: the second element names *why* it could
    not be trusted, so the caller can leave the trace `_refused` exists for, and what the
    caller does about it is the caller's to decide.
    """
    text = raw.strip()
    verdict = _object_in(text)
    if verdict is None:
        return {}, "not a JSON object"
    if "verdict" not in verdict:
        return verdict, "verdict reply has no 'verdict' key"
    if verdict["verdict"] == "correct" and not str(verdict.get("corrected_response") or "").strip():
        return verdict, "correct verdict has an empty corrected_response"
    return verdict, None


def _object_in(text: str) -> dict[str, Any] | None:
    candidates = [text]
    fenced = _FENCED.search(text)
    if fenced:
        candidates.append(fenced.group(1).strip())
    opened, closed = text.find("{"), text.rfind("}")
    if opened != -1 and closed > opened:
        candidates.append(text[opened : closed + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _issues_as_dicts(raw: Any) -> list[dict[str, Any]]:
    """The Validator's ``issues`` in the shape every reader of them assumes.

    The field comes straight from a model, so its rows are whatever the model wrote and a
    list of strings is as likely as a list of objects. Every reader asks each row for
    ``problem``, and a bare string there raises in the middle of the generative path, where
    the cost is the whole turn instead of one rejected draft.
    """
    if not isinstance(raw, list):
        return []
    return [row if isinstance(row, dict) else {"problem": str(row)} for row in raw]
