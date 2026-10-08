"""What a golden run has spent, read the one way both runners read it.

The price of a call is the room's own, written on the `[llm-usage]` line it reports; this
module only adds those figures up, so there is no second price table to drift from the
first. A call the table never priced carries no figure and is counted out loud and left out
of the sum, in the README's total and in the budget alike.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Iterable

OVER_BUDGET = 3
BUDGET_ENV = "GOLDEN_BUDGET_USD"
DEFAULT_BUDGET_USD = 20.0


def budget_of(args: argparse.Namespace) -> float:
    if args.budget_usd is not None:
        return float(args.budget_usd)
    return float(os.environ.get(BUDGET_ENV, DEFAULT_BUDGET_USD))


def priced(calls: Iterable[tuple[str, str, float | None]]) -> tuple[dict[str, float], list[str]]:
    by_role: dict[str, float] = {}
    unpriced: list[str] = []
    for role, rung, cost_usd in calls:
        if cost_usd is None:
            unpriced.append(rung)
        else:
            by_role[role] = by_role.get(role, 0.0) + cost_usd
    return by_role, unpriced


def split(by_role: dict[str, float]) -> str:
    return " · ".join(f"{role} US$ {cost:.2f}" for role, cost in sorted(by_role.items()))


def uncounted(unpriced: list[str]) -> str:
    if not unpriced:
        return ""
    plural = "s" if len(unpriced) > 1 else ""
    return f"; the budget did not count {len(unpriced)} call{plural} with no price"


def stopped(
    prefix: str, *, budget: float, spent: float, not_started: list[str], unpriced: list[str]
) -> str:
    return (
        f"{prefix}: budget US$ {budget:.2f} reached at US$ {spent:.2f}; "
        f"not started: {', '.join(not_started)}{uncounted(unpriced)}"
    )
