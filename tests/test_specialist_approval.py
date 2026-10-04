import pytest

from app.core.exceptions import AuthorizationError
from app.services.book_context.approve_bcd import approve_bcd
from app.services.book_context.get_approval_status import get_approval_status
from tests.baker import make_bcd, make_bible_book, make_user


async def test_exegete_can_approve(db_session):
    user = await make_user(db_session, email="exg1@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id)

    result = await approve_bcd(db_session, bcd.id, user.id, ["exegete"])
    assert result.status.value == "review"


async def test_biblical_language_specialist_can_approve(db_session):
    user = await make_user(db_session, email="bls1@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id)

    result = await approve_bcd(db_session, bcd.id, user.id, ["biblical_language_specialist"])
    assert result.status.value == "review"


async def test_translation_specialist_can_approve(db_session):
    user = await make_user(db_session, email="trs1@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id)

    result = await approve_bcd(db_session, bcd.id, user.id, ["translation_specialist"])
    assert result.status.value == "review"


async def test_two_specialists_covering_two_specialties_stay_review(db_session):
    user1 = await make_user(db_session, email="spec1@test.com")
    user2 = await make_user(db_session, email="spec2@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user1.id)

    await approve_bcd(db_session, bcd.id, user1.id, ["exegete"])
    result = await approve_bcd(db_session, bcd.id, user2.id, ["biblical_language_specialist"])

    assert result.status.value == "review"


async def test_two_specialists_same_specialty_stay_review(db_session):
    user1 = await make_user(db_session, email="dupe_spec1@test.com")
    user2 = await make_user(db_session, email="dupe_spec2@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user1.id)

    await approve_bcd(db_session, bcd.id, user1.id, ["exegete"])
    result = await approve_bcd(db_session, bcd.id, user2.id, ["exegete"])

    assert result.status.value == "review"


async def test_specialist_with_two_roles_plus_another_specialist_approves(db_session):
    spec1 = await make_user(db_session, email="spec1_multi@test.com")
    spec2 = await make_user(db_session, email="spec2_single@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, spec1.id)

    await approve_bcd(db_session, bcd.id, spec1.id, ["exegete", "biblical_language_specialist"])
    result = await approve_bcd(db_session, bcd.id, spec2.id, ["translation_specialist"])

    assert result.status.value == "approved"


async def test_user_with_multiple_specialist_roles(db_session):
    user1 = await make_user(db_session, email="multi1@test.com")
    user2 = await make_user(db_session, email="multi2@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user1.id)

    await approve_bcd(db_session, bcd.id, user1.id, ["exegete", "biblical_language_specialist"])

    result = await approve_bcd(db_session, bcd.id, user2.id, ["translation_specialist"])

    assert result.status.value == "approved"


async def test_facilitator_cannot_approve(db_session):
    user = await make_user(db_session, email="fac_no_approve@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id)

    with pytest.raises(AuthorizationError, match="admin or specialist role to approve"):
        await approve_bcd(db_session, bcd.id, user.id, ["facilitator"])


async def test_single_user_with_two_specialties_stays_review(db_session):
    user = await make_user(db_session, email="solo_spec@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id)

    result = await approve_bcd(
        db_session,
        bcd.id,
        user.id,
        ["exegete", "biblical_language_specialist", "translation_specialist"],
    )

    assert result.status.value == "review"


async def test_admin_still_instant_approves(db_session):
    admin = await make_user(db_session, email="admin_spec@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, admin.id)

    result = await approve_bcd(db_session, bcd.id, admin.id, ["admin"])
    assert result.status.value == "approved"


async def test_specialist_then_admin_approves(db_session):
    spec = await make_user(db_session, email="spec_pre@test.com")
    admin = await make_user(db_session, email="admin_post@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, spec.id)

    await approve_bcd(db_session, bcd.id, spec.id, ["exegete"])
    result = await approve_bcd(db_session, bcd.id, admin.id, ["admin"])

    assert result.status.value == "approved"


async def test_viewer_cannot_approve(db_session):
    user = await make_user(db_session, email="viewer_spec@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id)

    with pytest.raises(AuthorizationError, match="admin or specialist role to approve"):
        await approve_bcd(db_session, bcd.id, user.id, ["viewer"])


async def test_analyst_cannot_approve(db_session):
    user = await make_user(db_session, email="analyst_spec@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id)

    with pytest.raises(AuthorizationError, match="admin or specialist role to approve"):
        await approve_bcd(db_session, bcd.id, user.id, ["analyst"])


async def test_approval_status_empty(db_session):
    user = await make_user(db_session, email="status1@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id)

    status = await get_approval_status(db_session, bcd.id)

    assert status.approvals == []
    assert status.covered_specialties == []
    assert len(status.missing_specialties) == 3
    assert status.distinct_reviewers == 0
    assert status.is_complete is False


async def test_approval_status_partial(db_session):
    user = await make_user(db_session, email="status2@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id)

    await approve_bcd(db_session, bcd.id, user.id, ["exegete"])

    status = await get_approval_status(db_session, bcd.id)

    assert len(status.approvals) == 1
    assert "exegete" in status.covered_specialties
    assert status.distinct_reviewers == 1
    assert status.is_complete is False


async def test_approval_status_partial_two_specialties(db_session):
    user1 = await make_user(db_session, email="status3a@test.com")
    user2 = await make_user(db_session, email="status3b@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user1.id)

    await approve_bcd(db_session, bcd.id, user1.id, ["exegete"])
    await approve_bcd(db_session, bcd.id, user2.id, ["biblical_language_specialist"])

    status = await get_approval_status(db_session, bcd.id)

    assert len(status.approvals) == 2
    assert "exegete" in status.covered_specialties
    assert "biblical_language_specialist" in status.covered_specialties
    assert status.distinct_reviewers == 2
    assert status.is_complete is False


async def test_approval_status_complete_all_three_specialties(db_session):
    user1 = await make_user(db_session, email="status4a@test.com")
    user2 = await make_user(db_session, email="status4b@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user1.id)

    await approve_bcd(db_session, bcd.id, user1.id, ["exegete", "biblical_language_specialist"])
    await approve_bcd(db_session, bcd.id, user2.id, ["translation_specialist"])

    status = await get_approval_status(db_session, bcd.id)

    assert len(status.approvals) == 2
    assert status.distinct_reviewers == 2
    assert status.is_complete is True
