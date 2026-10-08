"""What a golden run has spent, read the one way both runners read it.

The price of a call is the room's own, written on the `[llm-usage]` line it reports; this
module only adds those figures up, so there is no second price table to drift from the
first. A call the table never priced carries no figure: the README's total leaves it out and
says so, and the budget counts it at the dearest price the table holds for each kind of token,
because a run that gates a model change is the run most likely to meet a rung the table has
not seen, and a ceiling blind to it would never fire.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Iterable
from typing import NamedTuple

from app.services.internalization_room.usage import LIST_PRICES

OVER_BUDGET = 3
BUDGET_ENV = "GOLDEN_BUDGET_USD"
DEFAULT_BUDGET_USD = 20.0


def budget_of(args: argparse.Namespace) -> float:
    if args.budget_usd is not None:
        return float(args.budget_usd)
    return float(os.environ.get(BUDGET_ENV, DEFAULT_BUDGET_USD))


class Call(NamedTuple):
    role: str
    rung: str
    cost_usd: float | None
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int


def priced(calls: Iterable[Call]) -> tuple[dict[str, float], list[str]]:
    by_role: dict[str, float] = {}
    unpriced: list[str] = []
    for call in calls:
        if call.cost_usd is None:
            unpriced.append(call.rung)
        else:
            by_role[call.role] = by_role.get(call.role, 0.0) + call.cost_usd
    return by_role, unpriced


def budgeted(calls: list[Call]) -> float:
    by_role, _ = priced(calls)
    prices = LIST_PRICES.values()
    dearest = (
        max(price.input for price in prices),
        max(price.output for price in prices),
        max(price.cache_read for price in prices),
        max(price.cache_write_1h for price in prices),
    )
    guessed = sum(
        (
            call.input_tokens * dearest[0]
            + call.output_tokens * dearest[1]
            + call.cache_read_tokens * dearest[2]
            + call.cache_write_tokens * dearest[3]
        )
        / 1_000_000
        for call in calls
        if call.cost_usd is None
    )
    return sum(by_role.values()) + guessed


def split(by_role: dict[str, float]) -> str:
    return " · ".join(f"{role} US$ {cost:.2f}" for role, cost in sorted(by_role.items()))


def uncounted(unpriced: list[str]) -> str:
    if not unpriced:
        return ""
    many = len(unpriced) > 1
    return (
        f"; {len(unpriced)} call{'s' if many else ''} had no table price; "
        f"the budget counted {'them' if many else 'it'} at the highest table price"
    )


def stopped(
    prefix: str, *, budget: float, spent: float, not_started: list[str], unpriced: list[str]
) -> str:
    return (
        f"{prefix}: budget US$ {budget:.2f} reached at US$ {spent:.2f}; "
        f"not started: {', '.join(not_started)}{uncounted(unpriced)}"
    )
