# src/snmpv3_utils/cli/auth.py
"""CLI commands for snmpv3 auth *."""

from pathlib import Path
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
from snmpv3_utils.core.auth import bulk_check as core_bulk_check
from snmpv3_utils.core.auth import check_creds as core_check_creds
from snmpv3_utils.output import OutputFormat, print_error, print_records, print_single

app = typer.Typer(no_args_is_help=True)


@app.command()
def check(
    host: str,
    profile: ProfileOpt = None,
    username: UsernameOpt = None,
    auth_protocol: AuthProtoOpt = None,
    auth_key: AuthKeyOpt = None,
    priv_protocol: PrivProtoOpt = None,
    priv_key: PrivKeyOpt = None,
    security_level: SecLevelOpt = None,
    port: PortOpt = None,
    timeout: TimeoutOpt = None,
    retries: RetriesOpt = None,
    fmt: FormatOpt = OutputFormat.RICH,
) -> None:
    """Test a single set of credentials against a host."""
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
    result = core_check_creds(
        host, usm, port=creds.port, timeout=creds.timeout, retries=1, username=creds.username
    )
    if result["status"] == "failed":
        print_error(result, fmt=fmt)
        raise typer.Exit(1)
    print_single(result, fmt=fmt)


@app.command()
def bulk(
    host: str,
    file: Annotated[Path, typer.Option("--file", "-f", help="CSV file with credentials")],
    fmt: Annotated[
        OutputFormat, typer.Option("--format", help="Output format")
    ] = OutputFormat.RICH,
) -> None:
    """Test all credential rows in a CSV file against a single host.

    CSV format: username,auth_protocol,auth_key,priv_protocol,priv_key,security_level
    """
    if not file.exists():
        typer.echo(f"File not found: {file}", err=True)
        raise typer.Exit(1)
    results = core_bulk_check(host, file)
    print_records(results, fmt=fmt)
