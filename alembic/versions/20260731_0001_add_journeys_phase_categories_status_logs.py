from __future__ import annotations

import uuid

import sqlalchemy as sa

from alembic import op

revision: str = "20260731_0001"
down_revision: str | None = "20260601_0001"
branch_labels = None
depends_on = None

SEED_CATEGORIES = (
    ("Discovery", "#A87B12", "compass"),
    ("Research", "#6F5691", "search"),
    ("Planning", "#4D7068", "clipboard"),
    ("Design", "#777D45", "pen"),
    ("Development", "#BE4A01", "code"),
    ("Testing", "#A63A2E", "flask"),
    ("Deployment", "#4E5B8C", "rocket"),
    ("Maintenance", "#6B6A52", "wrench"),
)


def upgrade() -> None:
    op.create_table(
        "journeys",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "phase_categories",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("color", sa.String(length=9), nullable=False),
        sa.Column("icon", sa.String(length=40), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "phase_status_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("phase_id", sa.String(length=36), nullable=False),
        sa.Column("from_status", sa.String(length=20), nullable=False),
        sa.Column("to_status", sa.String(length=20), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("changed_by", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["phase_id"], ["phases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_phase_status_logs_project_id"),
        "phase_status_logs",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_phase_status_logs_phase_id"),
        "phase_status_logs",
        ["phase_id"],
        unique=False,
    )

    with op.batch_alter_table("phases") as batch_op:
        batch_op.add_column(sa.Column("journey_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("category_id", sa.String(length=36), nullable=True))
        batch_op.add_column(
            sa.Column(
                "sort_order",
                sa.Integer(),
                server_default=sa.text("0"),
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("icon_url", sa.String(length=500), nullable=True))
        batch_op.create_foreign_key(
            "fk_phases_journey_id_journeys",
            "journeys",
            ["journey_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_phases_category_id_phase_categories",
            "phase_categories",
            ["category_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(op.f("ix_phases_journey_id"), ["journey_id"], unique=False)

    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(sa.Column("journey_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_projects_journey_id_journeys",
            "journeys",
            ["journey_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(op.f("ix_projects_journey_id"), ["journey_id"], unique=False)

    bind = op.get_bind()
    for name, color, icon in SEED_CATEGORIES:
        bind.execute(
            sa.text(
                "INSERT INTO phase_categories (id, name, color, icon, created_at) "
                "VALUES (:id, :name, :color, :icon, CURRENT_TIMESTAMP)"
            ),
            {"id": str(uuid.uuid4()), "name": name, "color": color, "icon": icon},
        )

    phase_ids = [
        row[0]
        for row in bind.execute(sa.text("SELECT id FROM phases ORDER BY created_at, id")).all()
    ]
    if phase_ids:
        journey_id = str(uuid.uuid4())
        bind.execute(
            sa.text(
                "INSERT INTO journeys (id, name, description, created_at, updated_at) "
                "VALUES (:id, :name, :description, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {
                "id": journey_id,
                "name": "Default journey",
                "description": "Migrated from the phase catalog",
            },
        )
        for position, phase_id in enumerate(phase_ids):
            bind.execute(
                sa.text(
                    "UPDATE phases SET journey_id = :journey_id, sort_order = :sort_order "
                    "WHERE id = :id"
                ),
                {"journey_id": journey_id, "sort_order": position, "id": phase_id},
            )
        bind.execute(
            sa.text(
                "UPDATE projects SET journey_id = :journey_id "
                "WHERE id IN (SELECT DISTINCT project_id FROM project_phases)"
            ),
            {"journey_id": journey_id},
        )


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_index(op.f("ix_projects_journey_id"))
        batch_op.drop_constraint("fk_projects_journey_id_journeys", type_="foreignkey")
        batch_op.drop_column("journey_id")

    with op.batch_alter_table("phases") as batch_op:
        batch_op.drop_index(op.f("ix_phases_journey_id"))
        batch_op.drop_constraint("fk_phases_category_id_phase_categories", type_="foreignkey")
        batch_op.drop_constraint("fk_phases_journey_id_journeys", type_="foreignkey")
        batch_op.drop_column("icon_url")
        batch_op.drop_column("sort_order")
        batch_op.drop_column("category_id")
        batch_op.drop_column("journey_id")

    op.drop_index(op.f("ix_phase_status_logs_phase_id"), table_name="phase_status_logs")
    op.drop_index(op.f("ix_phase_status_logs_project_id"), table_name="phase_status_logs")
    op.drop_table("phase_status_logs")
    op.drop_table("phase_categories")
    op.drop_table("journeys")
