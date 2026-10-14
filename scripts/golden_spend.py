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
from dataclasses import dataclass
from typing import Any, NamedTuple

from app.services.internalization_room.usage import LIST_PRICES

OVER_BUDGET = 3
BUDGET_ENV = "GOLDEN_BUDGET_USD"
DEFAULT_BUDGET_USD = 20.0


def budget_of(args: argparse.Namespace) -> float:
    if args.budget_usd is not None:
        return float(args.budget_usd)
    return float(os.environ.get(BUDGET_ENV, DEFAULT_BUDGET_USD))


@dataclass
class Usage:
    """One model call as this room's seam reports it; her app reports none."""

    role: str
    rung: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int | None
    cache_write_tokens: int | None
    latency_ms: int | None
    cost_usd: float | None

    @classmethod
    def from_wire(cls, call: dict[str, Any]) -> Usage:
        """The seam's `ModelCall` at this commit, every field; her app sends no `usage` at all.

        Read by key and not by `.get`, so a room that reports usage in another shape — a
        deployment older than the seam's `role` and `cost_usd` — is a `KeyError` on turn 0 and
        not a README that silently prices the run wrong. The runner and the room it tallies
        move together.
        """
        return cls(
            role=call["role"],
            rung=call["rung"],
            input_tokens=call["input_tokens"],
            output_tokens=call["output_tokens"],
            cache_read_tokens=call["cache_read_tokens"],
            cache_write_tokens=call["cache_write_tokens"],
            latency_ms=call["latency_ms"],
            cost_usd=call["cost_usd"],
        )


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


def what_killed(dead: BaseException) -> str:
    named = type(dead).__name__
    return f"{named}: {dead}" if str(dead) else named


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
