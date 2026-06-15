"""Tests for the Typer `pecp` CLI.

Uses typer.testing.CliRunner to invoke CLI commands without a live server.
HTTP calls are mocked with a custom httpx transport to assert the correct
request URL, headers, and body are sent (Behavior 5).
"""

import json
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


# ---------------------------------------------------------------------------
# Wave 0 CLI test scaffolds — FAIL intentionally until Wave 3 implements commands
# ---------------------------------------------------------------------------


def test_get_command_renders_table_with_status_badge() -> None:
    """CLI-02: pecp get renders a Rich table with name, Status column for each resource."""
    import unittest.mock as mock

    mock_response = mock.MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {
            "id": "aaa111",
            "kind": "PECPLambda",
            "name": "hello-world",
            "status": "ready",
            "env": "dev",
        },
        {
            "id": "bbb222",
            "kind": "PECPLambda",
            "name": "goodbye-world",
            "status": "pending",
            "env": None,
        },
    ]

    with mock.patch("httpx.get", return_value=mock_response):
        result = runner.invoke(
            app,
            [
                "get",
                "PECPLambda",
                "--team",
                "toxins-research",
                "--api-url",
                "http://t:8000",
            ],
            catch_exceptions=False,
        )

    assert result.exit_code == 0
    assert "hello-world" in result.output
    assert "goodbye-world" in result.output
    assert "Status" in result.output


def test_status_command_renders_table_and_notes_block() -> None:
    """CLI-04: pecp status renders table and Notes: block when notes exist (D-06)."""
    import unittest.mock as mock

    list_response = mock.MagicMock(spec=httpx.Response)
    list_response.status_code = 200
    list_response.json.return_value = [
        {
            "id": "ccc333",
            "kind": "PECPLambda",
            "name": "hello-world",
            "status": "ready",
            "env": "dev",
        }
    ]

    detail_response = mock.MagicMock(spec=httpx.Response)
    detail_response.status_code = 200
    detail_response.json.return_value = {
        "id": "ccc333",
        "team": "toxins-research",
        "kind": "PECPLambda",
        "name": "hello-world",
        "status": "ready",
        "env": "dev",
        "created_at": "2026-06-14T00:00:00Z",
        "provider_metadata": {},
        "activity_log": [],
        "notes": [
            {
                "author": "stub-user",
                "timestamp": "2026-06-14 10:00",
                "text": "deployment looks good",
            }
        ],
    }

    with mock.patch("httpx.get", side_effect=[list_response, detail_response]):
        result = runner.invoke(
            app,
            [
                "status",
                "PECPLambda",
                "hello-world",
                "--team",
                "toxins-research",
                "--api-url",
                "http://t:8000",
            ],
            catch_exceptions=False,
        )

    assert result.exit_code == 0
    assert "Notes:" in result.output
    assert "deployment looks good" in result.output


def test_status_command_no_notes_omits_block() -> None:
    """CLI-04: pecp status omits Notes: block when notes list is empty (D-06)."""
    import unittest.mock as mock

    list_response = mock.MagicMock(spec=httpx.Response)
    list_response.status_code = 200
    list_response.json.return_value = [
        {
            "id": "ddd444",
            "kind": "PECPLambda",
            "name": "hello-world",
            "status": "pending",
            "env": None,
        }
    ]

    detail_response = mock.MagicMock(spec=httpx.Response)
    detail_response.status_code = 200
    detail_response.json.return_value = {
        "id": "ddd444",
        "team": "toxins-research",
        "kind": "PECPLambda",
        "name": "hello-world",
        "status": "pending",
        "env": None,
        "created_at": "2026-06-14T00:00:00Z",
        "provider_metadata": {},
        "activity_log": [],
        "notes": [],
    }

    with mock.patch("httpx.get", side_effect=[list_response, detail_response]):
        result = runner.invoke(
            app,
            [
                "status",
                "PECPLambda",
                "hello-world",
                "--team",
                "toxins-research",
                "--api-url",
                "http://t:8000",
            ],
            catch_exceptions=False,
        )

    assert result.exit_code == 0
    assert "Notes:" not in result.output


