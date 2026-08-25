"""the resource-request module's tables: requests, evaluations, funds, ledger, board

Revision ID: 20260825_rr01
Revises: 20260819_room08
Create Date: 2026-08-25

Written by hand, like the other 66 revisions here. `alembic/env.py` imports only
`app.core.database`, so its metadata is empty and `--autogenerate` would emit a
migration dropping all 64 existing tables (docs/resource_requests.md §8.1).

The append-only DDL is spelled out here rather than imported from
`app.db.models.resource_request`, following the reasoning 20260731_0001 recorded:
importing a model module executes `app.core.database`, which builds a database engine at
import time, and an unrelated import error would then fail the deploy's migration step
before a single statement runs. A migration is also a permanent record of what ran on
this date and should keep running exactly that.

The enum objects are shared between the tables that use them. Alembic keeps one impl for
the whole run and the PostgreSQL ENUM type memoises against its `_ddl_runner`, so the
type is created once and every later table reuses it rather than failing on a second
CREATE TYPE.

`rr_requests.revision_of_id` and `rr_snapshots.request_id` reference each other, so the
first is added afterwards, once both tables exist. `use_alter=True` on the model is what
says the same thing to `create_all`, and it costs nothing under pytest: SQLite cannot
ALTER TABLE ADD CONSTRAINT, so SQLAlchemy writes that FK inline instead, and it is
enforced there like every other constraint in this revision.

The append-only trigger is written in plpgsql with no dialect guard, unlike what
docs/resource_requests.md §8.2 expects. Measured against this graph: `alembic upgrade
head` cannot run on SQLite at all — 20260226_0001 creates `users` with
`server_default=sa.text("now()")`, which SQLite rejects outright — and nothing runs
alembic anywhere but PostgreSQL (docker-compose, Dockerfile.dev, restore_local_db.sh,
migrations.yml, deploy.yml). A branch for a dialect this file never meets would be dead
code that no test could reach. The SQLite half of the same guard lives in the model,
where `Base.metadata.create_all` is what builds the test suite's schema.
"""

import sqlalchemy as sa

from alembic import op

revision = "20260825_rr01"
down_revision = "20260819_room08"
branch_labels = None
depends_on = None

REQUEST_TYPE = sa.Enum("traducao", "treinamento", "equipamentos", name="rr_request_type_enum")
STAGE = sa.Enum(
    "triagem", "analise", "aprovado", "condicional", "revisar", "recusado", name="rr_stage_enum"
)
DECISION = sa.Enum("approved", "conditional", "revise", "declined", name="rr_decision_enum")
CURRENCY = sa.Enum("BRL", "USD", "EUR", name="rr_currency_enum")
MOVEMENT_KIND = sa.Enum(
    "allocation", "commitment", "approval_deduction", "reversal", name="rr_movement_kind_enum"
)

APPEND_ONLY_TABLES = ("rr_fund_movements", "rr_snapshots")

APPEND_ONLY_FUNCTION = (
    "CREATE OR REPLACE FUNCTION rr_reject_write() RETURNS trigger AS $$ "
    "BEGIN RAISE EXCEPTION '% is append-only', TG_TABLE_NAME; END; $$ LANGUAGE plpgsql"
)


