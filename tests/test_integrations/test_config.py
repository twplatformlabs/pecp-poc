"""Tests for IntegrationConfig + load_and_register_integrations (INTG-03)."""

import logging

from pecp.integrations import (
    INTEGRATION_REGISTRY,
    IntegrationConfig,
    load_and_register_integrations,
)


def _clear_registry() -> list:
    original = list(INTEGRATION_REGISTRY)
    INTEGRATION_REGISTRY.clear()
    return original


def _restore_registry(original: list) -> None:
    INTEGRATION_REGISTRY.clear()
    INTEGRATION_REGISTRY.extend(original)


def test_config_defaults_to_empty_strings(monkeypatch) -> None:
    """IntegrationConfig with no env vars has empty-string defaults."""
    monkeypatch.delenv("GITHUB_PAT", raising=False)
    monkeypatch.delenv("GITHUB_ORG", raising=False)
    cfg = IntegrationConfig()
    assert cfg.GITHUB_PAT == ""
    assert cfg.GITHUB_ORG == ""


def test_config_reads_env_when_set(monkeypatch) -> None:
    """IntegrationConfig reads GITHUB_PAT and GITHUB_ORG from env when set."""
    monkeypatch.setenv("GITHUB_PAT", "ghp_test_pat_value")
    monkeypatch.setenv("GITHUB_ORG", "test-org")
    cfg = IntegrationConfig()
    assert cfg.GITHUB_PAT == "ghp_test_pat_value"
    assert cfg.GITHUB_ORG == "test-org"


def test_missing_env_logs_warning_not_crash(monkeypatch, caplog) -> None:
    """load_and_register_integrations with missing env logs a warning and does not crash."""
    monkeypatch.delenv("GITHUB_PAT", raising=False)
    monkeypatch.delenv("GITHUB_ORG", raising=False)

    original = _clear_registry()
    try:
        with caplog.at_level(logging.WARNING, logger="pecp.integrations"):
            load_and_register_integrations()

        # No exception was raised
        assert len(INTEGRATION_REGISTRY) == 0
        # A warning containing "GITHUB_PAT" was logged
        assert any(
            "GITHUB_PAT" in r.message
            for r in caplog.records
            if r.levelno == logging.WARNING
        ), f"No WARNING about GITHUB_PAT found in: {[(r.levelname, r.message) for r in caplog.records]}"
    finally:
        _restore_registry(original)


def test_warning_message_does_not_contain_pat_value(monkeypatch, caplog) -> None:
    """load_and_register_integrations warning never contains the PAT value (T-07-03)."""
    monkeypatch.setenv("GITHUB_PAT", "ghp_FAKE_LEAKED_SECRET_123")
    monkeypatch.delenv("GITHUB_ORG", raising=False)

    original = _clear_registry()
    try:
        with caplog.at_level(logging.WARNING, logger="pecp.integrations"):
            load_and_register_integrations()

        for record in caplog.records:
            assert "ghp_FAKE_LEAKED_SECRET_123" not in record.message, (
                f"PAT value leaked in log message: {record.message}"
            )
    finally:
        _restore_registry(original)


def test_empty_registry_when_env_missing(monkeypatch) -> None:
    """load_and_register_integrations leaves INTEGRATION_REGISTRY empty when env is missing."""
    monkeypatch.delenv("GITHUB_PAT", raising=False)
    monkeypatch.delenv("GITHUB_ORG", raising=False)

    original = _clear_registry()
    try:
        load_and_register_integrations()
        assert len(INTEGRATION_REGISTRY) == 0
    finally:
        _restore_registry(original)
