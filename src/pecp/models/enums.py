"""Resource status enum — single source of truth (D-12)."""

from enum import Enum


class ResourceStatus(str, Enum):
    pending = "pending"
    provisioning = "provisioning"
    ready = "ready"
    failed = "failed"
