"""Add provider_metadata and activity_log columns to resource_records.

Revision ID: 0001
Revises: None
Create Date: 2026-05-28
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = "0000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("resource_records", sa.Column("provider_metadata", sa.Text(), nullable=True, server_default="{}"))
    op.add_column("resource_records", sa.Column("activity_log", sa.Text(), nullable=True, server_default="[]"))


def downgrade() -> None:
    op.drop_column("resource_records", "activity_log")
    op.drop_column("resource_records", "provider_metadata")
