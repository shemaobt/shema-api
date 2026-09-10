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

from contextvars import ContextVar
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


@dataclass
class Spend:
    """Everything a stretch of work asked of the models, added up.

    Kept as counts and dollars, never as text: the same rule that keeps the passage out of a
    usage line keeps it out of the total those lines roll into.
    """

    calls: int = 0
    cost_usd: float = 0.0
    unpriced_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    model_ms: int = 0


#: The ledger every call in flight adds itself to, when one is open. A context variable and
#: not an argument threaded through `call_agent`: twenty-seven test fakes stand in for that
#: function across thirteen files, and a parameter they never see is a parameter that records
#: nothing in exactly the runs a regression would show up in. Each request owns its own copy,
#: so two sessions answering at once cannot add to each other's total.
_OPEN: ContextVar[Spend | None] = ContextVar("internalization_room_spend", default=None)


def open_ledger() -> Spend:
    """Start counting a turn, and hand back the ledger it will be read from.

    Opening replaces whatever was open rather than nesting. There is no closing counterpart
    and no `finally`: a turn has exactly one exit and reads its ledger there, and a turn that
    dies before reaching it leaves a ledger that the next turn's opening throws away — inside
    a context the request owns and abandons with it.
    """
    spend = Spend()
    _OPEN.set(spend)
    return spend


def record(
    *,
    cost_usd: float | None,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cache_write_tokens: int,
    latency_ms: int,
) -> None:
    """Add one answered call to the open ledger, if anything is counting.

    A call with no ledger open — the classifier, running behind the team's turn rather than
    inside it — still leaves its own line; it is only the total that has nowhere to go.

    An unpriced call adds its tokens and no dollars, and says so by the count it raises. A
    total quietly short by one frontier call is worse than a total that admits it is short:
    the number exists to be compared against a bill, and only the second of those can be.
    """
    spend = _OPEN.get()
    if spend is None:
        return
    spend.calls += 1
    spend.cost_usd = round(spend.cost_usd + (cost_usd or 0.0), 6)
    spend.unpriced_calls += cost_usd is None
    spend.input_tokens += input_tokens
    spend.output_tokens += output_tokens
    spend.cache_read_tokens += cache_read_tokens
    spend.cache_write_tokens += cache_write_tokens
    spend.model_ms += latency_ms
