# src/snmpv3_utils/cli/trap.py
"""CLI commands for snmpv3 trap *."""

from typing import Annotated

import typer

from snmpv3_utils.cli._options import (
    AuthKeyOpt,
    AuthProtoOpt,
    FormatOpt,
    PortOpt,
    PrivKeyOpt,
    PrivProtoOpt,
    ProfileOpt,
    RetriesOpt,
    SecLevelOpt,
    TimeoutOpt,
    UsernameOpt,
    build_usm_from_cli,
)
from snmpv3_utils.core.trap import send_trap as core_send_trap
from snmpv3_utils.output import OutputFormat, print_error, print_single

app = typer.Typer(no_args_is_help=True)


@app.command()
def send(
    host: str,
    oid: Annotated[str, typer.Option("--oid", help="Trap OID")] = "1.3.6.1.6.3.1.1.5.1",
    inform: Annotated[
        bool, typer.Option("--inform", help="Send INFORM-REQUEST (acknowledged)")
    ] = False,
    port: PortOpt = None,
    timeout: TimeoutOpt = None,
    retries: RetriesOpt = None,
    profile: ProfileOpt = None,
    username: UsernameOpt = None,
    auth_protocol: AuthProtoOpt = None,
    auth_key: AuthKeyOpt = None,
    priv_protocol: PrivProtoOpt = None,
    priv_key: PrivKeyOpt = None,
    security_level: SecLevelOpt = None,
    fmt: FormatOpt = OutputFormat.RICH,
) -> None:
    """Send an SNMPv3 trap or inform to a host.

    By default sends a fire-and-forget trap (coldStart OID).
    Use --inform to send an INFORM-REQUEST and wait for acknowledgment.
    """
    usm, creds = build_usm_from_cli(
        profile,
        username,
        auth_protocol,
        auth_key,
        priv_protocol,
        priv_key,
        security_level,
        port,
        timeout,
        retries,
    )
    result = core_send_trap(
        host,
        usm,
        inform=inform,
        port=creds.port,
        timeout=creds.timeout,
        retries=creds.retries,
        oid=oid,
    )
    if "error" in result:
        print_error(result, fmt=fmt)
        raise typer.Exit(1)
    print_single(result, fmt=fmt)


@app.command()
def listen(
    port: Annotated[int, typer.Option("--port", help="UDP port to listen on")] = 162,
    profile: ProfileOpt = None,
    username: UsernameOpt = None,
    auth_protocol: AuthProtoOpt = None,
    auth_key: AuthKeyOpt = None,
    priv_protocol: PrivProtoOpt = None,
    priv_key: PrivKeyOpt = None,
    security_level: SecLevelOpt = None,
    fmt: FormatOpt = OutputFormat.RICH,
) -> None:
    """Listen for incoming SNMPv3 traps (blocking).

    Decrypts traps using the provided or configured credentials.
    v1 limitation: single USM credential set per invocation.
    Press Ctrl+C to stop.
    """
    from snmpv3_utils.core.trap import listen as core_listen

    usm, _creds = build_usm_from_cli(
        profile,
        username,
        auth_protocol,
        auth_key,
        priv_protocol,
        priv_key,
        security_level,
        None,
        None,
        None,
    )

    typer.echo(f"Listening for SNMPv3 traps on port {port}... (Ctrl+C to stop)")
    try:
        core_listen(port, usm, on_trap=lambda r: print_single(r, fmt=fmt))
    except NotImplementedError as e:
        typer.echo(f"[not implemented] {e}", err=True)
        raise typer.Exit(1) from e
    except KeyboardInterrupt:
        typer.echo("\nStopped.")
