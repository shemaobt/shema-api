"""Net working time: heartbeats in, one accumulated total out.

The SPA has computed this number since the pilot and kept it in ``localStorage``, which
means it dies with the browser profile — a cleared storage, a second machine or a second
seat all lose it. This is the same number, kept where it survives.

The definition is the SPA's and is not restated differently here: time with the session
open and the tab visible, with any gap longer than ``IDLE_GAP`` discarded as idle. What
it deliberately does not measure is keystrokes or clicks. That is not an oversight to be
fixed later — §14 forbids telemetry on listener behaviour, and listening to a stretch
without touching anything is the work, not a pause in it.

The total is derived, not asserted: the client sends "still here", the server decides
what that is worth. A client-supplied duration would be a number this API could neither
check nor reproduce, and one skewed or edited clock would put hours of work nobody did
into a facilitator's record. So the stored seconds on ``sn_sessions`` are only ever a
running sum of stretches this database measured between instants it stamped itself, and
the ticks are kept so the sum can be re-derived rather than merely believed.

When it is shown is not decided here. The SPA reveals it on completion and not before;
this exposes the number and nothing about when to look at it.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import DateTime, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import FunctionElement

from app.core.exceptions import NotFoundError
from app.db.models.sound_necklace import SessionStatus, SnSession, SnSessionTick
from app.services.sound_necklace.lock_fence import raise_if_locked_by_other

# The gap past which a stretch is idle rather than worked. Five minutes is the SPA's
# already-shipped threshold and the industry's default for the same judgement, so
# changing it here would silently disagree with every total the pilot accumulated.
IDLE_GAP = timedelta(minutes=5)

# How many times a heartbeat re-derives its stretch after losing the compare-and-swap.
# Each loss means another beat moved the cursor forward, so the retry reads a later
# cursor AND a later clock and measures only what is left. That convergence depends
# entirely on the clock advancing between attempts, which is why _DatabaseNow must not be
# transaction-scoped — see the note there. Exhausting the attempts returns the stored
# total rather than erroring: a heartbeat is not worth a 500, and the winner has already
# charged all but a sliver of what this beat was measuring.
_MAX_ATTEMPTS = 3


class _DatabaseNow(FunctionElement):
    """The database's clock, read afresh at every statement.

    Production is Cloud Run and multi-instance. Two consecutive beats can be served by
    two containers whose clocks disagree, and a stretch measured across that skew is
    wrong in whichever direction the skew runs — negative, and real work gets discarded;
    positive, and time nobody worked is added. One clock for all instances removes the
    question, and the database is the only clock they share.

    Postgres gets ``clock_timestamp()`` and emphatically NOT ``now()``, which is
    ``transaction_timestamp()`` and returns the same instant for the whole transaction
    however long it runs. Two things break under it. The retry loop stops converging: a
    second attempt re-reads a cursor that has moved forward against a clock that has not,
    so the stretch measures negative, is zeroed, and the compare-and-swap then writes the
    stale instant back — dragging the cursor BACKWARDS and letting the next beat charge
    those seconds again. And every gap silently absorbs the request's own latency, since
    the transaction opens at the authentication lookup rather than here.

    SQLite gets a spelling of its own because the portable ``CURRENT_TIMESTAMP``
    truncates to the whole second there, which would quantise every stretch measured.
    """

    type = DateTime()
    inherit_cache = True


@compiles(_DatabaseNow)
def _database_now(element: _DatabaseNow, compiler: object, **kw: object) -> str:
    return "CURRENT_TIMESTAMP"


@compiles(_DatabaseNow, "postgresql")
def _database_now_postgresql(element: _DatabaseNow, compiler: object, **kw: object) -> str:
    return "CLOCK_TIMESTAMP()"


@compiles(_DatabaseNow, "sqlite")
def _database_now_sqlite(element: _DatabaseNow, compiler: object, **kw: object) -> str:
    # '%f' yields seconds with three decimals; the trailing zeroes pad that to the six
    # digits SQLAlchemy reads back as microseconds, so a fraction of a second does not
    # come back a thousand times too small.
    return "STRFTIME('%Y-%m-%d %H:%M:%f000', 'now')"


async def read_working_time(db: AsyncSession, session_id: str) -> int:
    """The session's accumulated net working seconds.

    Read with a fresh SELECT rather than off a loaded ``SnSession``: every write to this
    column is a Core UPDATE with ``synchronize_session=False``, so an instance the
    identity map is already holding keeps the value it was loaded with. This is also the
    read that restores the SPA after a cleared ``localStorage``, which is the whole
    reason the number moved to the server.
    """
    total = (
        await db.execute(select(SnSession.net_working_seconds).where(SnSession.id == session_id))
    ).scalar_one_or_none()
    if total is None:
        raise NotFoundError("Session not found")
    return total


async def record_working_tick(
    db: AsyncSession, session: SnSession, *, client_tick_id: str, actor_user_id: str
) -> int:
    """Record one heartbeat and return the session's total afterwards.

    Charges the stretch since the previous heartbeat, or nothing if that stretch is idle,
    is the first of a sitting, or runs backwards.

    The charge is derived from ``last_working_tick_at`` and applied in the statement that
    moves it, conditional on it not having moved meanwhile. That condition is the whole
    correctness argument: deriving the stretch from a separate read leaves it computed
    under a snapshot the write does not share, so two heartbeats whose reads both land
    before either write measure the same stretch and both add it. The unique constraint
    cannot help — concurrent beats carry different tick ids and both inserts are
    legitimate — and neither can the row lock, which serialises applying a charge, not
    deriving one. Two tabs of one user are unfenced by design (see ``lock_fence``), and a
    client that times out and retries makes its own requests concurrent, so this is
    reached in ordinary use and its error only ever inflates.

    Completing a session clears the cursor, so the first heartbeat after a reopen has no
    stretch behind it and charges nothing regardless of how long the session was closed.
    The freeze is therefore a property of the cursor rather than of the idle threshold,
    and a session reopened after twenty seconds is treated exactly like one reopened
    after a week.

    Two clocks are in play here on purpose, each comparing like with like. The stretch is
    measured against the database's clock, which also stamps the cursor and the tick. The
    lease is measured against this process's clock, because ``acquire_lock`` stamps
    ``lock_expires_at`` from Python and ``raise_if_locked_by_other`` reads it back the
    same way — judging that column against the database's clock instead would let the
    write refuse a lease that the diagnosis then finds alive, which returns a silent
    no-op where the caller deserves either a charge or a 409.

    The tick row and the charge land in one transaction, which is what makes a duplicate
    impossible to charge twice. The replay a retrying client actually produces is caught
    by the read below and never writes. A genuinely simultaneous duplicate gets past that
    read and is caught by the unique constraint instead, and because the charge is
    uncommitted work in the same transaction it is rolled back with the rejected insert
    rather than left behind as a gap counted twice. Either way the caller gets the same
    answer: the stored total, and no error. A heartbeat is background infrastructure the
    facilitator never sees, so an outcome that varied with timing would leave a client
    believing its beat failed and retrying — a retry storm on the one route whose whole
    job is to say "still here".

    The collision is caught rather than avoided with an upsert because ``ON CONFLICT`` is
    not spelled the same on Postgres and on the SQLite the tests run against; the
    constraint is the guard that actually holds, whatever is layered in front of it.

    ``session`` is read once, for its id, and never touched again. A rollback expires
    every instance in the identity map, so reading an attribute after one would emit a
    lazy reload from plain Python — outside the greenlet the async driver needs, which is
    a MissingGreenlet crash rather than the answer the caller expects.
    """
    session_id = session.id
    if await _already_recorded(db, session_id, client_tick_id):
        return await read_working_time(db, session_id)

    for _attempt in range(_MAX_ATTEMPTS):
        now, cursor = await _clock_and_cursor(db, session_id)
        charged, advanced = _charge_and_cursor(cursor, now)
        lease_now = datetime.now(UTC)

        total = (
            await db.execute(
                update(SnSession)
                .where(
                    SnSession.id == session_id,
                    # Predicates on the target row's own columns rather than the
                    # autosave's NOT EXISTS, for the reason complete_session spells out:
                    # a subquery carries its own uncorrelated scan and would re-run under
                    # this statement's original snapshot, reporting a session free that
                    # has just been taken or in progress that has just been completed.
                    SnSession.status == SessionStatus.IN_PROGRESS,
                    # The compare-and-swap. Null-safe, because an untouched session and a
                    # freshly reopened one both carry a null cursor and both must match.
                    SnSession.last_working_tick_at.is_not_distinct_from(cursor),
                    SnSession.lock_expires_at.is_(None)
                    | (SnSession.lock_expires_at <= lease_now)
                    | (SnSession.locked_by == actor_user_id),
                )
                .values(
                    net_working_seconds=SnSession.net_working_seconds + charged,
                    last_working_tick_at=advanced,
                )
                .returning(SnSession.net_working_seconds)
                # The guard is the database's to decide, and the identity map cannot
                # answer for it. complete_session sets the same option on the same table.
                .execution_options(synchronize_session=False)
            )
        ).scalar_one_or_none()

        if total is not None:
            db.add(
                SnSessionTick(session_id=session_id, client_tick_id=client_tick_id, occurred_at=now)
            )
            try:
                await db.commit()
            except IntegrityError:
                # The same beat, delivered twice and racing itself. The rollback discards
                # the charge along with the rejected row, leaving the winner's alone.
                await db.rollback()
                return await read_working_time(db, session_id)
            return total

        # Nothing matched, so nothing is pending and no tick has been written. Three
        # predicates could have refused it, and they mean different things to the caller.
        # Completion is asked about first: a finished session answers with its frozen
        # total even while somebody else holds the lease, because the number is settled
        # and a 409 would invite a retry that can never succeed.
        if await _is_completed(db, session_id):
            return await read_working_time(db, session_id)
        await raise_if_locked_by_other(db, session_id, actor_user_id)
        # The cursor moved: another beat charged part of this stretch already. Re-derive
        # against where it moved to, and against a clock that has moved with it.

    return await read_working_time(db, session_id)


def _charge_and_cursor(previous: datetime | None, now: datetime) -> tuple[int, datetime]:
    """What the stretch since ``previous`` is worth, and where the cursor lands.

    The two are decided together because the second is what makes the first honest. Only
    whole seconds are charged, and the cursor advances by exactly what was charged rather
    than to ``now`` — so the fraction left over is still in front of the next beat
    instead of being thrown away. Discarding it would lose up to a second on every
    heartbeat, which at a fifteen-second beat is nearly two per cent of a session, all of
    it in the same direction. The carry is self-limiting: the cursor can never lag
    ``now`` by a whole second, or that second would have been charged.

    A null cursor charges nothing and starts the measurement here. That covers the first
    heartbeat of a session, where charging would invent time before the facilitator
    arrived, and the first after a reopen, where it would charge a stretch the session
    spent closed.

    A stretch outside the accepted range is worth zero and restarts the measurement at
    ``now``, since there is nothing to carry. Too long is the idle rule. Negative should
    not happen now that both instants come from the database's own clock, but a counter
    of somebody's working time must never subtract, so the range is stated rather than
    assumed.

    Neither instant is normalised to UTC first, and that is safe for one specific reason:
    both come from the same clock by the same route. ``now`` is read from the database
    and the cursor is derived from that same value, so Postgres yields two aware
    datetimes and SQLite two naive ones, never a mixture. It becomes necessary the moment
    anything else writes this column from a Python clock — which is why nothing does.
    """
    if previous is None:
        return 0, now
    gap = now - previous
    if not timedelta(0) <= gap <= IDLE_GAP:
        return 0, now
    charged = int(gap.total_seconds())
    return charged, previous + timedelta(seconds=charged)


async def _clock_and_cursor(db: AsyncSession, session_id: str) -> tuple[datetime, datetime | None]:
    """The database's clock and the session's cursor, read in one statement.

    Together, so no second boundary can fall between them: two reads would let the clock
    advance past the cursor it is about to be measured against.
    """
    row = (
        await db.execute(
            select(_DatabaseNow(), SnSession.last_working_tick_at).where(SnSession.id == session_id)
        )
    ).first()
    if row is None:
        raise NotFoundError("Session not found")
    now, cursor = row
    return now, cursor


async def _is_completed(db: AsyncSession, session_id: str) -> bool:
    status = (
        await db.execute(select(SnSession.status).where(SnSession.id == session_id))
    ).scalar_one_or_none()
    return status is SessionStatus.COMPLETED


async def _already_recorded(db: AsyncSession, session_id: str, client_tick_id: str) -> bool:
    result = await db.execute(
        select(SnSessionTick.id)
        .where(
            SnSessionTick.session_id == session_id,
            SnSessionTick.client_tick_id == client_tick_id,
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None
