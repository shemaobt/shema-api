"""register the consultant: a reader of every team's work in the Desk, who writes nothing

ADR 0058. Granted to a person like the facilitator role, never linked to a team.

Revision ID: 20261011_cons01
Revises: 20261007_pend01
"""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "20261011_cons01"
down_revision = "20261007_pend01"
branch_labels = None
depends_on = None

APP_KEY = "internalization-room"
ROLE_KEY = "consultant"
LABEL = "Consultor"
DESCRIPTION = (
    "Lê o trabalho de todas as equipes na mesa, depois do fato, para aprovar ou reprovar uma "
    "passagem; não responde, não força e não zera."
)


def upgrade() -> None:
    bind = op.get_bind()
    app_id = bind.execute(
        sa.text("SELECT id FROM apps WHERE app_key = :app_key"), {"app_key": APP_KEY}
    ).scalar()
    if app_id is None:
        return
    exists = bind.execute(
        sa.text("SELECT id FROM roles WHERE app_id = :app_id AND role_key = :role_key"),
        {"app_id": app_id, "role_key": ROLE_KEY},
    ).scalar()
    if exists is None:
        bind.execute(
            sa.text(
                "INSERT INTO roles (id, app_id, role_key, label, description, is_system) "
                "VALUES (:id, :app_id, :role_key, :label, :description, TRUE)"
            ),
            {
                "id": str(uuid.uuid4()),
                "app_id": app_id,
                "role_key": ROLE_KEY,
                "label": LABEL,
                "description": DESCRIPTION,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    the_role = (
        "SELECT r.id FROM roles r JOIN apps a ON a.id = r.app_id "
        "WHERE a.app_key = :app_key AND r.role_key = :role_key"
    )
    params = {"app_key": APP_KEY, "role_key": ROLE_KEY}
    bind.execute(sa.text(f"DELETE FROM user_app_roles WHERE role_id IN ({the_role})"), params)
    bind.execute(sa.text(f"DELETE FROM roles WHERE id IN ({the_role})"), params)
