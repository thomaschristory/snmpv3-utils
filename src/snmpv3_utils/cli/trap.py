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
from snmpv3_utils.core.trap import listen as core_listen
from snmpv3_utils.core.trap import send_trap as core_send_trap
from snmpv3_utils.core.trap import stress_trap as core_stress_trap
from snmpv3_utils.debug import translate_error
from snmpv3_utils.output import OutputFormat, print_error, print_single, stress_progress

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
        default_port=162,
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
        result["error"] = translate_error(result["error"], creds)  # type: ignore[typeddict-item]
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
        core_listen(port, [usm], on_trap=lambda r: print_single(r, fmt=fmt))
    except KeyboardInterrupt:
        typer.echo("\nStopped.")


@app.command()
def stress(
    host: str,
    count: Annotated[int, typer.Option("--count", "-n", help="Total traps to send")] = 1000,
    duration: Annotated[
        int | None, typer.Option("--duration", "-d", help="Run for N seconds (overrides --count)")
    ] = None,
    rate: Annotated[int, typer.Option("--rate", help="Target traps/sec (0=unlimited)")] = 100,
    concurrency: Annotated[
        int, typer.Option("--concurrency", help="Max concurrent in-flight traps")
    ] = 10,
    inform: Annotated[
        bool, typer.Option("--inform", help="Send INFORM-REQUEST (acknowledged)")
    ] = False,
    oid: Annotated[str, typer.Option("--oid", help="Trap OID")] = "1.3.6.1.6.3.1.1.5.1",
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
    """Send a high volume of traps for stress testing.

    By default sends 1000 traps at 100/s with concurrency=10.
    Use --duration to run for a fixed time instead of a fixed count.
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
        default_port=162,
    )

    # Use retries=0 default for stress unless explicitly overridden
    stress_retries = creds.retries if retries is not None else 0

    stress_kwargs: dict[str, object] = dict(
        count=count,
        duration=duration,
        rate=rate,
        concurrency=concurrency,
        inform=inform,
        port=creds.port,
        timeout=creds.timeout,
        retries=stress_retries,
        oid=oid,
    )

    try:
        if fmt == OutputFormat.RICH:
            with stress_progress(host, count, duration) as progress_callback:
                result = core_stress_trap(host, usm, on_progress=progress_callback, **stress_kwargs)  # type: ignore[arg-type]
        else:
            result = core_stress_trap(host, usm, **stress_kwargs)  # type: ignore[arg-type]
    except KeyboardInterrupt:
        typer.echo("\nStopped.")
        return

    print_single(result, fmt=fmt)
    if result["sent"] == 0 or result["errors"] >= result["sent"]:
        samples: list[str] = result["error_samples"]
        if samples:
            sample_msg = translate_error(samples[0], creds)
            typer.echo(
                f"Error: all {result['sent']} traps failed. Sample: {sample_msg}",
                err=True,
            )
        elif result["sent"] == 0:
            typer.echo("Error: no traps sent.", err=True)
        raise typer.Exit(1)
