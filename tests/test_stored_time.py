"""ENG-532 — the six places that read a stored timestamp back, pinned before they are moved.

`DateTime(timezone=True)` hands back a **naive** value on SQLite and an **aware** one on
Postgres. Every comparison against `datetime.now(UTC)` has to normalise, and six places wrote
their own. Each is correct today, so this file exists to prove nothing changes: it is written
and passing **before** the refactor and passes unchanged after. A refactor of a conversion
that errs in silence is worth exactly what the proof that it did not is worth.

**Why silence is the whole risk.** Reading a naive value as *local* rather than UTC does not
raise, does not fail a test and does not look broken — it draws a time wrong by the machine's
offset. Measured on the Desk on 2026-08-20: the server answered `20:00:56` with no offset and
the panel drew `05:00 PM` on a UTC-3 machine, where local would have said `08:00 PM`.

**Every case is written on both readings.** The suite runs on SQLite, so it only ever sees the
naive one; production only ever sees the other. A case pinned on one pins the half that is not
deployed, which is the wrong half.

The six divide by shape rather than by product, and the division is the plan of this file:
three name the conversion and can be pinned directly, three inline it and are pinned through
the decision they make with it. The last section is not one of the six — `audit._to_utc`
converts a bound off the **wire** and is a different conversion wearing a similar shape. Its
cases exist so that folding the two together goes red.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, ConflictError
from app.db.models.internalization_room import IRSession
from app.services.book_context.lock_bcd import LOCK_TIMEOUT, lock_bcd
from app.services.device.claim_code import has_expired
from app.services.internalization_room.session_end import SessionState, end_of
from tests.baker import make_bcd, make_bible_book, make_user

#: A moment with no offset attached, which is what SQLite hands back for a `timestamptz`.
NAIVE = datetime(2026, 8, 20, 20, 0, 56)

#: The same instant, as Postgres hands it back.
AWARE = NAIVE.replace(tzinfo=UTC)

#: The offset the servers this runs on actually carry, and the reason the two readings are not
#: interchangeable: three hours is what a wrong answer costs here.
BRASILIA = timezone(timedelta(hours=-3))

_books = iter(range(1, 500))


# ------------------------------------- the three that name it, pinned on the name they use


def test_the_rooms_normaliser_reads_a_naive_value_as_utc() -> None:
    from app.services.internalization_room.session_end import as_utc

    assert as_utc(NAIVE) == AWARE
    assert as_utc(NAIVE).tzinfo is not None


def test_the_rooms_normaliser_leaves_an_aware_value_alone() -> None:
    """Not merely equal — the same instant *and* still the offset it arrived with."""
    from app.services.internalization_room.session_end import as_utc

    assert as_utc(AWARE) == AWARE
    assert as_utc(AWARE).utcoffset() == timedelta(0)


def test_the_necklaces_normaliser_answers_exactly_the_same() -> None:
    """Two copies, one conversion. Asserted against each other rather than against a value.

    This is the case that says the merge is a merge: if the two ever disagreed, uniformising
    them would be changing one of them, which is the thing this slice must not do.
    """
    from app.services.internalization_room.session_end import as_utc as rooms
    from app.services.sound_necklace.get_lock_status import as_utc as necklace

    for reading in (NAIVE, AWARE, datetime(2026, 1, 1, tzinfo=BRASILIA)):
        assert rooms(reading) == necklace(reading)
        assert rooms(reading).utcoffset() == necklace(reading).utcoffset()


def test_a_value_that_already_carries_another_offset_is_not_shifted() -> None:
    """The stored normaliser passes an aware value through **unchanged**, offset and all.

    It is not `astimezone`, and the difference is the whole of finding 1 in the plan: the
    wire normaliser converts, this one does not. Nothing in this schema writes a non-UTC
    offset, so passing through is correct here — and pinning it is what makes the two
    functions impossible to collapse by accident.
    """
    from app.services.internalization_room.session_end import as_utc

    elsewhere = datetime(2026, 8, 20, 17, 0, 56, tzinfo=BRASILIA)

    assert as_utc(elsewhere) is elsewhere


# ------------------------------ the three that inline it, pinned through the decision made


def test_a_naive_expiry_is_read_as_utc_and_not_as_local() -> None:
    """One second before the deadline the code is still alive, on both readings.

    Read as local on a UTC-3 machine the same value is three hours in the past, and the code
    is refused at claim with nothing anywhere going red.
    """
    a_second_early = AWARE - timedelta(seconds=1)

    assert has_expired(NAIVE, at=a_second_early) is False
    assert has_expired(AWARE, at=a_second_early) is False


def test_the_claim_code_expires_at_its_own_moment_on_both_readings() -> None:
    assert has_expired(NAIVE, at=AWARE) is True
    assert has_expired(AWARE, at=AWARE) is True
    assert has_expired(NAIVE, at=AWARE + timedelta(hours=1)) is True


def test_a_session_length_is_the_same_whichever_way_the_database_answers() -> None:
    """The property that matters: two readings, one answer, not two."""
    naive = IRSession(
        id="n", pericope="P01", created_at=NAIVE, ended_at=NAIVE + timedelta(minutes=42)
    )
    aware = IRSession(
        id="a", pericope="P01", created_at=AWARE, ended_at=AWARE + timedelta(minutes=42)
    )

    assert end_of(naive, at=AWARE) == end_of(aware, at=AWARE)
    assert end_of(naive, at=AWARE).duration_minutes == 42
    assert end_of(naive, at=AWARE).state is SessionState.COMPLETE


async def a_document(db: AsyncSession, *, tag: str):
    """A document and two real people, because `locked_by` is a foreign key.

    Named users rather than literal strings: the column references `users.id`, so a readable
    placeholder fails on the constraint and the case reddens for a reason that has nothing to
    do with reading a timestamp.
    """
    holder = await make_user(db, email=f"{tag}-segura@stored-time.test")
    newcomer = await make_user(db, email=f"{tag}-chega@stored-time.test")
    book = await make_bible_book(
        db, name=f"Ruth {tag}", abbreviation=f"R{next(_books)}", order=8, chapter_count=4
    )
    return holder, newcomer, await make_bcd(db, book.id, holder.id)


@pytest.mark.asyncio
async def test_a_lock_older_than_the_timeout_is_taken_over(db_session: AsyncSession) -> None:
    holder, newcomer, bcd = await a_document(db_session, tag="velho")
    bcd.locked_by = holder.id
    bcd.locked_at = datetime.now(UTC) - LOCK_TIMEOUT * 2
    await db_session.commit()

    assert (await lock_bcd(db_session, bcd, newcomer.id)).locked_by == newcomer.id


@pytest.mark.asyncio
async def test_a_lock_inside_the_timeout_is_held(db_session: AsyncSession) -> None:
    """The half a wrong reading breaks silently: three hours of drift frees a live lock."""
    holder, newcomer, bcd = await a_document(db_session, tag="vivo")
    bcd.locked_by = holder.id
    bcd.locked_at = datetime.now(UTC) - timedelta(minutes=5)
    await db_session.commit()

    with pytest.raises(ConflictError):
        await lock_bcd(db_session, bcd, newcomer.id)


@pytest.mark.asyncio
async def test_a_document_nobody_ever_locked_is_lockable(db_session: AsyncSession) -> None:
    """`locked_at` is nullable, and this is the only one of the six whose input can be null.

    The shared normaliser stays non-optional, so the guard has to stay where the nullable
    column is. Without this case the guard can be dropped and nothing goes red until somebody
    opens a document that was never locked.
    """
    _holder, newcomer, bcd = await a_document(db_session, tag="nunca")

    assert bcd.locked_at is None
    assert (await lock_bcd(db_session, bcd, newcomer.id)).locked_by == newcomer.id


@pytest.mark.asyncio
async def test_a_lock_held_with_no_moment_recorded_is_not_broken_into(
    db_session: AsyncSession,
) -> None:
    """The guard the shared normaliser cannot carry, because it is not about time-zones.

    `as_utc` is non-optional, so `lock_bcd` reads `locked_at` only when there is one. No
    service produces a row with a holder and no moment — every writer sets and clears the two
    together, checked across the eight that touch them — so this is a row written *outside*
    the code: a seed, a hand-fixed record, an older schema. What matters is what happens then,
    and today the answer is that the lock **holds**: an unknown age is not an expired one.

    Without this case the guard can be deleted and every test stays green, because none of the
    others reaches the branch — the document nobody locked never gets that far.
    """
    holder, newcomer, bcd = await a_document(db_session, tag="sem-momento")
    bcd.locked_by = holder.id
    bcd.locked_at = None
    await db_session.commit()

    with pytest.raises(ConflictError):
        await lock_bcd(db_session, bcd, newcomer.id)


@pytest.mark.asyncio
async def test_a_refresh_token_with_a_naive_expiry_is_read_as_utc(
    db_session: AsyncSession,
) -> None:
    """Both directions in one case, because it is one branch and both sides of it matter.

    A live token read three hours early signs a person out mid-session; a dead one read three
    hours late keeps a revoked session alive. Neither raises anything.
    """
    from app.db.models.auth import RefreshToken
    from app.services.auth.hash_refresh_token import hash_refresh_token
    from app.services.auth.issue_tokens import issue_tokens
    from app.services.auth.refresh_access_token import refresh_access_token

    user = await make_user(db_session, email="token@stored-time.test")
    _access, refresh = await issue_tokens(db_session, user)
    row = (
        await db_session.execute(
            _select_token(RefreshToken, hash_refresh_token(refresh)),
        )
    ).scalar_one()

    row.expires_at = (datetime.now(UTC) + timedelta(hours=2)).replace(tzinfo=None)
    await db_session.commit()
    assert await refresh_access_token(db_session, refresh) is not None

    row.expires_at = (datetime.now(UTC) - timedelta(hours=2)).replace(tzinfo=None)
    await db_session.commit()
    with pytest.raises(AuthenticationError):
        await refresh_access_token(db_session, refresh)


def _select_token(model, token_hash: str):
    from sqlalchemy import select

    return select(model).where(model.token_hash == token_hash)


# ------------------------------------------ the one that is not a copy, and must stay apart


def test_an_aware_bound_off_the_wire_is_converted_and_not_passed_through() -> None:
    """`audit._to_utc` is not a sixth copy, and this is the case that says so.

    It normalises a bound the **client** sent, which may carry any offset, so an aware value
    is `astimezone`-converted rather than returned unchanged. Folding it into the stored-value
    normaliser would leave a `-03:00` bound filtering as though it were UTC — three hours of
    events on the wrong side of the window, on the screen whose whole job is to be the record.
    """
    from app.api.sound_necklace.audit import _to_utc

    in_brasilia = datetime(2026, 8, 20, 17, 0, 56, tzinfo=BRASILIA)

    converted = _to_utc(in_brasilia)

    assert converted == AWARE
    assert converted.utcoffset() == timedelta(0)
    assert converted.hour == 20, "o limite ciente foi repassado em vez de convertido"


def test_a_naive_bound_off_the_wire_is_assumed_utc() -> None:
    """The half `_to_utc` shares with the stored normaliser, so the difference is exactly one."""
    from app.api.sound_necklace.audit import _to_utc

    assert _to_utc(NAIVE) == AWARE


def test_the_two_conversions_disagree_and_that_is_the_point() -> None:
    """If someone replaces `_to_utc` with the stored normaliser, this is what reddens.

    Both sides are compared **on the same reading**, and that is not a detail. An earlier
    version of this case asserted that an aware result was unequal to a naive one, which
    Python answers `True` for any two values whatsoever — so it stayed green with the two
    conversions collapsed, which is the one thing it existed to catch.
    """
    from app.api.sound_necklace.audit import _to_utc
    from app.services.internalization_room.session_end import as_utc

    elsewhere = datetime(2026, 8, 20, 17, 0, 56, tzinfo=BRASILIA)

    assert _to_utc(elsewhere) == elsewhere.astimezone(UTC)
    assert as_utc(elsewhere) is elsewhere
    assert _to_utc(elsewhere).hour != as_utc(elsewhere).hour
    assert _to_utc(elsewhere).utcoffset() != as_utc(elsewhere).utcoffset()


# ------------------------------------------------------- the criterion, swept over the tree


#: The one module allowed to build an aware datetime out of a naive one without calling the
#: shared normaliser, and the reason is on its own function: it converts a bound off the wire
#: rather than reading back a value this codebase wrote. Named here rather than counted, so
#: that a seventh copy has to argue with this list instead of slipping under a threshold.
ALLOWED_TO_ATTACH_AN_OFFSET = {"api/sound_necklace/audit.py"}


def test_no_module_outside_the_shared_one_attaches_utc_to_a_naive_moment() -> None:
    """The acceptance criterion: no naive-to-UTC normalisation survives outside one place.

    Read with `ast` rather than as text, because the docstrings that explain the conversion —
    including this file's — say `replace(tzinfo=UTC)` in prose, and a text sweep would call
    the explanation the thing it explains.
    """
    import ast
    from pathlib import Path

    app_dir = Path(__file__).resolve().parents[1] / "app"
    shared = "utils/stored_time.py"

    attaching = sorted(
        {
            str(source.relative_to(app_dir))
            for source in app_dir.rglob("*.py")
            if _attaches_an_offset(ast.parse(source.read_text(encoding="utf-8")))
        }
        - ALLOWED_TO_ATTACH_AN_OFFSET
        - {shared}
    )

    assert attaching == [], f"normalização ingênuo→UTC fora do módulo único: {attaching}"


def _attaches_an_offset(tree) -> bool:
    """Whether a module *attaches* an offset — `.replace(tzinfo=<something>)`.

    The value is read and not only the keyword's name. `replace(tzinfo=None)` **strips** an
    offset, which is the opposite operation, and nothing in `app/` does it today — so a sweep
    matching on the name alone stays green and then, on the day somebody strips a tzinfo
    before a write, reports it as "naive-to-UTC normalisation outside the single module".
    A failure message that names the wrong thing is worse than none.
    """
    import ast

    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "replace"
        and any(
            keyword.arg == "tzinfo"
            and not (isinstance(keyword.value, ast.Constant) and keyword.value.value is None)
            for keyword in node.keywords
        )
        for node in ast.walk(tree)
    )


def test_the_shared_module_is_the_one_doing_it() -> None:
    """The sweep above passes just as well if nobody normalises anywhere.

    Written because an absence-assertion is only worth what the presence beside it is worth:
    without this, deleting `as_utc` outright would leave the criterion green.
    """
    import ast
    from pathlib import Path

    shared = Path(__file__).resolve().parents[1] / "app" / "utils" / "stored_time.py"

    assert _attaches_an_offset(ast.parse(shared.read_text(encoding="utf-8")))
