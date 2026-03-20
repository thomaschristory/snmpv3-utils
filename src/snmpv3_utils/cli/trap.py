# src/snmpv3_utils/cli/trap.py
"""CLI commands for snmpv3 trap *."""
from typing import Annotated

import typer

from snmpv3_utils.config import resolve_credentials
from snmpv3_utils.core.trap import send_trap as core_send_trap
from snmpv3_utils.output import OutputFormat, print_error, print_single
from snmpv3_utils.security import AuthProtocol, PrivProtocol, SecurityLevel, build_usm_user

app = typer.Typer(no_args_is_help=True)

_ProfileOpt = Annotated[str | None, typer.Option("--profile", "-p")]
_FormatOpt = Annotated[OutputFormat, typer.Option("--format", "-f")]
_UsernameOpt = Annotated[str | None, typer.Option("--username", "-u")]
_AuthProtoOpt = Annotated[AuthProtocol | None, typer.Option("--auth-protocol")]
_AuthKeyOpt = Annotated[str | None, typer.Option("--auth-key")]
_PrivProtoOpt = Annotated[PrivProtocol | None, typer.Option("--priv-protocol")]
_PrivKeyOpt = Annotated[str | None, typer.Option("--priv-key")]
_SecLevelOpt = Annotated[SecurityLevel | None, typer.Option("--security-level")]
_PortOpt = Annotated[int | None, typer.Option("--port")]
_TimeoutOpt = Annotated[int | None, typer.Option("--timeout")]
_RetriesOpt = Annotated[int | None, typer.Option("--retries")]


@app.command()
def send(
    host: str,
    oid: Annotated[str, typer.Option("--oid", help="Trap OID")] = "1.3.6.1.6.3.1.1.5.1",
    inform: Annotated[
        bool, typer.Option("--inform", help="Send INFORM-REQUEST (acknowledged)")
    ] = False,
    port: _PortOpt = None,
    timeout: _TimeoutOpt = None,
    retries: _RetriesOpt = None,
    profile: _ProfileOpt = None,
    username: _UsernameOpt = None,
    auth_protocol: _AuthProtoOpt = None,
    auth_key: _AuthKeyOpt = None,
    priv_protocol: _PrivProtoOpt = None,
    priv_key: _PrivKeyOpt = None,
    security_level: _SecLevelOpt = None,
    fmt: _FormatOpt = OutputFormat.RICH,
) -> None:
    """Send an SNMPv3 trap or inform to a host.

    By default sends a fire-and-forget trap (coldStart OID).
    Use --inform to send an INFORM-REQUEST and wait for acknowledgment.
    """
    overrides = {
        "username": username, "auth_protocol": auth_protocol, "auth_key": auth_key,
        "priv_protocol": priv_protocol, "priv_key": priv_key, "security_level": security_level,
        "port": port or 162, "timeout": timeout, "retries": retries,
    }
    creds = resolve_credentials(profile_name=profile, cli_overrides=overrides)
    usm = build_usm_user(creds)
    result = core_send_trap(
        host, usm, inform=inform,
        port=creds.port, timeout=creds.timeout, retries=creds.retries, oid=oid
    )
    if "error" in result:
        print_error(result, fmt=fmt)
        raise typer.Exit(1)
    print_single(result, fmt=fmt)


@app.command()
def listen(
    port: Annotated[int, typer.Option("--port", help="UDP port to listen on")] = 162,
    profile: _ProfileOpt = None,
    username: _UsernameOpt = None,
    auth_protocol: _AuthProtoOpt = None,
    auth_key: _AuthKeyOpt = None,
    priv_protocol: _PrivProtoOpt = None,
    priv_key: _PrivKeyOpt = None,
    security_level: _SecLevelOpt = None,
    fmt: _FormatOpt = OutputFormat.RICH,
) -> None:
    """Listen for incoming SNMPv3 traps (blocking).

    Decrypts traps using the provided or configured credentials.
    v1 limitation: single USM credential set per invocation.
    Press Ctrl+C to stop.
    """
    from snmpv3_utils.core.trap import listen as core_listen

    overrides = {
        "username": username, "auth_protocol": auth_protocol, "auth_key": auth_key,
        "priv_protocol": priv_protocol, "priv_key": priv_key, "security_level": security_level,
    }
    creds = resolve_credentials(profile_name=profile, cli_overrides=overrides)
    usm = build_usm_user(creds)

    typer.echo(f"Listening for SNMPv3 traps on port {port}... (Ctrl+C to stop)")
    try:
        core_listen(port, usm, on_trap=lambda r: print_single(r, fmt=fmt))
    except NotImplementedError as e:
        typer.echo(f"[not implemented] {e}", err=True)
        raise typer.Exit(1) from e
    except KeyboardInterrupt:
        typer.echo("\nStopped.")
