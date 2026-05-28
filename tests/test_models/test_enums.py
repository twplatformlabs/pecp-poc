"""Tests for ResourceStatus enum (D-12)."""

from pecp.models.enums import ResourceStatus


def test_resource_status_ready_value() -> None:
    """D-12: ResourceStatus.ready.value == 'ready'."""
    assert ResourceStatus.ready.value == "ready"


def test_resource_status_has_four_members() -> None:
    """D-12: Exactly 4 members: pending, provisioning, ready, failed."""
    members = {m.value for m in ResourceStatus}
    assert members == {"pending", "provisioning", "ready", "failed"}


def test_resource_status_is_string_enum() -> None:
    """D-12: str mixin — serializes as string value."""
    assert isinstance(ResourceStatus.pending, str)
    assert ResourceStatus.pending == "pending"
