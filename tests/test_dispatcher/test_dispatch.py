"""Tests for Dispatcher state machine (D-03, D-04, ADPT-02, KINDS-01) — RED gate."""

import pytest


def test_dispatcher_module_importable() -> None:
    """RED gate: will fail until dispatcher.py is created."""
    from pecp.dispatcher import dispatch, ADAPTER_REGISTRY, AdapterNotFoundError  # noqa: F401
    assert len(ADAPTER_REGISTRY) == 10, "ADAPTER_REGISTRY must have exactly 10 entries"
