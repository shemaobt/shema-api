"""Marcia's `mechanicalChecks`, ported whole as a pure function over one played turn.

Read from `src/golden/run.ts` in `shemaobt/Tripod-Internalization` at `533b6e3`, the commit
`docs/doctrine/DOCTRINE_PIN` names. The rules are hers and so are the messages, in her
English, because a report of ours is read beside one of hers and a rule renamed on our side
is a rule the two stacks no longer share. No check is added, none is dropped, none is
loosened. These are "the cheap, unambiguous ones" the runner makes without a judge; the rest
of her `expect` keys — `opens_more`, `names_gap`, `no_spoiler` — are the judge's to score.

Her regexes run without the `u` flag, so her `\\b` is ASCII-only where Python's is
Unicode-aware; `scripts/bt_golden_checks.py` measures the difference. Nothing a Guide turn
says separates the two here: the words on either side of every `\\b` below are unaccented.
"""

from __future__ import annotations

import re
from typing import Any

_REHEARSAL = re.compile(r"\bensai(em|ar|o)\b|rehears", re.IGNORECASE)
_RUTH_AND_MAHLON = re.compile(
    r"(Rute|Ruth)[^.]{0,40}\b(Malom|Mahlon)\b|(Malom|Mahlon)[^.]{0,40}\b(Rute|Ruth)\b",
    re.IGNORECASE,
)
_MARRIED = re.compile(r"casou|esposa|mulher de|married|wife", re.IGNORECASE)
_RECORD = re.compile(r"grav", re.IGNORECASE)
_THE_MAP = re.compile(r"\bo mapa\b|the map\b", re.IGNORECASE)
_FAREWELL = re.compile(r"vão com deus|god bless|amém|amen\b", re.IGNORECASE)


def mechanical_checks(
    *, guide: str, outcome: str, expect: dict[str, Any], previous_guide: str
) -> list[str]:
    """Every fault of one turn the runner can name without a judge, in her words and order.

    A keyed check is applied only where her script carries the key: a rehearsal invited is
    the demo failure on the turn where the team asked to understand first, and the voice's
    own send-off everywhere else. The three unkeyed ones — a verbatim repeat, `o mapa`, a
    blessing — are faults on any turn of any session.
    """
    fails: list[str] = []
    if expect.get("no_fail_safe") and outcome == "fail_safe":
        fails.append("fail_safe voiced in reply to a turn that must be answered")
    if guide.strip() and guide.strip() == previous_guide.strip():
        fails.append("verbatim repeat of the previous guide turn")
    if expect.get("no_rehearsal_invite") and _REHEARSAL.search(guide):
        fails.append("rehearsal invited on a turn where the team asked to understand first")
    if expect.get("no_pairing") and _RUTH_AND_MAHLON.search(guide) and _MARRIED.search(guide):
        fails.append("possible Ruth↔Mahlon pairing voiced (judge must confirm)")
    if expect.get("send_off_record") and not _RECORD.search(guide):
        fails.append("send-off did not tell the team to record (gravem o ensaio)")
    if _THE_MAP.search(guide):
        fails.append("says 'o mapa' / 'the map' to the team")
    if _FAREWELL.search(guide):
        fails.append("religious farewell of its own")
    return fails
