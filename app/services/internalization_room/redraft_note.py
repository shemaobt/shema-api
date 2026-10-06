from __future__ import annotations

from typing import Any

_REDRAFT_NOTE = (
    "(internal redraft note — the previous draft carried something the map does not support: "
    "{issues}. Redraft the same answer, as fully as the team's request deserves, using only "
    "what the map contains.)"
)


def _listed(issue: dict[str, Any]) -> str:
    line: str = issue.get("problem", "problem")
    if issue.get("claim"):
        line += f": {issue['claim']}"
    if issue.get("explanation"):
        line += f" — {issue['explanation']}"
    return line


def _redraft_note(issues: list[dict[str, Any]]) -> str:
    """Her note to a Guide whose draft did not pass, in English whatever the session speaks."""
    described = "; ".join(_listed(issue) for issue in issues) or "ungrounded content"
    return _REDRAFT_NOTE.format(issues=described)