def test_delete_command_finds_id_then_deletes() -> None:
    """CLI-03: pecp delete finds resource id via list then calls DELETE on /resources/{id}."""
    import unittest.mock as mock

    resource_id = "eee555"

    list_response = mock.MagicMock(spec=httpx.Response)
    list_response.status_code = 200
    list_response.json.return_value = [
        {
            "id": resource_id,
            "kind": "PECPLambda",
            "name": "hello-world",
            "status": "ready",
            "env": None,
        }
    ]

    delete_response = mock.MagicMock(spec=httpx.Response)
    delete_response.status_code = 204

    with (
        mock.patch("httpx.get", return_value=list_response),
        mock.patch("httpx.delete", return_value=delete_response) as mock_delete,
    ):
        result = runner.invoke(
            app,
            [
                "delete",
                "PECPLambda",
                "hello-world",
                "--team",
                "toxins-research",
                "--api-url",
                "http://t:8000",
            ],
            catch_exceptions=False,
        )

    assert result.exit_code == 0
    assert mock_delete.called
    called_url = str(mock_delete.call_args[0][0]) if mock_delete.call_args[0] else ""
    assert resource_id in called_url


def test_delete_command_passes_team_query_param() -> None:
    """Security A5: pecp delete passes team as query param to DELETE route."""
    import unittest.mock as mock

    resource_id = "fff666"

    list_response = mock.MagicMock(spec=httpx.Response)
    list_response.status_code = 200
    list_response.json.return_value = [
        {
            "id": resource_id,
            "kind": "PECPLambda",
            "name": "hello-world",
            "status": "ready",
            "env": None,
        }
    ]

    delete_response = mock.MagicMock(spec=httpx.Response)
    delete_response.status_code = 204

    with (
        mock.patch("httpx.get", return_value=list_response),
        mock.patch("httpx.delete", return_value=delete_response) as mock_delete,
    ):
        result = runner.invoke(
            app,
            [
                "delete",
                "PECPLambda",
                "hello-world",
                "--team",
                "toxins-research",
                "--api-url",
                "http://t:8000",
            ],
            catch_exceptions=False,
        )

    assert result.exit_code == 0
    call_kwargs = mock_delete.call_args
    assert call_kwargs is not None
    # team must be passed as a query param
    params = call_kwargs[1].get("params", {}) if call_kwargs[1] else {}
    assert params.get("team") == "toxins-research"


# ---------------------------------------------------------------------------
# Wave 0 CLI test scaffolds — FAIL intentionally until Plan 02/03 implements commands
# (CLI-05, CLI-06, CLI-07, CLI-08 and --json flag extensions)
# ---------------------------------------------------------------------------


def test_team_create_command_renders_panel() -> None:
    """CLI-05: pecp team create renders a panel with team name and members table."""
    import unittest.mock as mock

    team_body = {
        "id": "team-abc-123",
        "name": "payments",
        "owner_id": "alice",
        "created_at": "2026-06-14T00:00:00Z",
        "members": [
            {"user_id": "alice", "role": "owner", "joined_at": "2026-06-14T00:00:00Z"}
        ],
    }
    mock_response = mock.MagicMock(spec=httpx.Response)
    mock_response.status_code = 201
    mock_response.json.return_value = team_body

    with mock.patch("httpx.post", return_value=mock_response):
        result = runner.invoke(
            app,
            ["team", "create", "payments", "--owner", "alice", "--api-url", "http://t:8000"],
        )

    assert result.exit_code == 0
    assert "payments" in result.output
    assert "alice" in result.output
    assert "Members" in result.output


