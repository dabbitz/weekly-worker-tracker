"""Baseline schema for WorkTrack.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-11-12

This revision records the schema that already existed before migrations
were introduced. On an existing database it is intentionally a no-op so
that no table or row is ever recreated. On an empty database it creates
the original schema, after which later revisions apply the AI weekly
planning changes.

Downgrade is intentionally a no-op: dropping the original application
tables would destroy real data. The feature revision itself (0002) is
fully reversible.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


WEEKDAY_EXPRESSION = """
CASE EXTRACT(ISODOW FROM {column})
    WHEN 1 THEN 'pazartesi'
    WHEN 2 THEN 'salı'
    WHEN 3 THEN 'çarşamba'
    WHEN 4 THEN 'perşembe'
    WHEN 5 THEN 'cuma'
    WHEN 6 THEN 'cumartesi'
    WHEN 7 THEN 'pazar'
END
"""


def upgrade() -> None:
    bind = op.get_bind()
    existing_tables = set(sa.inspect(bind).get_table_names())

    if "weekly_task_plans" in existing_tables:
        # This is the real, pre-existing database. Never recreate tables.
        return

    op.create_table(
        "employees",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("role", sa.String(length=80), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_user_id"),
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("expected_completion_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=250), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("planned_start_date", sa.Date(), nullable=True),
        sa.Column(
            "planned_start_weekday",
            sa.String(length=10),
            sa.Computed(
                WEEKDAY_EXPRESSION.format(
                    column="planned_start_date"
                ),
                persisted=True,
            ),
            nullable=True,
        ),
        sa.Column("planned_due_date", sa.Date(), nullable=True),
        sa.Column(
            "planned_due_weekday",
            sa.String(length=10),
            sa.Computed(
                WEEKDAY_EXPRESSION.format(column="planned_due_date"),
                persisted=True,
            ),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "planned_start_date IS NULL "
            "OR planned_due_date IS NULL "
            "OR planned_start_date <= planned_due_date",
            name="ck_tasks_planned_dates",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tasks_project_id", "tasks", ["project_id"])

    op.create_table(
        "task_assignments",
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("task_id", "employee_id"),
    )
    op.create_index(
        "ix_task_assignments_employee",
        "task_assignments",
        ["employee_id"],
    )

    op.create_table(
        "weekly_task_plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("week_start_date", sa.Date(), nullable=False),
        sa.Column("week_end_date", sa.Date(), nullable=False),
        sa.Column("target_description", sa.Text(), nullable=False),
        sa.Column(
            "target_completion_percentage",
            sa.SmallInteger(),
            nullable=True,
        ),
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
        sa.CheckConstraint(
            "week_end_date >= week_start_date",
            name="ck_weekly_plans_date_range",
        ),
        sa.CheckConstraint(
            "target_completion_percentage IS NULL OR "
            "(target_completion_percentage BETWEEN 0 AND 100)",
            name="ck_weekly_plans_completion",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "task_id",
            "week_start_date",
            name="uq_weekly_plans_task_week",
        ),
    )
    op.create_index(
        "ix_weekly_task_plans_task_id",
        "weekly_task_plans",
        ["task_id"],
    )

    op.create_table(
        "task_updates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("weekly_plan_id", sa.Integer(), nullable=True),
        sa.Column("employee_id", sa.Integer(), nullable=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=False),
        sa.Column("original_message", sa.Text(), nullable=False),
        sa.Column(
            "task_reference_text",
            sa.String(length=250),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'unknown'"),
            nullable=False,
        ),
        sa.Column(
            "completion_percentage",
            sa.SmallInteger(),
            nullable=True,
        ),
        sa.Column("blocker", sa.Text(), nullable=True),
        sa.Column("delay_reason", sa.Text(), nullable=True),
        sa.Column("next_step", sa.Text(), nullable=True),
        sa.Column(
            "reported_eta_text",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column("reported_eta_date", sa.Date(), nullable=True),
        sa.Column(
            "reported_eta_weekday",
            sa.String(length=10),
            sa.Computed(
                WEEKDAY_EXPRESSION.format(
                    column="reported_eta_date"
                ),
                persisted=True,
            ),
            nullable=True,
        ),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "review_status",
            sa.String(length=20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "reviewed_by_employee_id",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "sync_status",
            sa.String(length=20),
            server_default=sa.text("'not_synced'"),
            nullable=False,
        ),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ai_model", sa.String(length=100), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('completed', 'in_progress', 'blocked', "
            "'not_started', 'unknown')",
            name="ck_task_updates_status",
        ),
        sa.CheckConstraint(
            "completion_percentage IS NULL OR "
            "(completion_percentage BETWEEN 0 AND 100)",
            name="ck_task_updates_completion",
        ),
        sa.CheckConstraint(
            "review_status IN ('pending', 'approved', 'rejected')",
            name="ck_task_updates_review_status",
        ),
        sa.CheckConstraint(
            "sync_status IN ('not_synced', 'synced', 'failed')",
            name="ck_task_updates_sync_status",
        ),
        sa.CheckConstraint(
            "(review_status = 'pending' "
            "AND reviewed_by_employee_id IS NULL "
            "AND reviewed_at IS NULL) "
            "OR "
            "(review_status IN ('approved', 'rejected') "
            "AND reviewed_by_employee_id IS NOT NULL "
            "AND reviewed_at IS NOT NULL)",
            name="ck_task_updates_review_consistency",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_employee_id"],
            ["employees.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["weekly_plan_id"],
            ["weekly_task_plans.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "telegram_chat_id",
            "telegram_message_id",
            name="uq_task_updates_telegram_message",
        ),
    )
    op.create_index(
        "ix_task_updates_task_received",
        "task_updates",
        ["task_id", "received_at"],
    )
    op.create_index(
        "ix_task_updates_employee_received",
        "task_updates",
        ["employee_id", "received_at"],
    )
    op.create_index(
        "ix_task_updates_weekly_plan_id",
        "task_updates",
        ["weekly_plan_id"],
    )

    op.create_table(
        "registration_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "requested_full_name",
            sa.String(length=150),
            nullable=False,
        ),
        sa.Column("employee_id", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "notification_sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "reviewed_by_telegram_user_id",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_registration_requests_status",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_registration_requests_pending_user",
        "registration_requests",
        ["telegram_user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    # Intentionally does not drop real application tables.
    pass
