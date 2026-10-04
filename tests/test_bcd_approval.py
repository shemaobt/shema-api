import pytest

from app.core.exceptions import AuthorizationError, ConflictError
from app.services.book_context.approve_bcd import approve_bcd
from app.services.book_context.request_revision import request_revision
from tests.baker import make_bcd, make_bible_book, make_user


async def test_single_admin_approves_immediately(db_session):
    admin = await make_user(db_session, email="admin@test.com")
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


async def test_single_specialist_moves_to_review(db_session):
    user = await make_user(db_session, email="spec1@test.com")
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


async def test_facilitator_cannot_approve(db_session):
    user = await make_user(db_session, email="fac_reject@test.com")
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


async def test_two_specialists_two_roles_stay_review(db_session):
    spec1 = await make_user(db_session, email="spec2a@test.com")
    spec2 = await make_user(db_session, email="spec2b@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, spec1.id)

    await approve_bcd(db_session, bcd.id, spec1.id, ["exegete"])
    result = await approve_bcd(db_session, bcd.id, spec2.id, ["translation_specialist"])

    assert result.status.value == "review"


async def test_three_specialties_covered_by_two_users_approve(db_session):
    spec1 = await make_user(db_session, email="spec3x@test.com")
    spec2 = await make_user(db_session, email="spec3y@test.com")
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


async def test_specialist_then_admin_approves(db_session):
    spec = await make_user(db_session, email="spec3@test.com")
    admin = await make_user(db_session, email="admin3@test.com")
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


async def test_admin_then_specialist_already_approved(db_session):
    admin = await make_user(db_session, email="admin4@test.com")
    spec = await make_user(db_session, email="spec4@test.com")
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

    with pytest.raises(ConflictError, match="already approved"):
        await approve_bcd(db_session, bcd.id, spec.id, ["exegete"])


async def test_rejects_duplicate_approval(db_session):
    spec = await make_user(db_session, email="spec5@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, spec.id)

    await approve_bcd(db_session, bcd.id, spec.id, ["exegete"])

    with pytest.raises(ConflictError, match="already approved this document"):
        await approve_bcd(db_session, bcd.id, spec.id, ["exegete"])


async def test_rejects_non_admin_non_specialist(db_session):
    user = await make_user(db_session, email="annotator@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id)

    with pytest.raises(AuthorizationError, match="admin or specialist role to approve"):
        await approve_bcd(db_session, bcd.id, user.id, ["annotator"])


async def test_rejects_if_generating(db_session):
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


async def test_request_revision_clears_approvals(db_session):
    admin = await make_user(db_session, email="admin7@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, admin.id, status="review")

    result = await request_revision(db_session, bcd.id, admin.id, "admin")

    assert result.status.value == "draft"


async def test_request_revision_from_approved(db_session):
    admin = await make_user(db_session, email="admin8@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, admin.id, status="approved")

    result = await request_revision(db_session, bcd.id, admin.id, "admin")

    assert result.status.value == "draft"


async def test_request_revision_rejects_non_admin(db_session):
    user = await make_user(db_session, email="annotator2@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    bcd = await make_bcd(db_session, book.id, user.id, status="review")

    with pytest.raises(AuthorizationError, match="Only admins can request revisions"):
        await request_revision(db_session, bcd.id, user.id, "annotator")


async def test_request_revision_rejects_facilitator(db_session):
    user = await make_user(db_session, email="fac_rev@test.com")
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
