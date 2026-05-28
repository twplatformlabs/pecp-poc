"""Tests for AwsDataMockAdapter (Wave 0 scaffold — populated by Plan 02; covers ADPT-02, ADPT-03, KINDS-03)."""

import pytest


def test_aws_data_module_not_yet_implemented() -> None:
    pytest.importorskip("pecp.adapters.mock.aws_data", reason="Wave 0 scaffold — adapter arrives in Plan 02/03/04")
    pytest.skip("Implementation plan owns this test")