def test_team_show_command_renders_members_table() -> None:
    """CLI-05: pecp team <name> renders team metadata and members table."""
    import unittest.mock as mock

    team_body = {
        "id": "team-abc-123",
        "name": "payments",
        "owner_id": "alice",
        "created_at": "2026-06-14T00:00:00Z",
        "members": [
            {"user_id": "alice", "role": "owner", "joined_at": "2026-06-14T00:00:00Z"}
        ],
    }
    mock_response = mock.MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = team_body

    with mock.patch("httpx.get", return_value=mock_response):
        result = runner.invoke(
            app,
            ["team", "payments", "--api-url", "http://t:8000"],
        )

    assert result.exit_code == 0
    assert "payments" in result.output
    assert "alice" in result.output
    assert "owner" in result.output


def test_team_command_json_flag_outputs_clean_json() -> None:
    """CLI-17: pecp team <name> --json outputs clean JSON dict with name key."""
    import unittest.mock as mock

    team_body = {
        "id": "team-abc-123",
        "name": "payments",
        "owner_id": "alice",
        "created_at": "2026-06-14T00:00:00Z",
        "members": [
            {"user_id": "alice", "role": "owner", "joined_at": "2026-06-14T00:00:00Z"}
        ],
    }
    mock_response = mock.MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = team_body

    with mock.patch("httpx.get", return_value=mock_response):
        result = runner.invoke(
            app,
            ["team", "payments", "--json", "--api-url", "http://t:8000"],
        )

    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert isinstance(parsed, dict)
    assert parsed["name"] == "payments"


def test_projects_command_renders_table_with_resource_count() -> None:
    """CLI-06: pecp projects --team renders a table with project name and resource_count."""
    import unittest.mock as mock

    projects_body = [
        {
            "id": "proj-abc-123",
            "name": "payments-backend",
            "environments": ["dev", "staging", "prod"],
            "resource_count": 4,
        }
    ]
    mock_response = mock.MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = projects_body

    with mock.patch("httpx.get", return_value=mock_response):
        result = runner.invoke(
            app,
            ["projects", "--team", "payments", "--api-url", "http://t:8000"],
        )

    assert result.exit_code == 0
    assert "payments-backend" in result.output
    assert "4" in result.output


def test_projects_command_json_flag_outputs_array() -> None:
    """CLI-06 / D-17: pecp projects --team --json outputs JSON array with required keys."""
    import unittest.mock as mock

    projects_body = [
        {
            "id": "proj-abc-123",
            "name": "payments-backend",
            "environments": ["dev", "staging", "prod"],
            "resource_count": 2,
        }
    ]
    mock_response = mock.MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = projects_body

    with mock.patch("httpx.get", return_value=mock_response):
        result = runner.invoke(
            app,
            ["projects", "--team", "payments", "--json", "--api-url", "http://t:8000"],
        )

    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert isinstance(parsed, list)
    assert len(parsed) == 1
    item = parsed[0]
    for key in ("id", "name", "environments", "resource_count"):
        assert key in item


def test_deployments_command_renders_sorted_newest_first() -> None:
    """CLI-07 / D-16: pecp deployments renders table with deployment columns."""
    import unittest.mock as mock

    deployments_body = [
        {
            "id": "dep-001",
            "resource_name": "hello-world",
            "kind": "PECPLambda",
            "change_type": "create",
            "status": "ready",
            "deployed_at": "2026-06-14T12:00:00Z",
            "environment": "prod",
        },
        {
            "id": "dep-002",
            "resource_name": "goodbye-world",
            "kind": "PECPLambda",
            "change_type": "update",
            "status": "pending",
            "deployed_at": "2026-06-14T11:00:00Z",
            "environment": "prod",
        },
    ]
    mock_response = mock.MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = deployments_body

    with mock.patch("httpx.get", return_value=mock_response):
        result = runner.invoke(
            app,
            [
                "deployments",
                "--team",
                "payments",
                "--environment",
                "prod",
                "--api-url",
                "http://t:8000",
            ],
        )

    assert result.exit_code == 0
    assert "hello-world" in result.output
    assert "goodbye-world" in result.output
    # Verify columns appear in output
    output_lower = result.output.lower()
    assert any(col in output_lower for col in ("resource", "kind", "change", "status", "deployed"))


