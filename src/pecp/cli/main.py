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

import os
from pathlib import Path

import httpx
import typer
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
    api_url: str | None = typer.Option(
        None,
        "--api-url",
        help="PECP API base URL (overrides PECP_API_URL env var; default http://localhost:8000)",
    ),
) -> None:
    """Apply a resource YAML spec to the PECP Control Plane."""
    base = _resolve_base_url(api_url)

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


@app.command("get")
def get(
    kind: str = typer.Argument(..., help="Resource kind (e.g. PECPLambda)"),
    team: str = typer.Option(..., "--team", help="Team that owns these resources"),
    api_url: str | None = typer.Option(
        None,
        "--api-url",
        help="PECP API base URL (overrides PECP_API_URL env var; default http://localhost:8000)",
    ),
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


@app.command("status")
def status(
    kind: str = typer.Argument(..., help="Resource kind (e.g. PECPLambda)"),
    name: str = typer.Argument(..., help="Resource name"),
    team: str = typer.Option(..., "--team", help="Team that owns this resource"),
    api_url: str | None = typer.Option(
        None,
        "--api-url",
        help="PECP API base URL (overrides PECP_API_URL env var; default http://localhost:8000)",
    ),
) -> None:
    """Show provisioning status and notes for a resource."""
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


@app.command("version")
def version() -> None:
    """Print the CLI version."""
    console.print("pecp 0.1.0")


if __name__ == "__main__":
    app()
