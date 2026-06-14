"""Create initial resource_records table.

Revision ID: 0000
Revises:
Create Date: 2026-05-28
"""

import sqlalchemy as sa
from alembic import op

revision = "0000"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "resource_records",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("team", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("spec_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_resource_records_team", "resource_records", ["team"])


def downgrade() -> None:
    op.drop_index("ix_resource_records_team", table_name="resource_records")
    op.drop_table("resource_records")
