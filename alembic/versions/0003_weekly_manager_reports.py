"""Add stored weekly manager reports.

Revision ID: 0003_weekly_manager_reports
Revises: 0002_ai_weekly_plan_workflow
Create Date: 2026-11-14

This migration is additive only. It creates one new table and one index.
No existing table, column, constraint, index or row is modified.

The table deliberately has no foreign keys to source tables. A stored
weekly manager report is a self-contained snapshot: deleting a task, plan,
employee or work report later must not break the historical document.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision: str = "0003_weekly_manager_reports"
down_revision: Union[str, None] = "0002_ai_weekly_plan_workflow"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


REPORT_TABLE = "weekly_manager_reports"
INDEX_NAME = "ix_weekly_manager_reports_week_version"


def _create_report_table() -> None:
    op.create_table(
        REPORT_TABLE,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("week_start_date", sa.Date(), nullable=False),
        sa.Column("week_end_date", sa.Date(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column(
            "request_fingerprint",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column(
            "is_partial_week",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("extra_instructions", sa.Text(), nullable=True),
        sa.Column(
            "metrics_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "data_quality",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "narrative",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "references",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
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
            name="ck_weekly_manager_reports_status",
        ),
        sa.CheckConstraint(
            "version >= 1",
            name="ck_weekly_manager_reports_version",
        ),
        sa.CheckConstraint(
            "week_end_date >= week_start_date",
            name="ck_weekly_manager_reports_date_range",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "week_start_date",
            "version",
            name="uq_weekly_manager_reports_week_version",
        ),
        sa.UniqueConstraint(
            "request_id",
            name="uq_weekly_manager_reports_request_id",
        ),
    )

    op.execute(
        sa.text(
            f"CREATE INDEX {INDEX_NAME} "
            f"ON {REPORT_TABLE} "
            "(week_start_date DESC, version DESC)"
        )
    )


def upgrade() -> None:
    if context.is_offline_mode():
        _create_report_table()
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if REPORT_TABLE in inspector.get_table_names():
        return

    _create_report_table()


def downgrade() -> None:
    if context.is_offline_mode():
        op.execute(
            sa.text(f"DROP INDEX IF EXISTS {INDEX_NAME}")
        )
        op.drop_table(REPORT_TABLE)
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if REPORT_TABLE not in inspector.get_table_names():
        return

    index_names = {
        index["name"]
        for index in inspector.get_indexes(REPORT_TABLE)
        if index.get("name")
    }

    if INDEX_NAME in index_names:
        op.drop_index(INDEX_NAME, table_name=REPORT_TABLE)

    op.drop_table(REPORT_TABLE)
