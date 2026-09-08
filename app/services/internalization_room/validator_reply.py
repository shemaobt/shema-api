from __future__ import annotations

import json
import re
from typing import Any

_UNPARSEABLE_VERDICT: dict[str, Any] = {
    "verdict": "regenerate",
    "issues": [{"problem": "unparseable_verdict"}],
}


def _parse_verdict(raw: str) -> tuple[dict[str, Any], str | None]:
    """The Validator's reply as a verdict, and the condition that refused it when one did.

    A parse failure still returns a usable ``regenerate`` verdict — the loop above asks for
    another draft either way — but the second element names *why* this reply could not be
    trusted, so the caller can leave the trace `_refused` exists for instead of the silence
    that used to sit here for two of these three exits.
    """
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return _UNPARSEABLE_VERDICT, "not JSON"
    if not isinstance(parsed, dict):
        return _UNPARSEABLE_VERDICT, "verdict reply is not a JSON object"
    if "verdict" not in parsed:
        return _UNPARSEABLE_VERDICT, "verdict reply has no 'verdict' key"
    return parsed, None


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
