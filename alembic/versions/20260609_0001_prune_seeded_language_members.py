"""annotation-studio: prune seeded (no-lockout) language memberships

Migration 20260608_0001 seeded an as_language_members row for every existing
annotation-studio user across every active language, so nobody was locked out on
deploy. That made per-language scoping ineffective (everyone could edit every
language). This removes those seeded grants so only explicitly-invited members
keep access.

Seeded rows are exactly those with ``granted_by IS NULL`` (the seed insert omitted
``granted_by``); Members-panel invites always set ``granted_by`` to the admin's id.
Admins and platform admins bypass membership entirely, so they are unaffected.

Revision ID: 20260609_0001
Revises: 20260608_0001
Create Date: 2026-06-09 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260609_0001"
down_revision: str | None = "20260608_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Delete only seeded grants; explicitly-invited memberships (granted_by set) stay.
    op.execute(sa.text("DELETE FROM as_language_members WHERE granted_by IS NULL"))


def downgrade() -> None:
    # Irreversible: the original seed set cannot be reconstructed. No-op.
    pass
