from __future__ import annotations

import pytest

from app.core.exceptions import NotFoundError
from app.services.annotation_studio import member_service
from tests.baker import make_language, make_user


async def test_add_member_by_email_then_list_and_remove(db_session, as_app):
    lang = await make_language(db_session, code="mmm")
    user = await make_user(db_session, email="fac@example.com")
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)

    member, resolved = await member_service.add_member(
        db_session, lang.id, "FAC@example.com", admin.id
    )
    assert resolved.id == user.id
    assert member.user_id == user.id

    rows = await member_service.list_members(db_session, lang.id)
    assert [u.id for _m, u in rows] == [user.id]

    # Idempotent: adding again returns the same membership, no duplicate.
    await member_service.add_member(db_session, lang.id, "fac@example.com", admin.id)
    rows = await member_service.list_members(db_session, lang.id)
    assert len(rows) == 1

    await member_service.remove_member(db_session, lang.id, user.id)
    rows = await member_service.list_members(db_session, lang.id)
    assert rows == []


async def test_add_member_unknown_email_raises(db_session, as_app):
    lang = await make_language(db_session, code="nnn")
    with pytest.raises(NotFoundError):
        await member_service.add_member(db_session, lang.id, "ghost@example.com", None)
