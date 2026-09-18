import pytest

from app.core.exceptions import AuthorizationError, ConflictError
from app.services.book_context.approve_bcd import approve_bcd
from app.services.book_context.request_revision import request_revision
from tests.baker import make_bcd, make_bible_book, make_user


async def test_admin_approval_auto_approves(db_session):
    user = await make_user(db_session, email="admin1@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id, status="draft")

    result = await approve_bcd(db_session, bcd.id, user.id, ["admin"])
    assert result.status.value == "approved"


async def test_single_specialist_sets_review(db_session):
    user = await make_user(db_session, email="spec1@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id, status="draft")

    result = await approve_bcd(db_session, bcd.id, user.id, ["exegete"])
    assert result.status.value == "review"


async def test_facilitator_cannot_approve(db_session):
    user = await make_user(db_session, email="fac_no@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id, status="draft")

    with pytest.raises(AuthorizationError, match="admin or specialist role to approve"):
        await approve_bcd(db_session, bcd.id, user.id, ["facilitator"])


async def test_two_specialists_same_role_stay_review(db_session):
    spec1 = await make_user(db_session, email="spec2a@test.com")
    spec2 = await make_user(db_session, email="spec2b@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, spec1.id, status="draft")

    await approve_bcd(db_session, bcd.id, spec1.id, ["exegete"])
    result = await approve_bcd(db_session, bcd.id, spec2.id, ["exegete"])
    assert result.status.value == "review"


async def test_duplicate_approval_rejected(db_session):
    user = await make_user(db_session, email="dup1@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id, status="draft")

    await approve_bcd(db_session, bcd.id, user.id, ["exegete"])
    with pytest.raises(ConflictError, match="already approved"):
        await approve_bcd(db_session, bcd.id, user.id, ["exegete"])


async def test_approval_rejects_unauthorized_role(db_session):
    user = await make_user(db_session, email="analyst1@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id, status="draft")

    with pytest.raises(AuthorizationError, match="admin or specialist role to approve"):
        await approve_bcd(db_session, bcd.id, user.id, ["analyst"])


async def test_approval_rejects_already_approved(db_session):
    user = await make_user(db_session, email="appr1@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id, status="approved")

    with pytest.raises(ConflictError, match="already approved"):
        await approve_bcd(db_session, bcd.id, user.id, ["admin"])


async def test_approval_rejects_generating(db_session):
    user = await make_user(db_session, email="gen1@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id, status="generating")

    with pytest.raises(ConflictError, match="Only draft or in-review"):
        await approve_bcd(db_session, bcd.id, user.id, ["admin"])


async def test_request_revision_resets_to_draft(db_session):
    user = await make_user(db_session, email="rev1@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id, status="review")

    result = await request_revision(db_session, bcd.id, user.id, "admin")
    assert result.status.value == "draft"


async def test_request_revision_rejects_generating(db_session):
    user = await make_user(db_session, email="rev2@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id, status="generating")

    with pytest.raises(ConflictError, match="being generated"):
        await request_revision(db_session, bcd.id, user.id, "admin")


async def test_request_revision_rejects_unauthorized_role(db_session):
    user = await make_user(db_session, email="rev3@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id, status="draft")

    with pytest.raises(AuthorizationError, match="Only admins can request revisions"):
        await request_revision(db_session, bcd.id, user.id, "viewer")


async def test_request_revision_rejects_facilitator(db_session):
    user = await make_user(db_session, email="rev_fac@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id, status="review")

    with pytest.raises(AuthorizationError, match="Only admins can request revisions"):
        await request_revision(db_session, bcd.id, user.id, "facilitator")