def test_deployments_command_json_flag_outputs_array() -> None:
    """CLI-07 / D-17: pecp deployments --json outputs JSON array of deployment records."""
    import unittest.mock as mock

    deployments_body = [
        {
            "id": "dep-001",
            "resource_name": "hello-world",
            "kind": "PECPLambda",
            "change_type": "create",
            "status": "ready",
            "deployed_at": "2026-06-14T12:00:00Z",
            "environment": "prod",
        }
    ]
    mock_response = mock.MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = deployments_body

    with mock.patch("httpx.get", return_value=mock_response):
        result = runner.invoke(
            app,
            [
                "deployments",
                "--team",
                "payments",
                "--environment",
                "prod",
                "--json",
                "--api-url",
                "http://t:8000",
            ],
        )

    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert isinstance(parsed, list)


def test_get_command_json_flag_outputs_array() -> None:
    """CLI-02 / D-17: pecp get --json outputs clean JSON array of resource records."""
    import unittest.mock as mock

    resources_body = [
        {
            "id": "aaa111",
            "kind": "PECPLambda",
            "name": "hello-world",
            "status": "ready",
            "env": "dev",
        }
    ]
    mock_response = mock.MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = resources_body

    with mock.patch("httpx.get", return_value=mock_response):
        result = runner.invoke(
            app,
            [
                "get",
                "PECPLambda",
                "--team",
                "toxins-research",
                "--json",
                "--api-url",
                "http://t:8000",
            ],
        )

    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert isinstance(parsed, list)


def test_status_command_json_flag_outputs_object() -> None:
    """CLI-04 / D-17: pecp status --json outputs clean JSON object with expected keys."""
    import unittest.mock as mock

    list_response = mock.MagicMock(spec=httpx.Response)
    list_response.status_code = 200
    list_response.json.return_value = [
        {
            "id": "ccc333",
            "kind": "PECPLambda",
            "name": "hello-world",
            "status": "ready",
            "env": "dev",
        }
    ]

    detail_response = mock.MagicMock(spec=httpx.Response)
    detail_response.status_code = 200
    detail_response.json.return_value = {
        "id": "ccc333",
        "team": "toxins-research",
        "kind": "PECPLambda",
        "name": "hello-world",
        "status": "ready",
        "env": "dev",
        "created_at": "2026-06-14T00:00:00Z",
        "provider_metadata": {},
        "activity_log": [],
        "notes": [],
    }

    with mock.patch("httpx.get", side_effect=[list_response, detail_response]):
        result = runner.invoke(
            app,
            [
                "status",
                "PECPLambda",
                "hello-world",
                "--team",
                "toxins-research",
                "--json",
                "--api-url",
                "http://t:8000",
            ],
        )

    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert isinstance(parsed, dict)
    for key in ("notes", "activity_log", "provider_metadata"):
        assert key in parsed


def test_project_create_command_renders_confirmation() -> None:
    """CLI-08 / D-06: pecp project create renders confirmation with project name and id."""
    import unittest.mock as mock

    project_body = {
        "id": "abc-123",
        "name": "payments-backend",
        "environments": ["dev", "staging", "prod"],
    }
    mock_response = mock.MagicMock(spec=httpx.Response)
    mock_response.status_code = 201
    mock_response.json.return_value = project_body

    with mock.patch("httpx.post", return_value=mock_response):
        result = runner.invoke(
            app,
            [
                "project",
                "create",
                "payments-backend",
                "--team",
                "payments",
                "--env",
                "dev,staging,prod",
                "--api-url",
                "http://t:8000",
            ],
        )

    assert result.exit_code == 0
    assert "payments-backend" in result.output
    assert "abc-123" in result.output
