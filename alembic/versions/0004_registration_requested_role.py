"""Store the job title reported during Telegram registration.

Revision ID: 0004_registration_requested_role
Revises: 0003_weekly_manager_reports
Create Date: 2026-11-15

This migration is additive only. It adds one nullable column to
``registration_requests`` so the employee's position can be captured with
the request and copied to ``employees.role`` on approval.

No existing table, column, constraint, index or row is modified. The
column is nullable, so existing pending/approved/rejected requests keep
working with "not specified".
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0004_registration_requested_role"
down_revision: Union[str, None] = "0003_weekly_manager_reports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE = "registration_requests"
COLUMN = "requested_role"


def upgrade() -> None:
    op.add_column(
        TABLE,
        sa.Column(COLUMN, sa.String(length=80), nullable=True),
    )


def downgrade() -> None:
    op.drop_column(TABLE, COLUMN)