def upgrade() -> None:
    op.create_table(
        "rr_funds",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("provisional", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "rr_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("request_type", REQUEST_TYPE, nullable=False),
        sa.Column("reg_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("stage", STAGE, nullable=False),
        sa.Column("currency", CURRENCY, nullable=False),
        sa.Column("fund_id", sa.String(32), sa.ForeignKey("rr_funds.id"), nullable=True),
        sa.Column("amount_requested", sa.Numeric(14, 2), nullable=True),
        sa.Column("declaration", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("tpp_name", sa.String(160), nullable=False, server_default=""),
        sa.Column("tpp_date", sa.Date(), nullable=True),
        sa.Column("leader_name", sa.String(160), nullable=False, server_default=""),
        sa.Column("leader_date", sa.Date(), nullable=True),
        sa.Column(
            "created_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("revision_of_id", sa.String(36), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_rr_requests_stage", "rr_requests", ["stage"])
    op.create_index("ix_rr_requests_fund_id", "rr_requests", ["fund_id"])
    op.create_index("ix_rr_requests_created_by", "rr_requests", ["created_by"])
    op.create_index("ix_rr_requests_stage_created", "rr_requests", ["stage", "created_at"])

    op.create_table(
        "rr_request_sections",
        sa.Column(
            "request_id",
            sa.String(36),
            sa.ForeignKey("rr_requests.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("content", sa.JSON(), nullable=False, server_default="{}"),
    )

    op.create_table(
        "rr_budget_lines",
        sa.Column(
            "request_id",
            sa.String(36),
            sa.ForeignKey("rr_requests.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("category_key", sa.String(48), primary_key=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("quantity", sa.Numeric(14, 2), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=True),
    )

    op.create_table(
        "rr_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "request_id", sa.String(36), sa.ForeignKey("rr_requests.id"), nullable=False
        ),
        sa.Column("document", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_rr_snapshots_request_id", "rr_snapshots", ["request_id"])

    op.create_table(
        "rr_evaluations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "snapshot_id",
            sa.String(36),
            sa.ForeignKey("rr_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "evaluator_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("decision", DECISION, nullable=True),
        sa.Column("comments", sa.Text(), nullable=False, server_default=""),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "snapshot_id", "evaluator_id", name="uq_rr_evaluations_snapshot_evaluator"
        ),
    )
    op.create_index("ix_rr_evaluations_snapshot_id", "rr_evaluations", ["snapshot_id"])

    op.create_table(
        "rr_evaluation_scores",
        sa.Column(
            "evaluation_id",
            sa.String(36),
            sa.ForeignKey("rr_evaluations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("criterion_key", sa.String(64), primary_key=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= 5)", name="ck_rr_evaluation_scores_range"
        ),
    )

    op.create_table(
        "rr_fund_movements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("fund_id", sa.String(32), sa.ForeignKey("rr_funds.id"), nullable=False),
        sa.Column("request_id", sa.String(36), sa.ForeignKey("rr_requests.id"), nullable=True),
        sa.Column("kind", MOVEMENT_KIND, nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", CURRENCY, nullable=False),
        sa.Column(
            "reverses_id", sa.String(36), sa.ForeignKey("rr_fund_movements.id"), nullable=True
        ),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_rr_fund_movements_fund_id", "rr_fund_movements", ["fund_id"])
    op.create_index("ix_rr_fund_movements_request_id", "rr_fund_movements", ["request_id"])
    op.create_index(
        "ix_rr_fund_movements_fund_created", "rr_fund_movements", ["fund_id", "created_at"]
    )

    op.create_table(
        "rr_board_transitions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "request_id",
            sa.String(36),
            sa.ForeignKey("rr_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_stage", STAGE, nullable=True),
        sa.Column("to_stage", STAGE, nullable=False),
        sa.Column(
            "moved_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "movement_id", sa.String(36), sa.ForeignKey("rr_fund_movements.id"), nullable=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_rr_board_transitions_request_id", "rr_board_transitions", ["request_id"])
    op.create_index(
        "ix_rr_board_transitions_request_created",
        "rr_board_transitions",
        ["request_id", "created_at"],
    )

    op.create_foreign_key(
        "fk_rr_requests_revision_of", "rr_requests", "rr_snapshots", ["revision_of_id"], ["id"]
    )

    op.execute(APPEND_ONLY_FUNCTION)
    for table in APPEND_ONLY_TABLES:
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION rr_reject_write()"
        )


def downgrade() -> None:
    for table in APPEND_ONLY_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS {table}_append_only ON {table}")
    op.execute("DROP FUNCTION IF EXISTS rr_reject_write()")

    op.drop_constraint("fk_rr_requests_revision_of", "rr_requests", type_="foreignkey")

    op.drop_table("rr_board_transitions")
    op.drop_table("rr_fund_movements")
    op.drop_table("rr_evaluation_scores")
    op.drop_table("rr_evaluations")
    op.drop_table("rr_snapshots")
    op.drop_table("rr_budget_lines")
    op.drop_table("rr_request_sections")
    op.drop_table("rr_requests")
    op.drop_table("rr_funds")

    bind = op.get_bind()
    for enum_type in (MOVEMENT_KIND, CURRENCY, DECISION, STAGE, REQUEST_TYPE):
        enum_type.drop(bind, checkfirst=True)
