"""Add env and notes columns and unique constraint to resource_records.

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-14
"""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("resource_records", sa.Column("env", sa.Text(), nullable=True))
    op.add_column(
        "resource_records",
        sa.Column("notes", sa.Text(), nullable=True, server_default="[]"),
    )
    with op.batch_alter_table("resource_records") as batch_op:
        batch_op.create_unique_constraint(
            "uq_resource_team_kind_name", ["team", "kind", "name"]
        )


def downgrade() -> None:
    with op.batch_alter_table("resource_records") as batch_op:
        batch_op.drop_constraint("uq_resource_team_kind_name", type_="unique")
    op.drop_column("resource_records", "notes")
    op.drop_column("resource_records", "env")
