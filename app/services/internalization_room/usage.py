"""What a model call costs at list price.

Operator-facing arithmetic and nothing else: the room's own behaviour never reads a number
from here, and no text ever reaches it — a cost is computed from counts, so the team's words
cannot travel this far even by accident.

List price and not the invoice. A negotiated rate, a credit or a discount would make the
number here read high, and that is the right direction to be wrong in: this exists to catch
a session that suddenly costs ten times what it should, and a table that flatters the run
would hide exactly that.
"""

from __future__ import annotations

from dataclasses import dataclass

_A_MILLION = 1_000_000


@dataclass(frozen=True)
class ListPrice:
    """US dollars per million tokens, as published."""

    input: float
    output: float
    cache_write: float
    cache_read: float


#: Every rung of the room's three ladders, at the price published on 2026-06-24. A cache write
#: is the five-minute entry, at 1.25x input; a cache read is 0.1x input on every rung but
#: Claude Fable 5.1, whose read is 0.025x — which is the whole reason a 896-thousand-token map
#: can be pinned in front of every turn of a session at all.
LIST_PRICES: dict[str, ListPrice] = {
    "claude-fable-5-1": ListPrice(input=10.0, output=50.0, cache_write=12.50, cache_read=0.25),
    "claude-opus-5": ListPrice(input=5.0, output=25.0, cache_write=6.25, cache_read=0.50),
    "claude-opus-4-8": ListPrice(input=5.0, output=25.0, cache_write=6.25, cache_read=0.50),
    "claude-sonnet-5": ListPrice(input=2.0, output=10.0, cache_write=2.50, cache_read=0.20),
    "claude-sonnet-4-6": ListPrice(input=3.0, output=15.0, cache_write=3.75, cache_read=0.30),
}


def cost_of(
    model: str,
    *,
    input_tokens: int,
    output_tokens: int,
    cache_write_tokens: int,
    cache_read_tokens: int,
) -> float | None:
    """What one call cost at list price, or nothing for a rung this table has never priced.

    Nothing rather than a guess or an exception: a deployment is free to point a ladder at a
    model released after this table was written, and neither losing the team's turn to a
    `KeyError` nor reporting that turn as free is an answer. An unpriced rung says so, and the
    tokens it burned are still counted.
    """
    price = LIST_PRICES.get(model)
    if price is None:
        return None
    dollars = (
        input_tokens * price.input
        + output_tokens * price.output
        + cache_write_tokens * price.cache_write
        + cache_read_tokens * price.cache_read
    ) / _A_MILLION
    return round(dollars, 6)
