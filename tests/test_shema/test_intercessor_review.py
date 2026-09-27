"""The one-year review — a contact nobody has used in a year is flagged, and "Revisado" clears it.

The client's answer of 22/sep (4.3) is *revisar depois de um ano*. What these tests hold is the
server's half of it: the flag is computed here, from the latest of entry, review and send, and
the console only shows it; the stamp is one role's act; and the people no list may show are
counted — a number, never a name — so the review cannot silently miss them.

The clock is moved by writing the stored moments back in time, not by patching ``now``: the
routes read the real clock, and a test that patched it would be testing the patch.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from app.db.models.shema_consent import ShemaIntercessorConsent
from app.db.models.shema_intercessor import ShemaIntercessor
from app.services.shema._directory import REVIEW_AFTER, review_due
from tests.baker import make_user
from tests.test_shema.conftest import PEOPLE, auth_header, make_intercessor, make_scoped_user

NOW = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


async def _circle(db_session, shema_app, *, email: str = "circle@review.test"):
    user = await make_scoped_user(
        db_session, shema_app, email=email, role_key="resourceCircle", regions=[]
    )
    return user, await auth_header(db_session, user)


async def _listed(client, headers, **fields) -> dict:
    """One person with the ``directory`` consent, so the list carries them."""
    person = await make_intercessor(client, headers, **fields)
    res = await client.put(
        f"{PEOPLE}/{person['id']}/consents/directory", headers=headers, json={"basis": "yes"}
    )
    assert res.status_code == 200, res.text
    return person


async def _age(db_session, person_id: str, **moments: datetime) -> None:
    """Write stored moments back in time — the only honest way to let a year pass."""
    await db_session.execute(
        update(ShemaIntercessor).where(ShemaIntercessor.id == person_id).values(**moments)
    )
    await db_session.commit()


def _ago(days: int) -> datetime:
    return datetime.now(UTC) - timedelta(days=days)


# --- the rule -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("added", "reviewed", "sent", "due"),
    [
        pytest.param(NOW - timedelta(days=400), None, None, True, id="untouched-past-a-year"),
        pytest.param(NOW - timedelta(days=30), None, None, False, id="entered-this-year"),
        pytest.param(
            NOW - timedelta(days=800), NOW - timedelta(days=10), None, False, id="reviewed-lately"
        ),
        pytest.param(
            NOW - timedelta(days=800), None, NOW - timedelta(days=10), False, id="sent-lately"
        ),
        pytest.param(
            NOW - timedelta(days=800),
            NOW - timedelta(days=500),
            NOW - timedelta(days=400),
            True,
            id="all-three-past-a-year",
        ),
        pytest.param(NOW - REVIEW_AFTER, None, None, False, id="exactly-a-year-is-not-yet"),
        pytest.param(
            NOW - REVIEW_AFTER - timedelta(seconds=1), None, None, True, id="a-second-past-a-year"
        ),
        pytest.param(
            (NOW - timedelta(days=400)).replace(tzinfo=None),
            None,
            None,
            True,
            id="a-naive-stored-moment-reads-as-utc",
        ),
    ],
)
def test_the_year_counts_from_the_latest_of_entry_review_and_send(
    added: datetime, reviewed: datetime | None, sent: datetime | None, due: bool
) -> None:
    """The one reading of the year. *More than* is strict, and a moment that never happened
    (``None``) is not the latest one — a contact nobody reviewed counts from its entry."""
    assert review_due(added, reviewed, sent, now=NOW) is due


# --- the list flags it ----------------------------------------------------------------------


async def test_a_contact_untouched_for_more_than_a_year_is_due_for_review(
    db_session, client, shema_app
) -> None:
    """**The DoD's first line, over the wire**: the flag arrives computed; nothing in the
    console has to know what a year is."""
    _user, headers = await _circle(db_session, shema_app)
    old = await _listed(client, headers, name="Ana Velha", contact="ana@example.org")
    fresh = await _listed(client, headers, name="Bia Nova", contact="bia@example.org")
    await _age(db_session, old["id"], added_at=_ago(400))

    people = {
        row["name"]: row for row in (await client.get(PEOPLE, headers=headers)).json()["people"]
    }

    assert people["Ana Velha"]["reviewDue"] is True
    assert people["Bia Nova"]["reviewDue"] is False
    assert people["Ana Velha"]["reviewedAt"] is None
    assert people["Ana Velha"]["lastSentAt"] is None
    assert fresh["reviewDue"] is False


async def test_a_send_within_the_year_keeps_an_old_contact_off_the_review(
    db_session, client, shema_app
) -> None:
    """``last_sent_at`` is BE-09's to write; what is proved here is that it is read."""
    _user, headers = await _circle(db_session, shema_app)
    person = await _listed(client, headers)
    await _age(db_session, person["id"], added_at=_ago(700), last_sent_at=_ago(20))

    entry = (await client.get(PEOPLE, headers=headers)).json()["people"][0]

    assert entry["reviewDue"] is False
    assert entry["lastSentAt"] == _ago(20).date().isoformat()


# --- "Revisado" -----------------------------------------------------------------------------


