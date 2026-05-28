"""PECP CLI — apply resource specs via the PECP Control Plane API.

Commands:
  pecp apply -f <file> --team <team>   Submit a resource YAML to the API
  pecp version                          Print the CLI version

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

app = typer.Typer(
    name="pecp",
    help="PECP Platform Engineering Control Plane CLI",
    no_args_is_help=True,
)
console = Console()


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
    base = api_url or os.environ.get("PECP_API_URL") or "http://localhost:8000"
    base = base.rstrip("/")

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


@app.command("version")
def version() -> None:
    """Print the CLI version."""
    console.print("pecp 0.1.0")


if __name__ == "__main__":
    app()
