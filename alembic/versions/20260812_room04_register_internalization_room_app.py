"""register the internalization room so a facilitator can be given access

Revision ID: 20260812_room04
Revises: 20260812_room03

The team's app needs none of this — it carries a device key and never signs in. This is for
the person on the other end of the hand, who answers the team's questions and whose answers
are attributable to them.
"""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "20260812_room04"
down_revision = "20260812_room03"
branch_labels = None
depends_on = None

APP_KEY = "internalization-room"
APP_NAME = "Internalization Room"
APP_DESCRIPTION = (
    "A sala de internalização: a equipe trabalha por voz, e um facilitador responde "
    "as perguntas levantadas pela mão."
)
ROLES = [
    (
        "facilitator",
        "Facilitador",
        "Ouve as perguntas da equipe e responde por áudio, ou marca como resolvida "
        "quando vai falar com a equipe por outro meio.",
    ),
    ("admin", "Administrador", "Administra o acesso à sala."),
]


def upgrade() -> None:
    bind = op.get_bind()
    app_id = bind.execute(
        sa.text("SELECT id FROM apps WHERE app_key = :app_key"), {"app_key": APP_KEY}
    ).scalar()
    if app_id is None:
        app_id = str(uuid.uuid4())
        bind.execute(
            sa.text(
                "INSERT INTO apps (id, app_key, name, description, platform, is_active) "
                "VALUES (:id, :app_key, :name, :description, 'web', TRUE)"
            ),
            {
                "id": app_id,
                "app_key": APP_KEY,
                "name": APP_NAME,
                "description": APP_DESCRIPTION,
            },
        )

    for role_key, label, description in ROLES:
        exists = bind.execute(
            sa.text("SELECT id FROM roles WHERE app_id = :app_id AND role_key = :role_key"),
            {"app_id": app_id, "role_key": role_key},
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
                    "role_key": role_key,
                    "label": label,
                    "description": description,
                },
            )


def downgrade() -> None:
    bind = op.get_bind()
    app_id = bind.execute(
        sa.text("SELECT id FROM apps WHERE app_key = :app_key"), {"app_key": APP_KEY}
    ).scalar()
    if app_id is not None:
        bind.execute(sa.text("DELETE FROM roles WHERE app_id = :id"), {"id": app_id})
        bind.execute(sa.text("DELETE FROM apps WHERE id = :id"), {"id": app_id})
