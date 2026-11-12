"""Add AI weekly-plan drafts, source tracking and version lifecycle.

Revision ID: 0002_ai_weekly_plan_workflow
Revises: 0001_baseline
Create Date: 2026-11-12

Existing weekly plans are preserved and marked as approved manual plans,
because they were already used as official targets before this feature.
The old UNIQUE(task_id, week_start_date) constraint is replaced by a
partial unique index that only enforces uniqueness for approved plans.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0002_ai_weekly_plan_workflow"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PLAN_TABLE = "weekly_task_plans"
GENERATION_TABLE = "weekly_plan_generations"


def _columns(inspector, table: str) -> set[str]:
    return {
        column["name"]
        for column in inspector.get_columns(table)
    }


def _constraint_names(inspector, table: str) -> set[str]:
    names = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints(table)
        if constraint.get("name")
    }
    names.update(
        {
            constraint["name"]
            for constraint in inspector.get_check_constraints(table)
            if constraint.get("name")
        }
    )
    names.update(
        {
            constraint["name"]
            for constraint in inspector.get_foreign_keys(table)
            if constraint.get("name")
        }
    )
    return names


def _index_names(inspector, table: str) -> set[str]:
    return {
        index["name"]
        for index in inspector.get_indexes(table)
        if index.get("name")
    }


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if GENERATION_TABLE not in tables:
        op.create_table(
            GENERATION_TABLE,
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("request_id", sa.String(length=64), nullable=False),
            sa.Column(
                "request_fingerprint",
                sa.String(length=64),
                nullable=True,
            ),
            sa.Column("model", sa.String(length=100), nullable=True),
            sa.Column("extra_instructions", sa.Text(), nullable=True),
            sa.Column(
                "status",
                sa.String(length=20),
                server_default=sa.text("'pending'"),
                nullable=False,
            ),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "completed_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.CheckConstraint(
                "status IN ('pending', 'completed', 'failed')",
                name="ck_weekly_plan_generations_status",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "request_id",
                name="uq_weekly_plan_generations_request_id",
            ),
        )

    inspector = sa.inspect(bind)
    columns = _columns(inspector, PLAN_TABLE)

    if "status" not in columns:
        # Existing rows are official plans created before this feature.
        op.add_column(
            PLAN_TABLE,
            sa.Column(
                "status",
                sa.String(length=20),
                server_default=sa.text("'approved'"),
                nullable=False,
            ),
        )

    if "source" not in columns:
        op.add_column(
            PLAN_TABLE,
            sa.Column(
                "source",
                sa.String(length=20),
                server_default=sa.text("'manual'"),
                nullable=False,
            ),
        )

    if "generation_id" not in columns:
        op.add_column(
            PLAN_TABLE,
            sa.Column("generation_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "weekly_task_plans_generation_id_fkey",
            PLAN_TABLE,
            GENERATION_TABLE,
            ["generation_id"],
            ["id"],
            ondelete="SET NULL",
        )

    if "ai_rationale" not in columns:
        op.add_column(
            PLAN_TABLE,
            sa.Column("ai_rationale", sa.Text(), nullable=True),
        )

    if "ai_assumptions" not in columns:
        op.add_column(
            PLAN_TABLE,
            sa.Column("ai_assumptions", sa.Text(), nullable=True),
        )

    if "ai_warnings" not in columns:
        op.add_column(
            PLAN_TABLE,
            sa.Column("ai_warnings", sa.Text(), nullable=True),
        )

    if "approved_at" not in columns:
        op.add_column(
            PLAN_TABLE,
            sa.Column(
                "approved_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        )

    op.execute(
        """
        UPDATE weekly_task_plans
        SET approved_at = updated_at
        WHERE status = 'approved' AND approved_at IS NULL
        """
    )

    # New plans start as drafts. Existing rows keep their approved status.
    op.alter_column(
        PLAN_TABLE,
        "status",
        server_default=sa.text("'draft'"),
        existing_type=sa.String(length=20),
        existing_nullable=False,
    )

    inspector = sa.inspect(bind)
    constraint_names = _constraint_names(inspector, PLAN_TABLE)

    if "uq_weekly_plans_task_week" in constraint_names:
        op.drop_constraint(
            "uq_weekly_plans_task_week",
            PLAN_TABLE,
            type_="unique",
        )
    elif "uq_weekly_plans_task_week" in _index_names(
        inspector,
        PLAN_TABLE,
    ):
        op.drop_index(
            "uq_weekly_plans_task_week",
            table_name=PLAN_TABLE,
        )

    inspector = sa.inspect(bind)
    constraint_names = _constraint_names(inspector, PLAN_TABLE)

    if "ck_weekly_plans_status" not in constraint_names:
        op.create_check_constraint(
            "ck_weekly_plans_status",
            PLAN_TABLE,
            "status IN ('draft', 'approved', 'rejected', 'superseded')",
        )

    if "ck_weekly_plans_source" not in constraint_names:
        op.create_check_constraint(
            "ck_weekly_plans_source",
            PLAN_TABLE,
            "source IN ('manual', 'ai')",
        )

    inspector = sa.inspect(bind)

    if (
        "uq_weekly_plans_approved_task_week"
        not in _index_names(inspector, PLAN_TABLE)
    ):
        op.create_index(
            "uq_weekly_plans_approved_task_week",
            PLAN_TABLE,
            ["task_id", "week_start_date"],
            unique=True,
            postgresql_where=sa.text("status = 'approved'"),
        )

    if (
        "ix_weekly_task_plans_generation_id"
        not in _index_names(inspector, PLAN_TABLE)
    ):
        op.create_index(
            "ix_weekly_task_plans_generation_id",
            PLAN_TABLE,
            ["generation_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if (
        "uq_weekly_plans_approved_task_week"
        in _index_names(inspector, PLAN_TABLE)
    ):
        op.drop_index(
            "uq_weekly_plans_approved_task_week",
            table_name=PLAN_TABLE,
        )

    inspector = sa.inspect(bind)
    constraint_names = _constraint_names(inspector, PLAN_TABLE)

    if "ck_weekly_plans_source" in constraint_names:
        op.drop_constraint(
            "ck_weekly_plans_source",
            PLAN_TABLE,
            type_="check",
        )

    if "ck_weekly_plans_status" in constraint_names:
        op.drop_constraint(
            "ck_weekly_plans_status",
            PLAN_TABLE,
            type_="check",
        )

    inspector = sa.inspect(bind)

    if (
        "ix_weekly_task_plans_generation_id"
        in _index_names(inspector, PLAN_TABLE)
    ):
        op.drop_index(
            "ix_weekly_task_plans_generation_id",
            table_name=PLAN_TABLE,
        )

    columns = _columns(sa.inspect(bind), PLAN_TABLE)
    constraint_names = _constraint_names(
        sa.inspect(bind),
        PLAN_TABLE,
    )

    if "weekly_task_plans_generation_id_fkey" in constraint_names:
        op.drop_constraint(
            "weekly_task_plans_generation_id_fkey",
            PLAN_TABLE,
            type_="foreignkey",
        )

    for column in (
        "generation_id",
        "approved_at",
        "ai_warnings",
        "ai_assumptions",
        "ai_rationale",
    ):
        if column in columns:
            op.drop_column(PLAN_TABLE, column)

    columns = _columns(sa.inspect(bind), PLAN_TABLE)

    if "source" in columns:
        op.drop_column(PLAN_TABLE, "source")

    if "status" in columns:
        op.drop_column(PLAN_TABLE, "status")

    inspector = sa.inspect(bind)

    if (
        "uq_weekly_plans_task_week"
        not in _constraint_names(inspector, PLAN_TABLE)
        and "uq_weekly_plans_task_week"
        not in _index_names(inspector, PLAN_TABLE)
    ):
        op.create_unique_constraint(
            "uq_weekly_plans_task_week",
            PLAN_TABLE,
            ["task_id", "week_start_date"],
        )

    if GENERATION_TABLE in set(
        sa.inspect(bind).get_table_names()
    ):
        op.drop_table(GENERATION_TABLE)
