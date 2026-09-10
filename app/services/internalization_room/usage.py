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

import logging
from collections import OrderedDict
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

logger = logging.getLogger(__name__)

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
        """Whether this session has answered more than one turn and read none of the map back.

        The one reading a zero among eight numbers does not give anybody. The map is what the
        cache is for, it is pinned in front of every turn of every session, and a prefix that
        silently stops matching costs its full price again on each of them while changing
        nothing else anyone would notice — so the record says it in a word rather than leaving
        it to be inferred from a counter nobody was looking at.

        More than one turn, because the first one cannot tell. A session's opening turn writes
        the entry the rest of it reads, so a zero there is what a working cache looks like on
        its way up; a real run of the room raised this on the first turn of every session and
        cleared it on the second, which is how an alarm stops being read.
        """
        return self.turns > 1 and self.cache_read_tokens == 0


#: The ledger every call in flight adds itself to, when one is open. A context variable and
#: not an argument threaded through `call_agent`: twenty-seven test fakes stand in for that
#: function across thirteen files, and a parameter they never see is a parameter that records
#: nothing in exactly the runs a regression would show up in. Each request owns its own copy,
#: so two sessions answering at once cannot add to each other's total.
_OPEN: ContextVar[Spend | None] = ContextVar("internalization_room_spend", default=None)


def open_ledger() -> Spend:
    """Start counting, and hand back the ledger the count will be read from.

    Opening replaces whatever was open rather than nesting: a stretch that opens its own book
    is a stretch that owns its own total, and there is no case here of one inside another.
    """
    spend = Spend()
    _OPEN.set(spend)
    return spend


def close_ledger() -> None:
    """Stop counting, so that what happens next is not written into a total already read.

    Closing is what makes the promise in `record` true. Starlette runs a background task
    inside the request's own context rather than a new one, so the bead classifier settling
    behind an answered turn arrives here with that turn's ledger still in scope — and a
    ledger left open takes the call into a number that was written to the log two lines ago.
    """
    _OPEN.set(None)


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

    A call with no ledger open still leaves its own line; it is only the total that has
    nowhere to go.

    An unpriced call adds its tokens and no dollars, and the totals say so in their own line.
    A total quietly short by one frontier call is worse than a total that admits it is short:
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


@contextmanager
def counted_for(session_id: str) -> Iterator[None]:
    """Count what happens in here into a session's running total, and say where it stands.

    For work that happens behind a turn rather than inside one: the beads settle after the
    reply has already shipped, on a cheaper rung and off the voice path, and it is still the
    session's money. Marcia's reading of a pilot names the two apart and adds them — US$ 7.07
    on the frontier for the Guide, the Validator and the judge, US$ 0.90 on the classifier,
    about US$ 8 — and a total that left the second out would not be the number she read.

    It adds no turn: what happened here is not one, and the turn it trails was counted when
    it was answered.
    """
    spend = open_ledger()
    try:
        yield
    finally:
        close_ledger()
        report_session(session_id, spend, a_turn=False)


def report_session(session_id: str, spend: Spend, *, a_turn: bool = True) -> None:
    """Where a session stands after one more stretch of work, so far.

    Written every time rather than once at the end, because there is no end to write at: a
    session is completed or it is abandoned, and the second is derived from six hours of
    silence long after the process that answered it. So the session's total is the last line
    it has, and a session nobody ever came back to still has one.
    """
    total = session_total(session_id, spend, a_turn=a_turn)
    logger.info(
        "[llm-session] session %s after %s turns, %s calls, US$ %s: "
        "in=%s cache_read=%s cache_write=%s out=%s%s%s",
        session_id,
        total.turns,
        total.calls,
        total.cost_usd,
        total.input_tokens,
        total.cache_read_tokens,
        total.cache_write_tokens,
        total.output_tokens,
        " — no turn of this session has read the map from cache" if total.cache_missed else "",
        f" — {total.unpriced_calls} unpriced, so the total is short"
        if total.unpriced_calls
        else "",
        extra={
            "session_id": session_id,
            "session_turns": total.turns,
            "session_calls": total.calls,
            "session_cost_usd": total.cost_usd,
            "session_unpriced_calls": total.unpriced_calls,
            "session_input_tokens": total.input_tokens,
            "session_output_tokens": total.output_tokens,
            "session_cache_read_tokens": total.cache_read_tokens,
            "session_cache_write_tokens": total.cache_write_tokens,
            "session_model_ms": total.model_ms,
            "session_rung_number": total.rung_number,
            "session_rung_fell_because": total.rung_fell_because,
            "cache_missed": total.cache_missed,
        },
    )


def session_total(session_id: str, turn: Spend, *, a_turn: bool = True) -> Spend:
    """Fold a finished stretch into its session's total, and hand back the total.

    Kept per session and not per process: two teams translate at the same time on the same
    deployment, and a number that mixed them is a number neither of them can be shown.

    `a_turn` is false for the work that trails a turn rather than being one. Its money counts;
    its existence must not, or a session's turn count would run ahead of the turns the team
    actually took and the per-turn average would read low. Nor does its rung: the bead
    classifier walks a ladder a tier below the voice's, deliberately, off the voice path — a
    key that lost the top of that one says nothing about the rung the team was answered on,
    and letting the two share a number would report the doctrine's own arrangement as a fall.
    The classifier's own step-down is still in the classifier's own line.
    """
    total = _SESSIONS.pop(session_id, None) or Spend()
    if a_turn:
        total.turns += 1
    total.calls += turn.calls
    total.cost_usd = round(total.cost_usd + turn.cost_usd, 6)
    total.unpriced_calls += turn.unpriced_calls
    total.input_tokens += turn.input_tokens
    total.output_tokens += turn.output_tokens
    total.cache_read_tokens += turn.cache_read_tokens
    total.cache_write_tokens += turn.cache_write_tokens
    total.model_ms += turn.model_ms
    if a_turn and turn.rung_number > total.rung_number:
        total.rung_number = turn.rung_number
        total.rung_fell_because = turn.rung_fell_because
    _SESSIONS[session_id] = total
    while len(_SESSIONS) > _SESSIONS_KEPT:
        _SESSIONS.popitem(last=False)
    return total
