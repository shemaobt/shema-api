"""Manage per-language facilitator membership (annotation-studio admins only).

Thin CRUD over ``AsLanguageMember``. Authorization (admin-only) is enforced at
the router via the ``AdminUser`` dependency; these functions assume the caller is
already allowed to manage membership.
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.as_language_member import AsLanguageMember
from app.db.models.auth import User
from app.services.language.get_language_or_404 import get_language_or_404


async def list_members(db: AsyncSession, language_id: str) -> list[tuple[AsLanguageMember, User]]:
    await get_language_or_404(db, language_id)
    rows = await db.execute(
        select(AsLanguageMember, User)
        .join(User, AsLanguageMember.user_id == User.id)
        .where(AsLanguageMember.language_id == language_id)
        .order_by(User.email)
    )
    return [(member, user) for member, user in rows.all()]


async def add_member(
    db: AsyncSession, language_id: str, email: str, granted_by: str | None
) -> tuple[AsLanguageMember, User]:
    await get_language_or_404(db, language_id)
    user = (
        await db.execute(select(User).where(User.email == email.strip().lower()))
    ).scalar_one_or_none()
    if user is None:
        raise NotFoundError("No user with that email. They must sign in once first.")

    existing = (
        await db.execute(
            select(AsLanguageMember).where(
                AsLanguageMember.language_id == language_id,
                AsLanguageMember.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing, user

    member = AsLanguageMember(language_id=language_id, user_id=user.id, granted_by=granted_by)
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member, user


async def remove_member(db: AsyncSession, language_id: str, user_id: str) -> None:
    await db.execute(
        delete(AsLanguageMember).where(
            AsLanguageMember.language_id == language_id,
            AsLanguageMember.user_id == user_id,
        )
    )
    await db.commit()
