# src/snmpv3_utils/cli/auth.py
"""CLI commands for snmpv3 auth *."""
from pathlib import Path
from typing import Annotated

import typer

from snmpv3_utils.config import resolve_credentials
from snmpv3_utils.core.auth import bulk_check as core_bulk_check
from snmpv3_utils.core.auth import check_creds as core_check_creds
from snmpv3_utils.output import OutputFormat, print_error, print_records, print_single
from snmpv3_utils.security import AuthProtocol, PrivProtocol, SecurityLevel, build_usm_user

app = typer.Typer(no_args_is_help=True)

_ProfileOpt = Annotated[str | None, typer.Option("--profile", "-p", help="Credential profile name")]  # noqa: E501
_FormatOpt = Annotated[OutputFormat, typer.Option("--format", "-f", help="Output format")]
_UsernameOpt = Annotated[str | None, typer.Option("--username", "-u", help="SNMPv3 username")]
_AuthProtoOpt = Annotated[AuthProtocol | None, typer.Option("--auth-protocol", help="Auth protocol")]  # noqa: E501
_AuthKeyOpt = Annotated[str | None, typer.Option("--auth-key", help="Auth passphrase")]
_PrivProtoOpt = Annotated[PrivProtocol | None, typer.Option("--priv-protocol", help="Priv protocol")]  # noqa: E501
_PrivKeyOpt = Annotated[str | None, typer.Option("--priv-key", help="Priv passphrase")]
_SecLevelOpt = Annotated[SecurityLevel | None, typer.Option("--security-level", help="Security level")]  # noqa: E501
_PortOpt = Annotated[int | None, typer.Option("--port", help="UDP port")]
_TimeoutOpt = Annotated[int | None, typer.Option("--timeout", help="Timeout seconds")]
_RetriesOpt = Annotated[int | None, typer.Option("--retries", help="Number of retries")]


@app.command()
def check(
    host: str,
    profile: _ProfileOpt = None,
    username: _UsernameOpt = None,
    auth_protocol: _AuthProtoOpt = None,
    auth_key: _AuthKeyOpt = None,
    priv_protocol: _PrivProtoOpt = None,
    priv_key: _PrivKeyOpt = None,
    security_level: _SecLevelOpt = None,
    port: _PortOpt = None,
    timeout: _TimeoutOpt = None,
    retries: _RetriesOpt = None,
    fmt: _FormatOpt = OutputFormat.RICH,
) -> None:
    """Test a single set of credentials against a host."""
    overrides = {
        "username": username, "auth_protocol": auth_protocol, "auth_key": auth_key,
        "priv_protocol": priv_protocol, "priv_key": priv_key, "security_level": security_level,
        "port": port, "timeout": timeout, "retries": retries,
    }
    creds = resolve_credentials(profile_name=profile, cli_overrides=overrides)
    usm = build_usm_user(creds)
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
    fmt: Annotated[  # noqa: E501
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
