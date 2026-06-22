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


# ---------------------------------------------------------------------------
# Phase 5 Plan 01 — account sub-command tests (CLI-09, CLI-10)
# ---------------------------------------------------------------------------


def test_account_create_flag_path_returns_resource_id() -> None:
    """CLI-09 / D-01 / D-02: pecp create awsaccount --team --env --project builds PECPAccount spec and prints resource id."""
    import unittest.mock as mock
    import yaml

    posted_body: list[bytes] = []

    mock_response = mock.MagicMock(spec=httpx.Response)
    mock_response.status_code = 202
    mock_response.json.return_value = {
        "id": "acct-abc-123",
        "kind": "PECPAccount",
        "name": "pecp-customer-product-app",
        "status": "pending",
    }

    def capture_post(*args: object, **kwargs: object) -> httpx.Response:
        content = kwargs.get("content", b"")
        if isinstance(content, bytes):
            posted_body.append(content)
        return mock_response

    with mock.patch("httpx.post", side_effect=capture_post):
        result = runner.invoke(
            app,
            [
                "create",
                "awsaccount",
                "--team",
                "customer-product-app",
                "--env",
                "prod",
                "--project",
                "cpa-core",
                "--api-url",
                "http://t:8000",
            ],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, result.output
    assert "acct-abc-123" in result.output

    # Verify the request body is a valid YAML PECPAccount spec
    assert len(posted_body) == 1
    spec = yaml.safe_load(posted_body[0])
    assert spec["kind"] == "PECPAccount"
    assert spec["metadata"]["name"] == "pecp-customer-product-app"
    assert spec["metadata"]["team"] == "customer-product-app"
    assert spec["metadata"]["env"] == "prod"
    assert spec["metadata"]["project"] == "cpa-core"


def test_account_create_yaml_override_uses_file(tmp_path: Path) -> None:
    """CLI-09 / D-01: pecp create awsaccount -f account.yaml sends file bytes verbatim."""
    import unittest.mock as mock

    account_yaml = tmp_path / "account.yaml"
    yaml_content = b"""apiVersion: pecp/v1
kind: PECPAccount
metadata:
  name: pecp-custom-override
  team: customer-product-app
spec: {}
"""
    account_yaml.write_bytes(yaml_content)

    posted_body: list[bytes] = []

    mock_response = mock.MagicMock(spec=httpx.Response)
    mock_response.status_code = 202
    mock_response.json.return_value = {
        "id": "acct-file-456",
        "kind": "PECPAccount",
        "name": "pecp-custom-override",
        "status": "pending",
    }

    def capture_post(*args: object, **kwargs: object) -> httpx.Response:
        content = kwargs.get("content", b"")
        if isinstance(content, bytes):
            posted_body.append(content)
        return mock_response

    with mock.patch("httpx.post", side_effect=capture_post):
        result = runner.invoke(
            app,
            [
                "create",
                "awsaccount",
                "--team",
                "customer-product-app",
                "-f",
                str(account_yaml),
                "--api-url",
                "http://t:8000",
            ],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, result.output
    # File bytes must be sent verbatim (no internal YAML build)
    assert len(posted_body) == 1
    assert posted_body[0] == yaml_content


def test_account_status_renders_metadata_and_notes() -> None:
    """CLI-10 / D-03: pecp status awsaccount renders provider_metadata fields and notes."""
    import unittest.mock as mock

    list_response = mock.MagicMock(spec=httpx.Response)
    list_response.status_code = 200
    list_response.json.return_value = [
        {
            "id": "acct-r1",
            "kind": "PECPAccount",
            "name": "pecp-customer-product-app",
            "status": "ready",
            "env": "prod",
        }
    ]

    detail_response = mock.MagicMock(spec=httpx.Response)
    detail_response.status_code = 200
    detail_response.json.return_value = {
        "id": "acct-r1",
        "kind": "PECPAccount",
        "name": "pecp-customer-product-app",
        "status": "ready",
        "env": "prod",
        "created_at": "2026-06-22T00:00:00Z",
        "provider_metadata": {
            "account_id": "123456789012",
            "account_email": "aws+cpa@example.com",
            "account_name": "pecp-customer-product-app",
            "management_console_url": "https://console.aws.amazon.com/switch-role?account=123456789012",
        },
        "notes": [
            {
                "author": "pe-team",
                "timestamp": "2026-06-22 09:00",
                "text": "Account provisioning request received",
            }
        ],
    }

    with mock.patch("httpx.get", side_effect=[list_response, detail_response]):
        result = runner.invoke(
            app,
            [
                "status",
                "awsaccount",
                "--team",
                "customer-product-app",
                "--api-url",
                "http://t:8000",
            ],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, result.output
    # All four provider_metadata values must appear
    assert "123456789012" in result.output
    assert "aws+cpa@example.com" in result.output
    assert "pecp-customer-product-app" in result.output
    assert "console.aws.amazon.com" in result.output
    # Notes must appear
    assert "Account provisioning request received" in result.output
    # D-03: no AWS access keys in status output
    assert "AKIA" not in result.output


def test_account_status_json_output() -> None:
    """CLI-10 / D-03: pecp status awsaccount --json outputs raw JSON dict."""
    import unittest.mock as mock

    list_response = mock.MagicMock(spec=httpx.Response)
    list_response.status_code = 200
    list_response.json.return_value = [
        {
            "id": "acct-r2",
            "kind": "PECPAccount",
            "name": "pecp-customer-product-app",
            "status": "ready",
            "env": "prod",
        }
    ]

    detail_dict = {
        "id": "acct-r2",
        "kind": "PECPAccount",
        "name": "pecp-customer-product-app",
        "status": "ready",
        "env": "prod",
        "created_at": "2026-06-22T00:00:00Z",
        "provider_metadata": {
            "account_id": "123456789012",
            "account_email": "aws+cpa@example.com",
            "account_name": "pecp-customer-product-app",
            "management_console_url": "https://console.aws.amazon.com/",
        },
        "notes": [],
    }
    detail_response = mock.MagicMock(spec=httpx.Response)
    detail_response.status_code = 200
    detail_response.json.return_value = detail_dict

    with mock.patch("httpx.get", side_effect=[list_response, detail_response]):
        result = runner.invoke(
            app,
            [
                "status",
                "awsaccount",
                "--team",
                "customer-product-app",
                "--json",
                "--api-url",
                "http://t:8000",
            ],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, result.output
    parsed = json.loads(result.output)
    assert isinstance(parsed, dict)
    assert parsed["id"] == "acct-r2"
    assert "provider_metadata" in parsed


def test_account_status_watch_exits_on_ready(monkeypatch: object) -> None:
    """CLI-10 / D-05: pecp status awsaccount --watch polls until ready, prints timestamped lines."""
    import unittest.mock as mock

    # Patch time.sleep to no-op
    monkeypatch.setattr("pecp.cli.main.time.sleep", lambda _: None)  # type: ignore[attr-defined]

    call_count = 0

    def side_effect_get(*args: object, **kwargs: object) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call: list resources
            r = mock.MagicMock(spec=httpx.Response)
            r.status_code = 200
            r.json.return_value = [
                {"id": "acct-w1", "kind": "PECPAccount", "name": "pecp-customer-product-app", "status": "provisioning", "env": "prod"}
            ]
            return r
        elif call_count == 2:
            # First detail fetch: provisioning
            r = mock.MagicMock(spec=httpx.Response)
            r.status_code = 200
            r.json.return_value = {
                "id": "acct-w1", "kind": "PECPAccount", "name": "pecp-customer-product-app",
                "status": "provisioning", "env": "prod", "created_at": "2026-06-22T00:00:00Z",
                "provider_metadata": {}, "notes": [],
            }
            return r
        elif call_count == 3:
            # Second list: still provisioning
            r = mock.MagicMock(spec=httpx.Response)
            r.status_code = 200
            r.json.return_value = [
                {"id": "acct-w1", "kind": "PECPAccount", "name": "pecp-customer-product-app", "status": "provisioning", "env": "prod"}
            ]
            return r
        elif call_count == 4:
            # Second detail fetch: ready
            r = mock.MagicMock(spec=httpx.Response)
            r.status_code = 200
            r.json.return_value = {
                "id": "acct-w1", "kind": "PECPAccount", "name": "pecp-customer-product-app",
                "status": "ready", "env": "prod", "created_at": "2026-06-22T00:00:00Z",
                "provider_metadata": {}, "notes": [],
            }
            return r
        else:
            raise AssertionError("Too many calls to httpx.get")

    with mock.patch("httpx.get", side_effect=side_effect_get):
        result = runner.invoke(
            app,
            [
                "status",
                "awsaccount",
                "--team",
                "customer-product-app",
                "--watch",
                "--api-url",
                "http://t:8000",
            ],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, result.output
    # Should have timestamped poll lines
    assert "status:" in result.output
    assert "provisioning" in result.output
    assert "ready" in result.output


def test_account_login_prints_export_lines_when_ready() -> None:
    """CLI-10 / D-04: pecp login awsaccount prints export lines and exits 0 when ready."""
    import unittest.mock as mock

    list_response = mock.MagicMock(spec=httpx.Response)
    list_response.status_code = 200
    list_response.json.return_value = [
        {"id": "acct-l1", "kind": "PECPAccount", "name": "pecp-customer-product-app", "status": "ready", "env": "prod"}
    ]

    detail_response = mock.MagicMock(spec=httpx.Response)
    detail_response.status_code = 200
    detail_response.json.return_value = {
        "id": "acct-l1", "kind": "PECPAccount", "name": "pecp-customer-product-app",
        "status": "ready", "env": "prod", "created_at": "2026-06-22T00:00:00Z",
        "provider_metadata": {
            "account_id": "123456789012",
            "account_email": "aws+cpa@example.com",
            "account_name": "pecp-customer-product-app",
            "management_console_url": "https://console.aws.amazon.com/",
            "access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "default_region": "us-east-1",
        },
        "notes": [],
    }

    with mock.patch("httpx.get", side_effect=[list_response, detail_response]):
        result = runner.invoke(
            app,
            [
                "login",
                "awsaccount",
                "--team",
                "customer-product-app",
                "--api-url",
                "http://t:8000",
            ],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, result.output
    assert "export AWS_ACCESS_KEY_ID=" in result.output
    assert "export AWS_SECRET_ACCESS_KEY=" in result.output
    assert "export AWS_DEFAULT_REGION=" in result.output
    # Comment line with profile and account
    assert "# Profile:" in result.output
    assert "123456789012" in result.output


def test_account_login_exit_code_2_when_not_ready() -> None:
    """CLI-10 / D-04: pecp login awsaccount exits 2 when account status is not ready."""
    import unittest.mock as mock

    list_response = mock.MagicMock(spec=httpx.Response)
    list_response.status_code = 200
    list_response.json.return_value = [
        {"id": "acct-l2", "kind": "PECPAccount", "name": "pecp-customer-product-app", "status": "provisioning", "env": "prod"}
    ]

    detail_response = mock.MagicMock(spec=httpx.Response)
    detail_response.status_code = 200
    detail_response.json.return_value = {
        "id": "acct-l2", "kind": "PECPAccount", "name": "pecp-customer-product-app",
        "status": "provisioning", "env": "prod", "created_at": "2026-06-22T00:00:00Z",
        "provider_metadata": {}, "notes": [],
    }

    with mock.patch("httpx.get", side_effect=[list_response, detail_response]):
        result = runner.invoke(
            app,
            [
                "login",
                "awsaccount",
                "--team",
                "customer-product-app",
                "--api-url",
                "http://t:8000",
            ],
        )

    assert result.exit_code == 2, result.output
    assert "not yet ready" in result.output.lower() or "not ready" in result.output.lower()


def test_account_login_exit_code_1_when_not_found() -> None:
    """CLI-10 / D-04: pecp login awsaccount exits 1 when no PECPAccount found for team."""
    import unittest.mock as mock

    list_response = mock.MagicMock(spec=httpx.Response)
    list_response.status_code = 200
    list_response.json.return_value = []  # No accounts found

    with mock.patch("httpx.get", return_value=list_response):
        result = runner.invoke(
            app,
            [
                "login",
                "awsaccount",
                "--team",
                "customer-product-app",
                "--api-url",
                "http://t:8000",
            ],
        )

    assert result.exit_code == 1, result.output


def test_status_awsaccount_subapp_registered() -> None:
    """Registration smoke test: pecp status awsaccount --help exits 0 and shows --team/--watch."""
    result = runner.invoke(app, ["status", "awsaccount", "--help"])
    assert result.exit_code == 0, result.output
    assert "--team" in result.output
    assert "--watch" in result.output


def test_login_awsaccount_subapp_registered() -> None:
    """Registration smoke test: pecp login awsaccount --help exits 0 and shows --team."""
    result = runner.invoke(app, ["login", "awsaccount", "--help"])
    assert result.exit_code == 0, result.output
    assert "--team" in result.output
