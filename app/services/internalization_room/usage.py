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

from collections import OrderedDict
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
    #: How many turns were folded in. A turn's own ledger leaves it at zero: it counts only
    #: where totals are added to totals, which is the session.
    turns: int = 0
    #: The lowest rung anything here answered on, and the reason it was reached — the deepest
    #: of the calls rather than the last, because one call falling through the doctrine's
    #: first rung is the whole finding and the call after it recovering does not undo it.
    rung_number: int = 1
    rung_fell_because: str = ""

    @property
    def cache_missed(self) -> bool:
        """Whether work happened here and none of it was served from cache.

        The one reading a zero among eight numbers does not give anybody. The map is what the
        cache is for, it is pinned in front of every turn of every session, and a prefix that
        silently stops matching costs its full price again on each of them while changing
        nothing else anyone would notice. So the record says it in a word rather than leaving
        it to be inferred from a counter nobody was looking at.
        """
        return self.calls > 0 and self.cache_read_tokens == 0


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
    rung_number: int,
    rung_fell_because: str,
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
    if cost_usd is None:
        spend.unpriced_calls += 1
    spend.input_tokens += input_tokens
    spend.output_tokens += output_tokens
    spend.cache_read_tokens += cache_read_tokens
    spend.cache_write_tokens += cache_write_tokens
    spend.model_ms += latency_ms
    if rung_number > spend.rung_number:
        spend.rung_number = rung_number
        spend.rung_fell_because = rung_fell_because


#: What each session has spent so far, oldest first. A running total and not a closing one:
#: nothing in the backend fires when a session ends — `session_end` derives an end from six
#: hours of silence — so a summary that waited for one would never be written for a session
#: that was simply abandoned, which is most of them. Every turn appends the session's total
#: to date instead, and the last line a session has is its total.
_SESSIONS: OrderedDict[str, Spend] = OrderedDict()

#: How many sessions are remembered at once. A process that has answered turns for months
#: must not be holding a row per session it ever saw, and the oldest row is the one nobody is
#: adding to any more. Losing it costs a session that already has its last line in the log.
_SESSIONS_KEPT = 512


def forget_sessions() -> None:
    """Drop every running total, as a restart would."""
    _SESSIONS.clear()


def session_total(session_id: str, turn: Spend) -> Spend:
    """Fold a finished turn into its session's total, and hand back the total.

    Kept per session and not per process: two teams translate at the same time on the same
    deployment, and a number that mixed them is a number neither of them can be shown.
    """
    total = _SESSIONS.pop(session_id, None) or Spend()
    total.turns += 1
    total.calls += turn.calls
    total.cost_usd = round(total.cost_usd + turn.cost_usd, 6)
    total.unpriced_calls += turn.unpriced_calls
    total.input_tokens += turn.input_tokens
    total.output_tokens += turn.output_tokens
    total.cache_read_tokens += turn.cache_read_tokens
    total.cache_write_tokens += turn.cache_write_tokens
    total.model_ms += turn.model_ms
    if turn.rung_number > total.rung_number:
        total.rung_number = turn.rung_number
        total.rung_fell_because = turn.rung_fell_because
    _SESSIONS[session_id] = total
    while len(_SESSIONS) > _SESSIONS_KEPT:
        _SESSIONS.popitem(last=False)
    return total
