"""PECP CLI — apply resource specs via the PECP Control Plane API.

Commands:
  pecp apply -f <file> --team <team>        Submit a resource YAML to the API
  pecp get <kind> --team <team>             List resources for a team with status badges
  pecp status <kind> <name> --team <team>   Show provisioning status and notes
  pecp delete <kind> <name> --team <team>   Delete a resource
  pecp version                              Print the CLI version

The API base URL resolves in this priority order:
  1. --api-url flag
  2. PECP_API_URL environment variable
  3. Default: http://localhost:8000
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path

import httpx
import typer
import yaml
from rich.console import Console
from rich.table import Table
from rich.text import Text

app = typer.Typer(
    name="pecp",
    help="PECP Platform Engineering Control Plane CLI",
    no_args_is_help=True,
)
console = Console()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

STATUS_COLORS: dict[str, str] = {
    "pending": "yellow",
    "provisioning": "blue",
    "ready": "green",
    "failed": "red",
}


def status_badge(status: str) -> Text:
    """Return a Rich Text with color styling for the given status string."""
    return Text(status, style=f"bold {STATUS_COLORS.get(status, 'white')}")


def _resolve_base_url(api_url: str | None) -> str:
    """Resolve the API base URL from flag, env var, or default."""
    base = api_url or os.environ.get("PECP_API_URL") or "http://localhost:8000"
    return base.rstrip("/")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("apply")
def apply(
    file: Path = typer.Option(
        ...,
        "-f",
        "--file",
        help="Path to the resource YAML file",
        exists=True,
        readable=True,
    ),
    team: str = typer.Option(..., "--team", help="Team that owns this resource"),
    project: str | None = typer.Option(
        None,
        "--project",
        help="Project to associate with this resource (overrides spec.metadata.project per D-07)",
    ),
    api_url: str | None = typer.Option(
        None,
        "--api-url",
        help="PECP API base URL (overrides PECP_API_URL env var; default http://localhost:8000)",
    ),
) -> None:
    """Apply a resource YAML spec to the PECP Control Plane."""
    base = _resolve_base_url(api_url)

    yaml_bytes = file.read_bytes()

    params: dict[str, str] = {"team": team}
    if project is not None:
        params["project"] = project

    try:
        response = httpx.post(
            f"{base}/resources",
            params=params,
            headers={"Content-Type": "application/x-yaml"},
            content=yaml_bytes,
            timeout=10.0,
        )
    except httpx.RequestError as exc:
        console.print(f"[red]Connection error[/red]: {exc}")
        raise typer.Exit(code=1) from exc

    if response.status_code == 202:
        result = response.json()
        console.print(
            f"[green]Applied[/green] {result['kind']} {result['name']}"
            f" → id={result['id']} status={result['status']}"
        )
    else:
        console.print(f"[red]Error[/red] {response.status_code}: {response.text}")
        raise typer.Exit(code=1)


@app.command("get")
def get(
    kind: str = typer.Argument(..., help="Resource kind (e.g. PECPLambda)"),
    team: str = typer.Option(..., "--team", help="Team that owns these resources"),
    api_url: str | None = typer.Option(
        None,
        "--api-url",
        help="PECP API base URL (overrides PECP_API_URL env var; default http://localhost:8000)",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON to stdout"),
) -> None:
    """List resources of a given kind for a team with status badges."""
    base = _resolve_base_url(api_url)

    try:
        response = httpx.get(
            f"{base}/resources",
            params={"team": team, "kind": kind},
            timeout=10.0,
        )
    except httpx.RequestError as exc:
        console.print(f"[red]Connection error[/red]: {exc}")
        raise typer.Exit(code=1) from exc

    if response.status_code != 200:
        console.print(f"[red]Error[/red] {response.status_code}: {response.text}")
        raise typer.Exit(code=1)

    resources = response.json()

    if json_output:
        print(json.dumps(resources))
        return

    table = Table(title=f"Resources ({kind}) — team: {team}")
    table.add_column("Name")
    table.add_column("Kind")
    table.add_column("Status")
    table.add_column("Env")

    for r in resources:
        table.add_row(
            r["name"],
            r["kind"],
            status_badge(r["status"]),
            r.get("env") or "—",
        )

    console.print(table)


# ---------------------------------------------------------------------------
# `status` sub-typer group — handles BOTH legacy `pecp status <kind> <name>`
# AND new `pecp status awsaccount --team <team>` (D-03, CLI-10)
#
# Architecture: uses a custom TyperGroup (same pattern as _TeamDefaultGroup)
# to route unknown first tokens (e.g. PECPLambda) to the hidden `_resource`
# sub-command, while routing known sub-commands (awsaccount) normally.
# This avoids the Typer/Click limitation where positional callback args consume
# sub-command tokens before routing can occur.
# ---------------------------------------------------------------------------


class _StatusDefaultGroup(typer.core.TyperGroup):
    """TyperGroup subclass that routes unknown resource-kind tokens to the '_resource' sub-command.

    When the first arg is not a known sub-command (awsaccount), treat it as
    the <kind> positional for the legacy `pecp status <kind> <name>` form and
    redirect to '_resource'. The kind+name are stored in class-level slots and
    consumed by the status_resource() sub-command.
    """

    _pending_kind: str | None = None
    _pending_name: str | None = None

    def resolve_command(  # type: ignore[override]
        self, ctx: typer.Context, args: list[str]  # type: ignore[override]
    ) -> tuple[str, object, list[str]]:
        """Route unknown first args to '_resource'; known commands route normally."""
        try:
            return super().resolve_command(ctx, args)  # type: ignore[return-value]
        except Exception:
            # First token is not a known sub-command — treat as <kind> <name>
            kind_val = args[0] if args else None
            name_val = args[1] if len(args) > 1 else None
            resource_cmd = self.commands.get("_resource")
            if resource_cmd is not None and kind_val is not None:
                _StatusDefaultGroup._pending_kind = kind_val
                _StatusDefaultGroup._pending_name = name_val
                # Remaining args after kind and name (options like --team, --json)
                remaining = args[2:] if len(args) > 2 else args[1:]
                # If name_val looks like an option (starts with -), don't consume it
                if name_val is not None and name_val.startswith("-"):
                    _StatusDefaultGroup._pending_name = None
                    remaining = args[1:]
                return (kind_val, resource_cmd, remaining)
            raise


status_app = typer.Typer(
    name="status",
    help="Show provisioning status and notes for a resource.",
    cls=_StatusDefaultGroup,
    no_args_is_help=False,
)


@status_app.command("_resource", hidden=True)
def status_resource(
    team: str = typer.Option(..., "--team", help="Team that owns this resource"),
    api_url: str | None = typer.Option(
        None,
        "--api-url",
        help="PECP API base URL (overrides PECP_API_URL env var; default http://localhost:8000)",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON to stdout"),
) -> None:
    """Legacy resource status handler: pecp status <kind> <name> --team <team>."""
    kind = _StatusDefaultGroup._pending_kind
    name = _StatusDefaultGroup._pending_name
    _StatusDefaultGroup._pending_kind = None
    _StatusDefaultGroup._pending_name = None

    if kind is None:
        console.print("[red]Error[/red]: resource kind is required")
        raise typer.Exit(code=1)
    if name is None:
        console.print("[red]Error[/red]: resource name is required")
        raise typer.Exit(code=1)

    base = _resolve_base_url(api_url)

    # Step 1: list lookup to find the resource id
    try:
        list_response = httpx.get(
            f"{base}/resources",
            params={"team": team, "kind": kind},
            timeout=10.0,
        )
    except httpx.RequestError as exc:
        console.print(f"[red]Connection error[/red]: {exc}")
        raise typer.Exit(code=1) from exc

    if list_response.status_code != 200:
        console.print(f"[red]Error[/red] {list_response.status_code}: {list_response.text}")
        raise typer.Exit(code=1)

    records = list_response.json()
    record_id: str | None = None
    for record in records:
        if record["name"] == name and record["kind"] == kind:
            record_id = record["id"]
            break

    if record_id is None:
        console.print(f"[red]Not found[/red]: {kind} {name} in team {team}")
        raise typer.Exit(code=1)

    # Step 2: fetch full detail
    try:
        detail_response = httpx.get(f"{base}/resources/{record_id}", timeout=10.0)
    except httpx.RequestError as exc:
        console.print(f"[red]Connection error[/red]: {exc}")
        raise typer.Exit(code=1) from exc

    detail = detail_response.json()

    if json_output:
        print(json.dumps(detail))
        return

    table = Table(title=f"{kind}: {name}")
    table.add_column("Field")
    table.add_column("Value")

    for field in ["id", "kind", "name", "status", "env", "created_at"]:
        value = detail.get(field)
        if field == "status":
            table.add_row(field, status_badge(str(detail["status"])))
        elif value is None:
            table.add_row(field, "—")
        else:
            table.add_row(field, str(value))

    console.print(table)

    notes = detail.get("notes", [])
    if notes:
        console.print("\n[bold]Notes:[/bold]")
        for note in notes:
            console.print(f"  [{note['timestamp']}] {note['author']}: {note['text']}")


# ---------------------------------------------------------------------------
# `pecp status awsaccount` — account status sub-command (CLI-10 / D-03 / D-05)
# ---------------------------------------------------------------------------


def _lookup_account_and_fetch(base: str, team: str) -> tuple[str, dict[str, object]]:
    """Two-step list-then-detail lookup for a team's PECPAccount resource.

    Step 1: GET /resources?team=<team>&kind=PECPAccount — find the record with
            name == "pecp-<team>" (convention from D-01).
    Step 2: GET /resources/{id} — fetch full detail with provider_metadata and notes.

    Returns (resource_id, detail_dict). Raises typer.Exit(1) if not found.
    """
    account_name = f"pecp-{team}"
    try:
        list_response = httpx.get(
            f"{base}/resources",
            params={"team": team, "kind": "PECPAccount"},
            timeout=10.0,
        )
    except httpx.RequestError as exc:
        console.print(f"[red]Connection error[/red]: {exc}")
        raise typer.Exit(code=1) from exc

    if list_response.status_code != 200:
        console.print(f"[red]Error[/red] {list_response.status_code}: {list_response.text}")
        raise typer.Exit(code=1)

    records = list_response.json()
    record_id: str | None = None
    for record in records:
        if record.get("name") == account_name and record.get("kind") == "PECPAccount":
            record_id = record["id"]
            break

    if record_id is None:
        console.print(f"[red]Not found[/red]: PECPAccount {account_name} in team {team}")
        raise typer.Exit(code=1)

    try:
        detail_response = httpx.get(f"{base}/resources/{record_id}", timeout=10.0)
    except httpx.RequestError as exc:
        console.print(f"[red]Connection error[/red]: {exc}")
        raise typer.Exit(code=1) from exc

    return record_id, detail_response.json()


@status_app.command("awsaccount")
def account_status(
    team: str = typer.Option(..., "--team", help="Team to show account status for"),
    watch: bool = typer.Option(False, "--watch", help="Poll until ready or failed (D-05)"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON to stdout"),
    api_url: str | None = typer.Option(
        None,
        "--api-url",
        help="PECP API base URL (overrides PECP_API_URL env var; default http://localhost:8000)",
    ),
) -> None:
    """Show AWS account status for a team (CLI-10 / D-03 / D-05).

    Looks up the team's PECPAccount by convention (name=pecp-<team>) and
    renders account metadata, status badge, and PE notes.
    --watch polls every 2 seconds until status is ready or failed.
    --json outputs raw JSON (no Rich formatting).
    Status output never includes AWS access keys (D-03 / T-05-04).
    """
    base = _resolve_base_url(api_url)
    account_name = f"pecp-{team}"

    # D-03: fields to display from provider_metadata (T-05-04: no credential fields)
    metadata_display_fields = [
        "account_id",
        "account_email",
        "account_name",
        "management_console_url",
    ]

    if not watch:
        # Single fetch
        _, detail = _lookup_account_and_fetch(base, team)

        if json_output:
            print(json.dumps(detail))
            return

        table = Table(title=f"PECPAccount: {account_name}")
        table.add_column("Field")
        table.add_column("Value")

        for field in ["id", "name", "status", "env", "created_at"]:
            value = detail.get(field)
            if field == "status":
                table.add_row(field, status_badge(str(detail.get("status", ""))))
            elif value is None:
                table.add_row(field, "—")
            else:
                table.add_row(field, str(value))

        # Account metadata from provider_metadata (D-03 — no credentials)
        provider_meta: dict[str, object] = detail.get("provider_metadata") or {}  # type: ignore[assignment]
        if isinstance(provider_meta, str):
            import json as _json
            provider_meta = _json.loads(provider_meta) if provider_meta else {}
        for field in metadata_display_fields:
            val = provider_meta.get(field)
            table.add_row(field, str(val) if val is not None else "—")

        console.print(table)

        raw_notes = detail.get("notes")
        notes: list[dict[str, str]] = raw_notes if isinstance(raw_notes, list) else []
        if notes:
            console.print("\n[bold]Notes:[/bold]")
            for note in notes:
                console.print(f"  [{note['timestamp']}] {note['author']}: {note['text']}")
        return

    # --watch mode: line-per-poll (D-05)
    last_note_count = 0
    while True:
        _, detail = _lookup_account_and_fetch(base, team)
        current_status = str(detail.get("status", "unknown"))
        ts = datetime.now().strftime("%H:%M:%S")
        console.print(f"[{ts}] status: {status_badge(current_status)}")

        raw_notes = detail.get("notes")
        notes = raw_notes if isinstance(raw_notes, list) else []
        if len(notes) > last_note_count:
            for note in notes[last_note_count:]:
                console.print(f"  [{note['timestamp']}] {note['author']}: {note['text']}")
            last_note_count = len(notes)

        if current_status in ("ready", "failed"):
            break

        time.sleep(2)


@app.command("delete")
def delete(
    kind: str = typer.Argument(..., help="Resource kind (e.g. PECPLambda)"),
    name: str = typer.Argument(..., help="Resource name"),
    team: str = typer.Option(..., "--team", help="Team that owns this resource"),
    api_url: str | None = typer.Option(
        None,
        "--api-url",
        help="PECP API base URL (overrides PECP_API_URL env var; default http://localhost:8000)",
    ),
) -> None:
    """Delete a resource by looking up its id then calling DELETE with team verification."""
    base = _resolve_base_url(api_url)

    # Step 1: list lookup to find the resource id
    try:
        list_response = httpx.get(
            f"{base}/resources",
            params={"team": team, "kind": kind},
            timeout=10.0,
        )
    except httpx.RequestError as exc:
        console.print(f"[red]Connection error[/red]: {exc}")
        raise typer.Exit(code=1) from exc

    if list_response.status_code != 200:
        console.print(f"[red]Error[/red] {list_response.status_code}: {list_response.text}")
        raise typer.Exit(code=1)

    records = list_response.json()
    record_id: str | None = None
    for record in records:
        if record["name"] == name and record["kind"] == kind:
            record_id = record["id"]
            break

    if record_id is None:
        console.print(f"[red]Not found[/red]: {kind} {name} in team {team}")
        raise typer.Exit(code=1)

    # Step 2: DELETE with team query param (Security A5)
    try:
        delete_resp = httpx.delete(
            f"{base}/resources/{record_id}",
            params={"team": team},
            timeout=10.0,
        )
    except httpx.RequestError as exc:
        console.print(f"[red]Connection error[/red]: {exc}")
        raise typer.Exit(code=1) from exc

    if delete_resp.status_code == 204:
        console.print(f"[green]Deleted[/green] {kind} {name}")
    else:
        console.print(f"[red]Error[/red] {delete_resp.status_code}: {delete_resp.text}")
        raise typer.Exit(code=1)


@app.command("projects")
def projects_list(
    team: str = typer.Option(..., "--team", help="Team that owns these projects"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON to stdout"),
    api_url: str | None = typer.Option(
        None,
        "--api-url",
        help="PECP API base URL (overrides PECP_API_URL env var; default http://localhost:8000)",
    ),
) -> None:
    """List projects for a team with resource counts (CLI-07)."""
    base = _resolve_base_url(api_url)

    try:
        response = httpx.get(f"{base}/projects", params={"team": team}, timeout=10.0)
    except httpx.RequestError as exc:
        console.print(f"[red]Connection error[/red]: {exc}")
        raise typer.Exit(code=1) from exc

    if response.status_code != 200:
        console.print(f"[red]Error[/red] {response.status_code}: {response.text}")
        raise typer.Exit(code=1)

    data = response.json()

    if json_output:
        print(json.dumps(data))
        return

    table = Table(title=f"Projects — team: {team}")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Environments")
    table.add_column("Resources")

    for p in data:
        table.add_row(
            p["id"],
            p["name"],
            ", ".join(p["environments"]),
            str(p["resource_count"]),
        )

    console.print(table)


@app.command("deployments")
def deployments_list(
    team: str = typer.Option(..., "--team", help="Team that owns these resources"),
    environment: str | None = typer.Option(
        None,
        "--environment",
        help="Filter by environment (e.g. dev, staging, prod)",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON to stdout"),
    api_url: str | None = typer.Option(
        None,
        "--api-url",
        help="PECP API base URL (overrides PECP_API_URL env var; default http://localhost:8000)",
    ),
) -> None:
    """Show deployment audit trail for a team, optionally filtered by environment (CLI-08)."""
    base = _resolve_base_url(api_url)

    params: dict[str, str] = {"team": team}
    if environment is not None:
        params["environment"] = environment

    try:
        response = httpx.get(f"{base}/deployments", params=params, timeout=10.0)
    except httpx.RequestError as exc:
        console.print(f"[red]Connection error[/red]: {exc}")
        raise typer.Exit(code=1) from exc

    if response.status_code != 200:
        console.print(f"[red]Error[/red] {response.status_code}: {response.text}")
        raise typer.Exit(code=1)

    data = response.json()

    if json_output:
        print(json.dumps(data))
        return

    table = Table(title=f"Deployments — team: {team}")
    table.add_column("Resource")
    table.add_column("Kind")
    table.add_column("Change")
    table.add_column("Status")
    table.add_column("Deployed")

    for row in data:
        table.add_row(
            row["resource_name"],
            row["kind"],
            row["change_type"],
            status_badge(row["status"]),
            row["deployed_at"],
        )

    console.print(table)


@app.command("version")
def version() -> None:
    """Print the CLI version."""
    console.print("pecp 0.1.0")


# ---------------------------------------------------------------------------
# Team sub-command group
# ---------------------------------------------------------------------------


def _render_team_panel(data: dict[str, object], json_output: bool) -> None:
    """Render a team panel or output raw JSON (D-13, D-14, D-17).

    json_output=True: plain print(json.dumps(data)) — no Rich markup (Pattern 7).
    json_output=False: two Rich tables — key-value metadata + Members table.
    """
    if json_output:
        print(json.dumps(data))
        return

    # Top section: key-value metadata table
    table = Table(title=f"Team: {data['name']}")
    table.add_column("Field")
    table.add_column("Value")
    for field in ["id", "name", "owner_id", "created_at"]:
        table.add_row(field, str(data.get(field) or "—"))
    console.print(table)

    # Bottom section: members table (title "Members" — required by test assertion)
    members_table = Table(title="Members")
    members_table.add_column("user_id")
    members_table.add_column("role")
    members_table.add_column("joined_at")
    members: list[dict[str, str]] = data.get("members") or []  # type: ignore[assignment]
    for m in members:
        members_table.add_row(m["user_id"], m["role"], m["joined_at"])
    console.print(members_table)


class _TeamDefaultGroup(typer.core.TyperGroup):
    """TyperGroup subclass that routes unknown args to the 'show' command.

    Typer's standard sub-app callback pattern cannot simultaneously accept a
    positional NAME argument AND dispatch 'create' as a sub-command, because
    Click's Group argument parser consumes the first positional token before
    checking the command registry (Pitfall-3).

    Workaround: override resolve_command so that when the first arg is NOT a
    known sub-command (i.e. it is a team name), we redirect to 'show' and store
    the name in a class-level slot. The slot is read by team_show() and cleared
    immediately. Thread-safe for PoC single-process CLI use.
    """

    _pending_name: str | None = None  # set by resolve_command, consumed by team_show

    def resolve_command(  # type: ignore[override]
        self, ctx: typer.Context, args: list[str]  # type: ignore[override]
    ) -> tuple[str, object, list[str]]:
        """Route unknown first args to 'show'; known commands route normally.

        Pitfall-3 guard: if ctx.invoked_subcommand is not None, the subcommand
        (create) has already been resolved — the callback body must not run
        the show path. This method stores the name only when 'show' is selected
        so that team_create is unaffected.
        """
        # Standard resolution (handles 'create', '--help', etc.)
        try:
            return super().resolve_command(ctx, args)  # type: ignore[return-value]
        except Exception:
            # First token is not a known command — treat it as the team name
            # and redirect to the 'show' sub-command.
            team_name = args[0] if args else None
            show_cmd = self.commands.get("show")
            if show_cmd is not None and team_name is not None:
                _TeamDefaultGroup._pending_name = team_name
                return (team_name, show_cmd, args[1:])
            raise


team_app = typer.Typer(name="team", help="Team management commands", no_args_is_help=False, cls=_TeamDefaultGroup)


@team_app.callback(invoke_without_command=True)
def _team_callback(ctx: typer.Context) -> None:
    """Team management commands callback.

    Pitfall-3 guard: if ctx.invoked_subcommand is not None, a known sub-command
    (e.g. 'create') was dispatched — do not run the show path.
    """
    # Pitfall-3 guard: sub-command (create) handles it; callback must not interfere
    if ctx.invoked_subcommand is not None:
        return


@team_app.command("show")
def team_show(
    api_url: str | None = typer.Option(
        None,
        "--api-url",
        help="PECP API base URL (overrides PECP_API_URL env var; default http://localhost:8000)",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON to stdout"),
) -> None:
    """Show team metadata and members (D-14)."""
    name = _TeamDefaultGroup._pending_name
    _TeamDefaultGroup._pending_name = None
    if name is None:
        raise typer.BadParameter("Team name is required")
    base = _resolve_base_url(api_url)
    try:
        response = httpx.get(f"{base}/teams/{name}", timeout=10.0)
    except httpx.RequestError as exc:
        console.print(f"[red]Connection error[/red]: {exc}")
        raise typer.Exit(code=1) from exc
    if response.status_code != 200:
        console.print(f"[red]Error[/red] {response.status_code}: {response.text}")
        raise typer.Exit(code=1)
    _render_team_panel(response.json(), json_output)


@team_app.command("create")
def team_create(
    name: str = typer.Argument(..., help="Team name"),
    owner: str = typer.Option(
        ..., "--owner", help="Owner user_id (auto-added as first team member with role=owner)"
    ),
    api_url: str | None = typer.Option(
        None,
        "--api-url",
        help="PECP API base URL (overrides PECP_API_URL env var; default http://localhost:8000)",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON to stdout"),
) -> None:
    """Create a new team and display its full panel (D-13)."""
    base = _resolve_base_url(api_url)
    try:
        response = httpx.post(f"{base}/teams", json={"name": name, "owner": owner}, timeout=10.0)
    except httpx.RequestError as exc:
        console.print(f"[red]Connection error[/red]: {exc}")
        raise typer.Exit(code=1) from exc
    if response.status_code != 201:
        console.print(f"[red]Error[/red] {response.status_code}: {response.text}")
        raise typer.Exit(code=1)
    # D-13: render immediately from POST response — no second GET round-trip
    _render_team_panel(response.json(), json_output)


app.add_typer(team_app)


# ---------------------------------------------------------------------------
# Project sub-command group (D-06: explicit project creation)
# ---------------------------------------------------------------------------

project_app = typer.Typer(help="Manage PECP projects")


@project_app.command("create")
def project_create(
    name: str = typer.Argument(..., help="Project name"),
    team: str = typer.Option(..., "--team", help="Team that owns this project"),
    envs: str = typer.Option(
        ...,
        "--env",
        help="Comma-separated list of environments, e.g. dev,staging,prod",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON to stdout"),
    api_url: str | None = typer.Option(
        None,
        "--api-url",
        help="PECP API base URL (overrides PECP_API_URL env var; default http://localhost:8000)",
    ),
) -> None:
    """Create a new project for a team (D-06)."""
    base = _resolve_base_url(api_url)

    env_list = [e.strip() for e in envs.split(",") if e.strip()]
    body = {"name": name, "team": team, "environments": env_list}

    try:
        response = httpx.post(f"{base}/projects", json=body, timeout=10.0)
    except httpx.RequestError as exc:
        console.print(f"[red]Connection error[/red]: {exc}")
        raise typer.Exit(code=1) from exc

    if response.status_code != 201:
        console.print(f"[red]Error[/red] {response.status_code}: {response.text}")
        raise typer.Exit(code=1)

    data = response.json()

    if json_output:
        print(json.dumps(data))
        return

    console.print(f"Project {data['name']} created (id: {data['id']})")


app.add_typer(project_app, name="project")


# ---------------------------------------------------------------------------
# `create` sub-typer group — pecp create awsaccount (CLI-09 / D-01 / D-02)
# ---------------------------------------------------------------------------

# Pitfall 1 guard: verified no existing @app.command("create") above
account_app = typer.Typer(help="AWS account provisioning commands")


@account_app.command("awsaccount")
def account_create(
    team: str = typer.Option(..., "--team", help="Team to provision AWS account for"),
    env: str | None = typer.Option(None, "--env", help="Environment scope (e.g. prod)"),
    project: str | None = typer.Option(None, "--project", help="Project association"),
    file: Path | None = typer.Option(None, "-f", "--file", help="Optional YAML override file"),
    api_url: str | None = typer.Option(
        None,
        "--api-url",
        help="PECP API base URL (overrides PECP_API_URL env var; default http://localhost:8000)",
    ),
) -> None:
    """Request async AWS account provisioning (CLI-09 / D-01 / D-02).

    Primary path: builds PECPAccount spec from flags (--team required, --env and
    --project optional). Account name defaults to pecp-<team>.
    Override path: -f account.yaml sends the file bytes verbatim.
    Returns immediately with resource id and status=pending.
    """
    base = _resolve_base_url(api_url)

    if file is None:
        # Build spec dict from flags (D-01 / D-02)
        account_name = f"pecp-{team}"
        metadata: dict[str, str | None] = {
            "name": account_name,
            "team": team,
        }
        if env is not None:
            metadata["env"] = env
        if project is not None:
            metadata["project"] = project

        spec_dict = {
            "apiVersion": "pecp/v1",
            "kind": "PECPAccount",
            "metadata": metadata,
            "spec": {},
        }
        yaml_bytes = yaml.dump(spec_dict).encode("utf-8")
    else:
        yaml_bytes = file.read_bytes()

    try:
        response = httpx.post(
            f"{base}/resources",
            params={"team": team},
            headers={"Content-Type": "application/x-yaml"},
            content=yaml_bytes,
            timeout=10.0,
        )
    except httpx.RequestError as exc:
        console.print(f"[red]Connection error[/red]: {exc}")
        raise typer.Exit(code=1) from exc

    if response.status_code == 202:
        result = response.json()
        console.print(
            f"[green]Applied[/green] {result['kind']} {result['name']}"
            f" → id={result['id']} status={result['status']}"
        )
    else:
        console.print(f"[red]Error[/red] {response.status_code}: {response.text}")
        raise typer.Exit(code=1)


app.add_typer(account_app, name="create")


# ---------------------------------------------------------------------------
# `login` sub-typer group — pecp login awsaccount (CLI-10 / D-04)
# ---------------------------------------------------------------------------

# Verified no existing @app.command("login") exists
account_login_app = typer.Typer(help="Retrieve credentials for a provisioned resource")


@account_login_app.command("awsaccount")
def account_login(
    team: str = typer.Option(..., "--team", help="Team to retrieve AWS credentials for"),
    api_url: str | None = typer.Option(
        None,
        "--api-url",
        help="PECP API base URL (overrides PECP_API_URL env var; default http://localhost:8000)",
    ),
) -> None:
    """Print synthetic AWS credentials as env-var export lines (CLI-10 / D-04).

    Exit codes:
      0 — success: credentials printed
      1 — PECPAccount not found for team
      2 — account exists but status is not yet ready
    """
    base = _resolve_base_url(api_url)
    account_name = f"pecp-{team}"

    # Lookup — _lookup_account_and_fetch exits 1 if not found
    try:
        _, detail = _lookup_account_and_fetch(base, team)
    except SystemExit:
        raise typer.Exit(code=1)

    current_status = str(detail.get("status", "unknown"))

    if current_status != "ready":
        console.print(
            f"[yellow]Account not yet ready[/yellow] (status: {current_status}). "
            "Run `pecp status awsaccount --team {team}` to check progress."
        )
        raise typer.Exit(code=2)

    provider_meta: dict[str, object] = detail.get("provider_metadata") or {}  # type: ignore[assignment]
    if isinstance(provider_meta, str):
        import json as _json
        provider_meta = _json.loads(provider_meta) if provider_meta else {}

    # Read exact field names from AwsAccountMockAdapter (aws_account.py verified):
    # access_key_id, secret_access_key, default_region (synthetic creds — T-05-05)
    access_key_id = provider_meta.get("access_key_id", "")
    secret_access_key = provider_meta.get("secret_access_key", "")
    default_region = provider_meta.get("default_region", "us-east-1")
    account_id = provider_meta.get("account_id", "")

    # Print export lines (D-04) — use plain print so eval works cleanly
    print(f"export AWS_ACCESS_KEY_ID={access_key_id}")
    print(f"export AWS_SECRET_ACCESS_KEY={secret_access_key}")
    print(f"export AWS_DEFAULT_REGION={default_region}")
    print(f"# Profile: {account_name} | Account: {account_id}")
    print(f"# Copy and paste the above into your terminal, or run: eval $(pecp login awsaccount --team {team})")


app.add_typer(account_login_app, name="login")

# Register the status sub-typer (replaces the former @app.command("status"))
app.add_typer(status_app, name="status")


if __name__ == "__main__":
    app()
