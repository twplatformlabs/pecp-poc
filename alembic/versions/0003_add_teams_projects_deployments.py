"""Add teams, team_members, projects, deployments tables and extend resource_records.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-14
"""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Extend resource_records — batch mode required for SQLite (render_as_batch=True in env.py)
    with op.batch_alter_table("resource_records") as batch_op:
        batch_op.add_column(sa.Column("project", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    # 2. Create teams table
    op.create_table(
        "teams",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_teams_name"),
    )

    # 3. Create team_members table
    op.create_table(
        "team_members",
        sa.Column("team_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.PrimaryKeyConstraint("team_id", "user_id"),
    )

    # 4. Create projects table
    op.create_table(
        "projects",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("team_id", sa.String(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("environments", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "name", name="uq_projects_team_name"),
    )

    # 5. Create deployments table
    op.create_table(
        "deployments",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("resource_id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=True),
        sa.Column("environment", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("change_type", sa.Text(), nullable=False),
        sa.Column("deployed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["resource_id"], ["resource_records.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    # Reverse order — satisfy FK constraints
    op.drop_table("deployments")
    op.drop_table("projects")
    op.drop_table("team_members")
    op.drop_table("teams")
    with op.batch_alter_table("resource_records") as batch_op:
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("project")
