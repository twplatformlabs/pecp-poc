"""Tests for ProvisionResult model (D-01, D-02, D-03)."""

from pecp.models.enums import ResourceStatus
from pecp.models.provision_result import ProvisionResult


def test_provision_result_defaults_to_empty_collections() -> None:
    """D-01, D-02, D-03: Default factories produce empty containers."""
    result = ProvisionResult(status=ResourceStatus.pending)
    assert result.provider_metadata == {}
    assert result.activity_log == []
    assert result.error is None


def test_provision_result_failed_status_carries_error() -> None:
    """D-02: error field accepts string on failed status."""
    result = ProvisionResult(status=ResourceStatus.failed, error="Quota exceeded")
    assert result.status == ResourceStatus.failed
    assert result.error == "Quota exceeded"


def test_get_status_reuse_allows_empty_log_and_metadata() -> None:
    """D-03: get_status() reuses ProvisionResult; activity_log may be empty."""
    result = ProvisionResult(status=ResourceStatus.ready)
    assert result.activity_log == []
    assert result.provider_metadata == {}
