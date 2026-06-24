"""Add github_team_slug to teams and create project_repos table.

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-24
"""

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add github_team_slug column to existing teams table (batch mode required for SQLite)
    with op.batch_alter_table("teams") as batch_op:
        batch_op.add_column(sa.Column("github_team_slug", sa.Text(), nullable=True))

    # 2. Create project_repos table with FK to projects and named unique constraint
    op.create_table(
        "project_repos",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("repo_name", sa.Text(), nullable=False),
        sa.Column("repo_url", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "repo_name", name="uq_project_repos_project_name"),
    )


def downgrade() -> None:
    # Reverse order — drop project_repos first before removing github_team_slug
    op.drop_table("project_repos")

    # Remove github_team_slug from teams table (batch mode required for SQLite)
    with op.batch_alter_table("teams") as batch_op:
        batch_op.drop_column("github_team_slug")
