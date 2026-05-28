"""Tests for ServiceNowMockAdapter (Wave 0 scaffold — populated by Plan 02; covers ADPT-02, ADPT-03, KINDS-01)."""

import pytest


def test_servicenow_module_not_yet_implemented() -> None:
    pytest.importorskip("pecp.adapters.mock.servicenow", reason="Wave 0 scaffold — adapter arrives in Plan 02/03/04")
    pytest.skip("Implementation plan owns this test")
