from __future__ import annotations

import pytest

from app.core.exceptions import AuthorizationError, NotFoundError
from app.db.models.as_language_member import AsLanguageMember
from app.services.annotation_studio import access
from tests.baker import make_language, make_user, make_user_app_role
from tests.test_annotation_studio.conftest import add_tier_a_recording, make_speaker, make_word


async def _add_member(db_session, language_id: str, user_id: str) -> None:
    db_session.add(AsLanguageMember(language_id=language_id, user_id=user_id))
    await db_session.commit()


async def test_member_has_access(db_session, as_app):
    lang = await make_language(db_session, code="aaa")
    user = await make_user(db_session, email="member@example.com")
    await _add_member(db_session, lang.id, user.id)

    # Does not raise.
    await access.assert_language_access(db_session, user, lang.id)


async def test_non_member_denied(db_session, as_app):
    lang = await make_language(db_session, code="bbb")
    user = await make_user(db_session, email="outsider@example.com")

    with pytest.raises(AuthorizationError):
        await access.assert_language_access(db_session, user, lang.id)


async def test_platform_admin_bypasses(db_session, as_app):
    lang = await make_language(db_session, code="ccc")
    admin = await make_user(db_session, email="pa@example.com", is_platform_admin=True)

    await access.assert_language_access(db_session, admin, lang.id)
    assert await access.accessible_language_ids(db_session, admin) is None


async def test_as_admin_role_bypasses(db_session, as_app):
    lang = await make_language(db_session, code="ddd")
    user = await make_user(db_session, email="asadmin@example.com")
    admin_role = next(
        r for r in (await _roles_for_app(db_session, as_app.id)) if r.role_key == "admin"
    )
    await make_user_app_role(db_session, user.id, as_app.id, admin_role.id)

    await access.assert_language_access(db_session, user, lang.id)
    assert await access.accessible_language_ids(db_session, user) is None


async def test_accessible_language_ids_for_facilitator(db_session, as_app):
    lang_a = await make_language(db_session, code="eee")
    lang_b = await make_language(db_session, code="fff")
    user = await make_user(db_session, email="fac@example.com")
    await _add_member(db_session, lang_a.id, user.id)

    allowed = await access.accessible_language_ids(db_session, user)
    assert allowed == {lang_a.id}
    assert lang_b.id not in allowed


async def test_language_id_for_storage_key_resolves(db_session, as_app):
    lang = await make_language(db_session, code="ggg")
    word = await make_word(db_session, lang.id, "w001")
    speaker = await make_speaker(db_session, lang.id, "speaker1")
    await add_tier_a_recording(
        db_session, word.id, speaker.id, 0, stored=True, key="ggg/tier_a/raw/rec1"
    )

    resolved = await access.language_id_for_storage_key(db_session, "ggg/tier_a/raw/rec1")
    assert resolved == lang.id


async def test_language_id_for_storage_key_unknown_raises(db_session, as_app):
    with pytest.raises(NotFoundError):
        await access.language_id_for_storage_key(db_session, "nope/does/not/exist")


# ── helper ────────────────────────────────────────────────────────────────────


async def _roles_for_app(db_session, app_id: str):
    from sqlalchemy import select

    from app.db.models.auth import Role

    rows = await db_session.execute(select(Role).where(Role.app_id == app_id))
    return list(rows.scalars().all())