async def test_marking_reviewed_stamps_the_row_and_clears_the_flag(
    db_session, client, shema_app
) -> None:
    """The stamp is read back from the table, not from the response that claims it."""
    _user, headers = await _circle(db_session, shema_app)
    person = await _listed(client, headers)
    await _age(db_session, person["id"], added_at=_ago(400))

    res = await client.post(f"{PEOPLE}/{person['id']}/review", headers=headers)

    assert res.status_code == 200, res.text
    assert res.json()["reviewDue"] is False
    assert res.json()["reviewedAt"] == datetime.now(UTC).date().isoformat()
    stamped = (
        await db_session.execute(
            select(ShemaIntercessor.reviewed_at).where(ShemaIntercessor.id == person["id"])
        )
    ).scalar_one()
    assert stamped is not None
    assert datetime.now(UTC) - stamped < timedelta(minutes=5)
    listed = (await client.get(PEOPLE, headers=headers)).json()["people"][0]
    assert listed["reviewDue"] is False


async def test_the_review_logs_who_kept_the_person_and_not_the_person(
    db_session, client, shema_app, caplog
) -> None:
    """ "Revisado" keeps somebody's data for another year, so it leaves the same trace every
    other write on a person leaves: who did it and which row — never the name or the contact."""
    user, headers = await _circle(db_session, shema_app)
    person = await _listed(client, headers, name="Ana Velha", contact="ana@example.org")
    caplog.set_level(logging.INFO, logger="app.services.shema.review_intercessor")

    assert (
        await client.post(f"{PEOPLE}/{person['id']}/review", headers=headers)
    ).status_code == 200

    lines = [r for r in caplog.records if r.name == "app.services.shema.review_intercessor"]
    assert len(lines) == 1
    assert lines[0].__dict__["shema_user_id"] == user.id
    assert lines[0].__dict__["shema_intercessor_id"] == person["id"]
    written = " ".join(str(value) for value in lines[0].__dict__.values())
    assert "Ana Velha" not in written
    assert "ana@example.org" not in written


async def test_a_review_moves_neither_added_at_nor_a_consent(db_session, client, shema_app) -> None:
    """A review is somebody deciding the person should still be held — not a new entry, and
    not a new answer from the person."""
    _user, headers = await _circle(db_session, shema_app)
    person = await _listed(client, headers)
    long_ago = _ago(400)
    await _age(db_session, person["id"], added_at=long_ago)
    await db_session.execute(
        update(ShemaIntercessorConsent)
        .where(ShemaIntercessorConsent.intercessor_id == person["id"])
        .values(recorded_at=long_ago)
    )
    await db_session.commit()

    res = await client.post(f"{PEOPLE}/{person['id']}/review", headers=headers)

    assert res.json()["addedAt"] == long_ago.date().isoformat()
    assert {row["recordedAt"] for row in res.json()["consents"]} == {long_ago.date().isoformat()}


async def test_reviewing_somebody_who_is_not_there_is_a_404(db_session, client, shema_app) -> None:
    _user, headers = await _circle(db_session, shema_app)

    res = await client.post(f"{PEOPLE}/nobody/review", headers=headers)

    assert res.status_code == 404


async def test_only_the_resource_circle_may_mark_a_review(db_session, client, shema_app) -> None:
    """Every other Shemá role is refused, and so is an account with none. **Never an admin**:
    an admin passes every guard, and this test would pass with the guard deleted."""
    _user, headers = await _circle(db_session, shema_app)
    person = await _listed(client, headers)

    for role in ("coordinator", "obtLab", "globalStrategist"):
        other = await make_scoped_user(
            db_session, shema_app, email=f"{role}@review.test", role_key=role, regions=[]
        )
        res = await client.post(
            f"{PEOPLE}/{person['id']}/review", headers=await auth_header(db_session, other)
        )
        assert res.status_code == 403, role

    outsider = await make_user(db_session, email="outsider@review.test")
    res = await client.post(
        f"{PEOPLE}/{person['id']}/review", headers=await auth_header(db_session, outsider)
    )
    assert res.status_code == 403
    assert (
        await db_session.execute(
            select(ShemaIntercessor.reviewed_at).where(ShemaIntercessor.id == person["id"])
        )
    ).scalar_one() is None


# --- the people no list may show ------------------------------------------------------------


async def test_a_withheld_person_past_a_year_is_counted_and_never_named(
    db_session, client, shema_app
) -> None:
    """Somebody with no ``directory`` consent is on no screen, so nobody can review them there.
    The count is what says they exist — and it is a number: the body carries no name of theirs.
    A listed person past their year is flagged on their entry and is not counted twice."""
    _user, headers = await _circle(db_session, shema_app)
    hidden = await make_intercessor(
        client, headers, name="Carla Oculta", contact="carla@example.org"
    )
    hidden_fresh = await make_intercessor(
        client, headers, name="Dora Oculta", contact="dora@example.org"
    )
    listed = await _listed(client, headers, name="Eva Listada", contact="eva@example.org")
    await _age(db_session, hidden["id"], added_at=_ago(500))
    await _age(db_session, listed["id"], added_at=_ago(500))

    res = await client.get(PEOPLE, headers=headers)

    body = res.json()
    assert body["withheldCount"] == 2
    assert body["withheldReviewDueCount"] == 1
    assert [row["name"] for row in body["people"]] == ["Eva Listada"]
    assert body["people"][0]["reviewDue"] is True
    assert "Carla" not in res.text
    assert hidden_fresh["id"] not in res.text
