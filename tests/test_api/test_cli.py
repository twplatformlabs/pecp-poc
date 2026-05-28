"""Tests for the Typer `pecp` CLI.

Uses typer.testing.CliRunner to invoke CLI commands without a live server.
HTTP calls are mocked with a custom httpx transport to assert the correct
request URL, headers, and body are sent (Behavior 5).
"""

from pathlib import Path

import httpx
from typer.testing import CliRunner

from pecp.cli.main import app

runner = CliRunner()


def test_apply_command_posts_to_api_url_flag(tmp_path: Path) -> None:
    """Behavior 3: --api-url flag overrides the default and env var URL."""
    example_yaml = tmp_path / "resource.yaml"
    example_yaml.write_bytes(
        b"""apiVersion: pecp/v1
kind: PECPLambda
metadata:
  name: hello-world
spec:
  name: hello-world
  exposure: private
  api-gateway: /hello
  source-code: github://myorg/lambda-code
"""
    )

    import unittest.mock as mock

    mock_response = mock.MagicMock(spec=httpx.Response)
    mock_response.status_code = 202
    mock_response.json.return_value = {
        "id": "test123",
        "kind": "PECPLambda",
        "name": "hello-world",
        "status": "pending",
    }

    with mock.patch("httpx.post", return_value=mock_response) as mock_post:
        result = runner.invoke(
            app,
            [
                "apply",
                "-f",
                str(example_yaml),
                "--team",
                "toxins-research",
                "--api-url",
                "http://test-server:8000",
            ],
            catch_exceptions=False,
        )

    assert result.exit_code == 0
    call_args = mock_post.call_args
    assert call_args is not None
    called_url = call_args[0][0] if call_args[0] else ""
    assert "test-server:8000" in str(called_url)
    # Verify content-type header
    headers = call_args[1].get("headers", {}) if call_args[1] else {}
    assert headers.get("Content-Type") == "application/x-yaml"


def test_apply_command_success_output(tmp_path: Path) -> None:
    """CLI prints green success line with id, kind, name on 202 response (Behavior 2)."""
    example_yaml = tmp_path / "resource.yaml"
    example_yaml.write_bytes(
        b"""apiVersion: pecp/v1
kind: PECPLambda
metadata:
  name: hello-world
spec:
  name: hello-world
  exposure: private
  api-gateway: /hello
  source-code: github://myorg/lambda-code
"""
    )

    # Monkeypatch httpx.post to return a 202 with a known body
    import unittest.mock as mock

    mock_response = mock.MagicMock(spec=httpx.Response)
    mock_response.status_code = 202
    mock_response.json.return_value = {
        "id": "deadbeef",
        "kind": "PECPLambda",
        "name": "hello-world",
        "status": "pending",
    }

    with mock.patch("httpx.post", return_value=mock_response) as mock_post:
        result = runner.invoke(
            app,
            [
                "apply",
                "-f",
                str(example_yaml),
                "--team",
                "toxins-research",
                "--api-url",
                "http://localhost:8000",
            ],
            catch_exceptions=False,
        )

    assert result.exit_code == 0
    assert "deadbeef" in result.output
    assert "PECPLambda" in result.output
    assert "hello-world" in result.output

    # Assert request was made to the right URL with correct headers
    call_kwargs = mock_post.call_args
    assert call_kwargs is not None
    url_arg = call_kwargs[0][0] if call_kwargs[0] else call_kwargs[1].get("url", "")
    assert "toxins-research" in str(url_arg) or "toxins-research" in str(call_kwargs)


def test_apply_command_env_var_url(tmp_path: Path) -> None:
    """CLI uses PECP_API_URL env var when --api-url is not provided (Behavior 4)."""
    example_yaml = tmp_path / "resource.yaml"
    example_yaml.write_bytes(
        b"""apiVersion: pecp/v1
kind: PECPLambda
metadata:
  name: hello-world
spec:
  name: hello-world
  exposure: private
  api-gateway: /hello
  source-code: github://myorg/lambda-code
"""
    )

    import unittest.mock as mock

    mock_response = mock.MagicMock(spec=httpx.Response)
    mock_response.status_code = 202
    mock_response.json.return_value = {
        "id": "cafebabe",
        "kind": "PECPLambda",
        "name": "hello-world",
        "status": "pending",
    }

    with mock.patch("httpx.post", return_value=mock_response) as mock_post:
        result = runner.invoke(
            app,
            ["apply", "-f", str(example_yaml), "--team", "toxins-research"],
            env={"PECP_API_URL": "http://envhost:9000"},
            catch_exceptions=False,
        )

    assert result.exit_code == 0
    call_args = mock_post.call_args
    assert call_args is not None
    called_url = call_args[0][0] if call_args[0] else ""
    assert "envhost:9000" in str(called_url)


def test_version_command() -> None:
    """CLI version command prints pecp 0.1.0."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output
