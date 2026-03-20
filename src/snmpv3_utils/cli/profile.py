# src/snmpv3_utils/cli/profile.py
"""CLI commands for snmpv3 profile *."""
import json
from dataclasses import asdict
from typing import Annotated

import typer

from snmpv3_utils.config import delete_profile, list_profiles, load_profile, save_profile
from snmpv3_utils.output import OutputFormat
from snmpv3_utils.security import AuthProtocol, Credentials, PrivProtocol, SecurityLevel

app = typer.Typer(no_args_is_help=True)


@app.command(name="list")
def list_cmd(
    fmt: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.RICH,
) -> None:
    """List all saved profiles."""
    names = list_profiles()
    if not names:
        typer.echo("No profiles saved.")
        return
    if fmt == OutputFormat.JSON:
        print(json.dumps(names))
    else:
        for name in names:
            typer.echo(f"  {name}")


@app.command()
def show(
    name: str,
    fmt: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.RICH,
) -> None:
    """Show details for a named profile."""
    try:
        profile = load_profile(name)
    except KeyError:
        typer.echo(f"Profile '{name}' not found.", err=True)
        raise typer.Exit(1) from None
    data = {k: (v.value if hasattr(v, "value") else v) for k, v in asdict(profile).items()}
    if fmt == OutputFormat.JSON:
        print(json.dumps(data))
    else:
        for k, v in data.items():
            typer.echo(f"  {k}: {v}")


@app.command()
def add(
    name: str,
    username: Annotated[str, typer.Option("--username", "-u")] = "",
    auth_protocol: Annotated[AuthProtocol | None, typer.Option("--auth-protocol")] = None,
    auth_key: Annotated[str | None, typer.Option("--auth-key")] = None,
    priv_protocol: Annotated[PrivProtocol | None, typer.Option("--priv-protocol")] = None,
    priv_key: Annotated[str | None, typer.Option("--priv-key")] = None,
    security_level: Annotated[
        SecurityLevel, typer.Option("--security-level")
    ] = SecurityLevel.NO_AUTH_NO_PRIV,
    port: Annotated[int, typer.Option("--port")] = 161,
    timeout: Annotated[int, typer.Option("--timeout")] = 5,
    retries: Annotated[int, typer.Option("--retries")] = 3,
) -> None:
    """Add or update a named profile."""
    profile = Credentials(
        username=username,
        auth_protocol=auth_protocol,
        auth_key=auth_key,
        priv_protocol=priv_protocol,
        priv_key=priv_key,
        security_level=security_level,
        port=port,
        timeout=timeout,
        retries=retries,
    )
    save_profile(name, profile)
    typer.echo(f"Profile '{name}' saved.")


@app.command()
def delete(name: str) -> None:
    """Delete a named profile."""
    delete_profile(name)
    typer.echo(f"Profile '{name}' deleted.")
