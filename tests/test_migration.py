"""Smoke tests for Alembic migration 0004 (github fields).

Exercises the full upgrade/downgrade cycle of migration 0004 against an
isolated file-based SQLite database under tmp_path, verifying that
github_team_slug is added to teams and project_repos is created on upgrade
and both are removed on downgrade. The live pecp.db is never touched.
"""

import importlib

import alembic.command
import alembic.config
import pytest
from sqlalchemy import create_engine, inspect


def test_migration_upgrade_and_downgrade(tmp_path, monkeypatch):
    # 1. Compute paths — file-based SQLite required (Alembic opens multiple connections)
    db_path = tmp_path / "test_migration.db"
    async_url = f"sqlite+aiosqlite:///{db_path}"
    sync_url = f"sqlite:///{db_path}"

    # 2. Isolate test DB from live pecp.db via monkeypatch + module reload
    monkeypatch.setenv("PECP_DATABASE_URL", async_url)
    import pecp.persistence.database as db_module
    importlib.reload(db_module)

    # 3. Configure Alembic — env.py reads DATABASE_URL from reloaded module, not alembic.ini
    cfg = alembic.config.Config("alembic.ini")

    # 4. Run upgrade: applies all migrations 0000 -> 0004 against tmp DB
    alembic.command.upgrade(cfg, "head")

    # 5. Inspect post-upgrade schema with sync engine (async engines are not supported by inspect)
    engine = create_engine(sync_url)
    insp = inspect(engine)

    teams_cols = [c["name"] for c in insp.get_columns("teams")]
    assert "github_team_slug" in teams_cols, (
        f"Expected github_team_slug in teams columns after upgrade, got: {teams_cols}"
    )

    table_names = insp.get_table_names()
    assert "project_repos" in table_names, (
        f"Expected project_repos table after upgrade, got: {table_names}"
    )

    repo_cols = {c["name"] for c in insp.get_columns("project_repos")}
    assert {"id", "project_id", "repo_name", "repo_url", "created_at"}.issubset(repo_cols), (
        f"Expected all project_repos columns after upgrade, got: {repo_cols}"
    )

    uc_names = [uc["name"] for uc in insp.get_unique_constraints("project_repos")]
    assert "uq_project_repos_project_name" in uc_names, (
        f"Expected uq_project_repos_project_name unique constraint, got: {uc_names}"
    )

    fks = insp.get_foreign_keys("project_repos")
    assert any(fk["referred_table"] == "projects" for fk in fks), (
        f"Expected FK from project_repos to projects, got: {fks}"
    )

    engine.dispose()

    # 6. Run downgrade: rolls back to revision 0003
    alembic.command.downgrade(cfg, "-1")

    # 7. Inspect post-downgrade schema with a fresh sync engine
    engine2 = create_engine(sync_url)
    insp2 = inspect(engine2)

    teams_cols_after = [c["name"] for c in insp2.get_columns("teams")]
    assert "github_team_slug" not in teams_cols_after, (
        f"Expected github_team_slug removed from teams after downgrade, got: {teams_cols_after}"
    )

    table_names_after = insp2.get_table_names()
    assert "project_repos" not in table_names_after, (
        f"Expected project_repos table removed after downgrade, got: {table_names_after}"
    )

    engine2.dispose()

    # 8. Restore prior session state — re-bind db_module.DATABASE_URL to pre-test value
    importlib.reload(db_module)
