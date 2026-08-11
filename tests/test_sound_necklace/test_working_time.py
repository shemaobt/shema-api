"""Net working time: heartbeats in, one accumulated total out.

The number the SPA has kept in ``localStorage`` since the pilot, moved to the server so
it survives a cleared profile, a second machine or a second seat. The definition is the
SPA's and is not up for redesign here: time with the session open and the tab visible,
with any gap longer than five minutes thrown away as idle.

What these tests deliberately do NOT pin is anything about *what* the facilitator did.
There is one event type — "still here" — and the only thing it carries besides the
session is an idempotency key. That is the boundary §14 draws: session metadata is
allowed, listener behaviour is not, and a suite that asserted on richer ticks would be
the first step across it.

Time passes by rewinding what is already recorded rather than by sleeping, and by
rewinding it with the database's own clock rather than Python's. Both endpoints of every
stretch then come from one clock at one resolution, so the second counts here are exact
rather than off by however long the test took to reach its request. Crucially the rewind
moves the tick rows and the cursor together: a helper that moved only the cursor would
leave a tick log that no longer described the timeline it is supposed to be the record
of, and ``test_the_tick_log_reproduces_the_stored_total`` would be checking a fiction.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select, text

from app.db.models.sound_necklace import SnSession, SnSessionTick
from app.services.sound_necklace import working_time
from tests.baker import make_user
from tests.test_sound_necklace.conftest import (
    SN,
    auth_header,
    grant_role,
    hand_lease_to,
    new_session,
)

# The route takes a UUID and nothing else, so the beats need real ones. Fixed rather than
# random: a test that fails should fail the same way twice.
BEATS = [f"00000000-0000-4000-8000-{n:012d}" for n in range(12)]

# SQLite's own now(), at the resolution the service reads it with, shifted by an offset.
# Rewinding against Python's clock instead would leave every stretch short by the
# milliseconds between the two reads, and the exact-second assertions below would be off
# by one at random.
_SHIFTED = "STRFTIME('%Y-%m-%d %H:%M:%f000', {column}, :offset)"
_NOW_SHIFTED = _SHIFTED.format(column="'now'")

IDLE_SECONDS = int(working_time.IDLE_GAP.total_seconds())


async def post_tick(client, headers, session_id: str, tick_id: str):
    return await client.post(
        f"{SN}/sessions/{session_id}/working-time/ticks",
        headers=headers,
        json={"client_tick_id": tick_id},
    )


async def read_total(client, headers, session_id: str) -> int:
    res = await client.get(f"{SN}/sessions/{session_id}/working-time", headers=headers)
    assert res.status_code == 200, res.text
    return int(res.json()["net_working_seconds"])


async def read_cursor(db_session, session_id: str):
    """Typed rather than raw text(), so SQLAlchemy hands back an instant, not a string."""
    return (
        await db_session.execute(
            select(SnSession.last_working_tick_at).where(SnSession.id == session_id)
        )
    ).scalar_one()


async def tick_times(db_session, session_id: str) -> list:
    rows = await db_session.execute(
        select(SnSessionTick.occurred_at)
        .where(SnSessionTick.session_id == session_id)
        .order_by(SnSessionTick.occurred_at)
    )
    return list(rows.scalars())


async def stored_tick_count(db_session, session_id: str) -> int:
    row = await db_session.execute(
        text("SELECT COUNT(*) FROM sn_session_ticks WHERE session_id = :sid"),
        {"sid": session_id},
    )
    return int(row.scalar_one())


async def rewind(db_session, session_id: str, seconds: float) -> None:
    """Make it ``seconds`` later, by moving everything already recorded that far back.

    Behind the ORM's back, like the lease helpers next door and for the same reason: the
    app under test runs on this very session. The cursor and the tick rows shift by the
    same offset, so the recorded timeline stays internally consistent and the log still
    reproduces the total.

    A null cursor stays null — that is a reopened or untouched session, and inventing an
    instant for it would quietly defeat the freeze the null is there to express.
    """
    offset = f"{-seconds:+g} seconds"
    before = await read_cursor(db_session, session_id)
    await db_session.execute(
        text(
            f"UPDATE sn_sessions SET last_working_tick_at ="
            f" {_SHIFTED.format(column='last_working_tick_at')} WHERE id = :sid"
        ),
        {"offset": offset, "sid": session_id},
    )
    await db_session.execute(
        text(
            f"UPDATE sn_session_ticks SET occurred_at ="
            f" {_SHIFTED.format(column='occurred_at')} WHERE session_id = :sid"
        ),
        {"offset": offset, "sid": session_id},
    )
    after = await read_cursor(db_session, session_id)
    # SQLite answers a malformed modifier with NULL rather than an error, and a null
    # cursor charges nothing — so without this a broken helper would make every test here
    # pass while measuring nothing.
    assert (before is None) == (after is None), "the rewind helper lost the cursor"


async def tick_after(client, db_session, headers, session_id: str, seconds: float, tick_id: str):
    """A heartbeat arriving ``seconds`` after the one before it."""
    await rewind(db_session, session_id, seconds)
    return await post_tick(client, headers, session_id, tick_id)


async def _never_recorded(db, session_id: str, client_tick_id: str) -> bool:
    """The fast-path duplicate read, as it answers for a beat nobody has seen yet."""
    return False


def recomputed_total(occurred: list) -> int:
    """The documented rule, applied to a tick log from the outside.

    Sum the stretches between consecutive beats, discard any longer than the threshold,
    charge whole seconds and carry the remainder forward. Written out here rather than
    imported so that the log is checked against the rule the docstrings state, not
    against whatever the service happens to do.
    """
    total = 0
    cursor = None
    for beat in occurred:
        if cursor is None:
            cursor = beat
            continue
        gap = (beat - cursor).total_seconds()
        if not 0 <= gap <= IDLE_SECONDS:
            cursor = beat
            continue
        charged = int(gap)
        total += charged
        cursor = cursor + timedelta(seconds=charged)
    return total


@pytest.fixture()
async def session_id(client, alice, project) -> str:
    _user, headers = alice
    return await new_session(client, headers, project.id)


# ── Accumulation ─────────────────────────────────────────────────────────────


async def test_the_first_tick_of_a_session_charges_nothing(client, db_session, alice, session_id):
    _user, headers = alice

    res = await post_tick(client, headers, session_id, BEATS[0])

    assert res.status_code == 200, res.text
    assert res.json()["net_working_seconds"] == 0
    assert await stored_tick_count(db_session, session_id) == 1


async def test_the_first_beat_stamps_the_tick_and_the_cursor_from_one_clock(
    client, db_session, alice, session_id
):
    """The beat's recorded instant and the instant accumulation resumes from are one read.

    A tick stamped from this process's clock instead of the database's would land beside
    the cursor rather than on it, and the tick log would stop being a record of the
    timeline the total was derived from.
    """
    _user, headers = alice

    await post_tick(client, headers, session_id, BEATS[0])

    (stamped,) = await tick_times(db_session, session_id)
    assert stamped == await read_cursor(db_session, session_id)


async def test_ticks_inside_the_threshold_accumulate_the_gaps_between_them(
    client, db_session, alice, session_id
):
    _user, headers = alice
    await post_tick(client, headers, session_id, BEATS[0])

    first = await tick_after(client, db_session, headers, session_id, 30, BEATS[1])
    second = await tick_after(client, db_session, headers, session_id, 20, BEATS[2])

    assert first.json()["net_working_seconds"] == 30
    assert second.json()["net_working_seconds"] == 50


async def test_two_beats_in_the_same_moment_accumulate_without_error(
    client, db_session, alice, session_id
):
    """Back to back, with nothing rewound in between — the ordinary production path.

    A heartbeat arriving on time is worth nothing and must still be recorded, so the row
    count is asserted too: an implementation that answered zero by never writing would
    otherwise look correct here.
    """
    _user, headers = alice
    await post_tick(client, headers, session_id, BEATS[0])

    res = await post_tick(client, headers, session_id, BEATS[1])

    assert res.status_code == 200, res.text
    assert res.json()["net_working_seconds"] == 0
    assert await stored_tick_count(db_session, session_id) == 2


async def test_a_gap_longer_than_five_minutes_is_discarded_as_idle(
    client, db_session, alice, session_id
):
    _user, headers = alice
    await post_tick(client, headers, session_id, BEATS[0])

    idle = await tick_after(client, db_session, headers, session_id, 400, BEATS[1])
    back = await tick_after(client, db_session, headers, session_id, 10, BEATS[2])

    assert idle.json()["net_working_seconds"] == 0
    assert back.json()["net_working_seconds"] == 10


async def test_the_fraction_of_a_second_left_over_is_carried_to_the_next_beat(
    client, db_session, alice, session_id
):
    """Only whole seconds are charged, so the remainder has to survive to the next beat.

    Two stretches of a second and a half are three seconds of work. Advancing the cursor
    to the moment of each beat instead of by what was charged would throw both halves
    away and bill two — a loss on every heartbeat, always downwards, which over a session
    of them is percentage points rather than rounding.
    """
    _user, headers = alice
    await post_tick(client, headers, session_id, BEATS[0])

    first = await tick_after(client, db_session, headers, session_id, 1.5, BEATS[1])
    second = await tick_after(client, db_session, headers, session_id, 1.5, BEATS[2])

    assert first.json()["net_working_seconds"] == 1
    assert second.json()["net_working_seconds"] == 3


async def test_a_clock_that_stepped_backwards_does_not_subtract_from_the_total(
    client, db_session, alice, session_id
):
    """The cursor left in the future, which is what skew between two stampers looks like.

    The database's clock is meant to make this unreachable; the guard stays because a
    counter of somebody's working time must never give back time they spent.
    """
    _user, headers = alice
    await post_tick(client, headers, session_id, BEATS[0])
    await tick_after(client, db_session, headers, session_id, 40, BEATS[1])
    await rewind(db_session, session_id, -120)

    res = await post_tick(client, headers, session_id, BEATS[2])

    assert res.status_code == 200, res.text
    assert res.json()["net_working_seconds"] == 40


async def test_the_tick_log_reproduces_the_stored_total(client, db_session, alice, session_id):
    """The claim the tick table exists to support: the number can be re-derived.

    Without this nothing anywhere recomputes from the log, and a log that never has to
    agree with the total is a log that can drift from it unnoticed.
    """
    _user, headers = alice
    await post_tick(client, headers, session_id, BEATS[0])
    await tick_after(client, db_session, headers, session_id, 30, BEATS[1])
    await tick_after(client, db_session, headers, session_id, 400, BEATS[2])
    await tick_after(client, db_session, headers, session_id, 10, BEATS[3])

    stored = await read_total(client, headers, session_id)

    assert stored == 40
    assert recomputed_total(await tick_times(db_session, session_id)) == stored


# ── Concurrency ──────────────────────────────────────────────────────────────


async def test_a_stretch_is_not_charged_twice_when_two_beats_derive_it_together(
    client, db_session, alice, session_id, monkeypatch
):
    """The bug this design exists to prevent, staged deterministically.

    Two heartbeats whose reads both land before either write measure the same stretch.
    Nothing else can catch it: their tick ids differ, so both inserts are legitimate and
    the unique constraint has no opinion, and the row lock serialises applying a charge
    rather than deriving one. Only tying the derivation to the write does.

    The interleaving is staged by letting the cursor read do what a concurrent beat would
    have done just after it — the same technique as ``hand_lease_to``, which exists
    because a second request cannot express a turnover landing mid-request.
    """
    _user, headers = alice
    await post_tick(client, headers, session_id, BEATS[0])
    await rewind(db_session, session_id, 30)

    real_clock_and_cursor = working_time._clock_and_cursor
    raced = False

    async def _cursor_then_a_concurrent_beat(db, sid):
        nonlocal raced
        now, cursor = await real_clock_and_cursor(db, sid)
        if not raced:
            # Once only: a second beat lands between this read and the write it feeds.
            # Racing every retry as well would model a permanently contended session
            # rather than the collision under test.
            raced = True
            await db.execute(
                text(
                    "UPDATE sn_sessions SET net_working_seconds = net_working_seconds + 30,"
                    f" last_working_tick_at = {_NOW_SHIFTED} WHERE id = :sid"
                ),
                {"offset": "+0 seconds", "sid": sid},
            )
        return now, cursor

    monkeypatch.setattr(working_time, "_clock_and_cursor", _cursor_then_a_concurrent_beat)

    res = await post_tick(client, headers, session_id, BEATS[1])

    assert res.status_code == 200, res.text
    assert res.json()["net_working_seconds"] == 30
    assert await read_total(client, headers, session_id) == 30


async def test_a_beat_that_loses_the_race_still_charges_what_the_winner_left(
    client, db_session, alice, session_id, monkeypatch
):
    """Losing the compare-and-swap must not mean losing the work.

    The winner here only takes part of the stretch — it moves the cursor to twenty
    seconds ago, not to now — so a real remainder is left behind. Giving up on refusal
    would silently drop it and undercount the session; re-deriving against where the
    cursor actually landed, and against a clock that moved with it, charges it once.
    """
    _user, headers = alice
    await post_tick(client, headers, session_id, BEATS[0])
    await rewind(db_session, session_id, 60)

    real_clock_and_cursor = working_time._clock_and_cursor
    raced = False

    async def _cursor_then_a_partial_winner(db, sid):
        nonlocal raced
        now, cursor = await real_clock_and_cursor(db, sid)
        if not raced:
            raced = True
            await db.execute(
                text(
                    "UPDATE sn_sessions SET net_working_seconds = net_working_seconds + 40,"
                    f" last_working_tick_at = {_NOW_SHIFTED} WHERE id = :sid"
                ),
                {"offset": "-20 seconds", "sid": sid},
            )
        return now, cursor

    monkeypatch.setattr(working_time, "_clock_and_cursor", _cursor_then_a_partial_winner)

    res = await post_tick(client, headers, session_id, BEATS[1])

    assert res.status_code == 200, res.text
    assert res.json()["net_working_seconds"] == 60
    assert await read_total(client, headers, session_id) == 60


async def test_a_beat_that_never_wins_the_race_answers_with_the_stored_total(
    client, db_session, alice, session_id, monkeypatch
):
    """Every attempt refused: a permanently contended session, or a refusal that is not
    contention at all.

    The answer has to be the number as it stands — not zero, and not an error. A
    heartbeat the facilitator never sees is not worth a 500, and a total of zero handed
    to a client that is about to display it would be a visible lie.
    """
    _user, headers = alice
    await post_tick(client, headers, session_id, BEATS[0])
    await tick_after(client, db_session, headers, session_id, 30, BEATS[1])
    await rewind(db_session, session_id, 20)

    real_clock_and_cursor = working_time._clock_and_cursor

    async def _cursor_that_is_always_stale(db, sid):
        now, cursor = await real_clock_and_cursor(db, sid)
        await db.execute(
            text(f"UPDATE sn_sessions SET last_working_tick_at = {_NOW_SHIFTED} WHERE id = :sid"),
            {"offset": "+0 seconds", "sid": sid},
        )
        return now, cursor

    monkeypatch.setattr(working_time, "_clock_and_cursor", _cursor_that_is_always_stale)

    res = await post_tick(client, headers, session_id, BEATS[2])

    assert res.status_code == 200, res.text
    assert res.json()["net_working_seconds"] == 30
    assert await stored_tick_count(db_session, session_id) == 2


# ── Idempotency ──────────────────────────────────────────────────────────────


async def test_replaying_a_tick_id_moves_nothing_and_writes_no_second_row(
    client, db_session, alice, session_id
):
    _user, headers = alice
    await post_tick(client, headers, session_id, BEATS[0])
    await tick_after(client, db_session, headers, session_id, 30, BEATS[1])

    replay = await post_tick(client, headers, session_id, BEATS[1])

    assert replay.status_code == 200, replay.text
    assert replay.json()["net_working_seconds"] == 30
    assert await stored_tick_count(db_session, session_id) == 2


async def test_a_duplicate_that_gets_past_the_fast_path_is_still_charged_only_once(
    client, db_session, alice, session_id, monkeypatch
):
    """The same answer as the replay above, by the other route into it.

    Two deliveries of one beat can straddle the fast-path read, and then only the unique
    constraint is left to stop them. A single-process test cannot stage that interleaving,
    so it neutralises the read instead and lets the collision reach the database — the
    rollback, the constraint and the stored total are all real.

    Thirty seconds are rewound first so the charge would be visible if it survived: this
    has to prove the stretch was rolled back with the rejected row, not merely that it
    was zero.
    """
    _user, headers = alice
    await post_tick(client, headers, session_id, BEATS[0])
    await tick_after(client, db_session, headers, session_id, 30, BEATS[1])
    monkeypatch.setattr(working_time, "_already_recorded", _never_recorded)

    replay = await tick_after(client, db_session, headers, session_id, 30, BEATS[1])

    assert replay.status_code == 200, replay.text
    assert replay.json()["net_working_seconds"] == 30
    assert await stored_tick_count(db_session, session_id) == 2


async def test_two_sessions_may_reuse_the_same_tick_ids_without_shadowing_each_other(
    client, db_session, alice, project
):
    """A client mints these per session and has no idea what other sessions exist.

    Interleaved on purpose: if either the duplicate check or the accumulation ignored the
    session, the second session's beats would read as replays of the first's and its
    total would stop moving.
    """
    _user, headers = alice
    first = await new_session(client, headers, project.id)
    second = await new_session(client, headers, project.id)

    await post_tick(client, headers, first, BEATS[0])
    await post_tick(client, headers, second, BEATS[0])
    await tick_after(client, db_session, headers, first, 30, BEATS[1])
    await tick_after(client, db_session, headers, second, 45, BEATS[1])

    assert await read_total(client, headers, first) == 30
    assert await read_total(client, headers, second) == 45
    assert await stored_tick_count(db_session, first) == 2
    assert await stored_tick_count(db_session, second) == 2


async def test_a_tick_id_that_is_not_a_uuid_is_refused(client, alice, session_id):
    """The idempotency key is not a place to smuggle what the facilitator was doing."""
    _user, headers = alice

    res = await post_tick(client, headers, session_id, "cut;played=3;bead=17")

    assert res.status_code == 422, res.text


# ── Reading it back ──────────────────────────────────────────────────────────


async def test_the_total_is_readable_back_after_the_ticks(client, db_session, alice, session_id):
    _user, headers = alice
    await post_tick(client, headers, session_id, BEATS[0])
    await tick_after(client, db_session, headers, session_id, 25, BEATS[1])

    assert await read_total(client, headers, session_id) == 25


async def test_a_session_that_was_never_ticked_reads_back_as_zero(client, alice, session_id):
    _user, headers = alice

    assert await read_total(client, headers, session_id) == 0


# ── Freeze and resume ────────────────────────────────────────────────────────


async def test_ticks_after_completion_do_not_move_the_frozen_total(
    client, db_session, alice, session_id
):
    _user, headers = alice
    await post_tick(client, headers, session_id, BEATS[0])
    await tick_after(client, db_session, headers, session_id, 30, BEATS[1])
    complete = await client.post(f"{SN}/sessions/{session_id}/complete", headers=headers)
    assert complete.status_code == 200, complete.text

    late = await tick_after(client, db_session, headers, session_id, 30, BEATS[2])

    assert late.json()["net_working_seconds"] == 30
    assert await read_total(client, headers, session_id) == 30


async def test_a_completed_session_reports_its_total_even_while_someone_else_holds_it(
    client, db_session, alice, bob, session_id
):
    """A settled number is not a conflict. Answering 409 would invite a retry that can
    never succeed, since no amount of waiting will make a finished session accumulate."""
    _alice, alice_headers = alice
    bob_user, _bob_headers = bob
    await post_tick(client, alice_headers, session_id, BEATS[0])
    await tick_after(client, db_session, alice_headers, session_id, 30, BEATS[1])
    await client.post(f"{SN}/sessions/{session_id}/complete", headers=alice_headers)
    await hand_lease_to(db_session, session_id, bob_user.id)

    res = await post_tick(client, alice_headers, session_id, BEATS[2])

    assert res.status_code == 200, res.text
    assert res.json()["net_working_seconds"] == 30


async def test_a_session_completed_mid_request_does_not_take_the_charge(
    client, db_session, alice, session_id, monkeypatch
):
    """Completion landing after the beat read the session and before it wrote.

    The guard for this is the status predicate inside the UPDATE, and only that: a check
    made before the statement is a check the completion can slip behind. Staged the way
    ``hand_lease_to`` stages a lease turnover, because a second request cannot express a
    change landing mid-request.
    """
    _user, headers = alice
    await post_tick(client, headers, session_id, BEATS[0])
    await rewind(db_session, session_id, 30)

    real_clock_and_cursor = working_time._clock_and_cursor

    async def _cursor_then_a_completion(db, sid):
        now, cursor = await real_clock_and_cursor(db, sid)
        await db.execute(
            text("UPDATE sn_sessions SET status = 'completed' WHERE id = :sid"), {"sid": sid}
        )
        return now, cursor

    monkeypatch.setattr(working_time, "_clock_and_cursor", _cursor_then_a_completion)

    res = await post_tick(client, headers, session_id, BEATS[1])

    assert res.status_code == 200, res.text
    assert res.json()["net_working_seconds"] == 0
    assert await stored_tick_count(db_session, session_id) == 1


async def test_a_beat_in_flight_across_a_reopen_does_not_resurrect_the_old_cursor(
    client, db_session, alice, session_id, monkeypatch
):
    """A completion AND a reopen land between this beat's read and its write.

    The status predicate only closes the window while the session is completed; by the
    time this beat retries, the session is in progress again and the swap is allowed. If
    the retry reused the instant it read before the completion, it would plant a cursor
    predating the closed stretch and the next beat would charge straight across it. The
    retry therefore has to re-read the clock, not just the cursor.
    """
    _user, headers = alice
    await post_tick(client, headers, session_id, BEATS[0])
    await rewind(db_session, session_id, 30)

    real_clock_and_cursor = working_time._clock_and_cursor
    interrupted = False
    reopened_at = None

    async def _cursor_then_a_completion_and_reopen(db, sid):
        nonlocal interrupted, reopened_at
        now, cursor = await real_clock_and_cursor(db, sid)
        if not interrupted:
            interrupted = True
            await db.execute(
                text(
                    "UPDATE sn_sessions SET status = 'completed', last_working_tick_at = NULL"
                    " WHERE id = :sid"
                ),
                {"sid": sid},
            )
            await db.execute(
                text("UPDATE sn_sessions SET status = 'in_progress' WHERE id = :sid"),
                {"sid": sid},
            )
            reopened_at, _ = await real_clock_and_cursor(db, sid)
        return now, cursor

    monkeypatch.setattr(working_time, "_clock_and_cursor", _cursor_then_a_completion_and_reopen)

    res = await post_tick(client, headers, session_id, BEATS[1])

    assert res.status_code == 200, res.text
    assert res.json()["net_working_seconds"] == 0
    planted = await read_cursor(db_session, session_id)
    assert planted >= reopened_at, f"the cursor {planted} predates the reopen at {reopened_at}"


async def test_reopening_resumes_accumulation_without_charging_the_pause(
    client, db_session, alice, session_id
):
    """A short pause, deliberately: this has to test the freeze, not the idle rule.

    Two minutes is well inside the five-minute threshold, so nothing but the freeze can
    stop it being charged. The cursor is rewound BEFORE completing rather than after,
    which is what makes that discriminating: completing clears it, so the rewound value
    only survives to be charged if the clearing is missing — and then the first beat
    after the reopen bills the whole closed stretch.
    """
    _user, headers = alice
    await post_tick(client, headers, session_id, BEATS[0])
    await tick_after(client, db_session, headers, session_id, 30, BEATS[1])
    await rewind(db_session, session_id, 120)
    await client.post(f"{SN}/sessions/{session_id}/complete", headers=headers)
    reopen = await client.post(f"{SN}/sessions/{session_id}/reopen", headers=headers)
    assert reopen.status_code == 200, reopen.text

    resumed = await post_tick(client, headers, session_id, BEATS[2])
    working = await tick_after(client, db_session, headers, session_id, 45, BEATS[3])

    assert resumed.json()["net_working_seconds"] == 30
    assert working.json()["net_working_seconds"] == 75


# ── The guards ───────────────────────────────────────────────────────────────


async def test_a_tick_from_someone_who_is_not_the_holder_is_refused(
    client, db_session, alice, bob, session_id
):
    _alice, alice_headers = alice
    bob_user, _bob_headers = bob
    await post_tick(client, alice_headers, session_id, BEATS[0])
    await hand_lease_to(db_session, session_id, bob_user.id)

    res = await tick_after(client, db_session, alice_headers, session_id, 30, BEATS[1])

    assert res.status_code == 409, res.text
    assert res.json()["code"] == "SESSION_LOCKED"
    assert res.json()["holder_name"] == "Bob"


async def test_a_refused_tick_leaves_no_row_and_no_charge_behind(
    client, db_session, alice, bob, session_id
):
    _alice, alice_headers = alice
    bob_user, bob_headers = bob
    await post_tick(client, alice_headers, session_id, BEATS[0])
    await hand_lease_to(db_session, session_id, bob_user.id)

    await tick_after(client, db_session, alice_headers, session_id, 30, BEATS[1])

    assert await stored_tick_count(db_session, session_id) == 1
    assert await read_total(client, bob_headers, session_id) == 0


async def test_a_beat_lands_once_the_other_holders_lease_has_lapsed(
    client, db_session, alice, bob, session_id
):
    """The handover the two clocks used to swallow.

    A lapsed lease must let the next facilitator's beats through immediately. Judging the
    expiry against a different clock than the one that stamped it made the write refuse
    while the diagnosis found nobody to blame, and the beat vanished with a 200.
    """
    _alice, alice_headers = alice
    bob_user, bob_headers = bob
    await post_tick(client, bob_headers, session_id, BEATS[0])
    await hand_lease_to(db_session, session_id, bob_user.id)
    await db_session.execute(
        text("UPDATE sn_sessions SET lock_expires_at = :when WHERE id = :sid"),
        {"when": "2020-01-01 00:00:00.000000", "sid": session_id},
    )

    res = await tick_after(client, db_session, alice_headers, session_id, 30, BEATS[1])

    assert res.status_code == 200, res.text
    assert res.json()["net_working_seconds"] == 30
    assert await stored_tick_count(db_session, session_id) == 2


async def test_ticking_a_session_in_an_unreachable_project_is_denied(
    client, db_session, alice, sound_necklace_app, session_id
):
    outsider = await make_user(db_session, email="outsider@example.com")
    await grant_role(db_session, sound_necklace_app.id, outsider.id, "facilitator")
    outsider_headers = await auth_header(db_session, outsider)

    res = await post_tick(client, outsider_headers, session_id, BEATS[0])

    assert res.status_code == 403, res.text


async def test_reading_the_total_of_an_unreachable_project_is_denied(
    client, db_session, alice, sound_necklace_app, session_id
):
    outsider = await make_user(db_session, email="outsider-reader@example.com")
    await grant_role(db_session, sound_necklace_app.id, outsider.id, "facilitator")
    outsider_headers = await auth_header(db_session, outsider)

    res = await client.get(f"{SN}/sessions/{session_id}/working-time", headers=outsider_headers)

    assert res.status_code == 403, res.text
