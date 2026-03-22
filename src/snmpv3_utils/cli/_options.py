# src/snmpv3_utils/cli/_options.py
"""Shared CLI option type aliases and credential helpers.

All CLI subcommand modules import their credential-related Annotated types
and the build_usm_from_cli helper from here to avoid duplication.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer

if TYPE_CHECKING:
    from snmpv3_utils.security import UsmUserData

from snmpv3_utils.config import resolve_credentials
from snmpv3_utils.output import OutputFormat
from snmpv3_utils.security import (
    AuthProtocol,
    Credentials,
    PrivProtocol,
    SecurityLevel,
    build_usm_user,
)

ProfileOpt = Annotated[str | None, typer.Option("--profile", "-p", help="Credential profile name")]
FormatOpt = Annotated[OutputFormat, typer.Option("--format", "-f", help="Output format")]
UsernameOpt = Annotated[str | None, typer.Option("--username", "-u", help="SNMPv3 username")]
AuthProtoOpt = Annotated[AuthProtocol | None, typer.Option("--auth-protocol", help="Auth protocol")]
AuthKeyOpt = Annotated[str | None, typer.Option("--auth-key", help="Auth passphrase")]
PrivProtoOpt = Annotated[PrivProtocol | None, typer.Option("--priv-protocol", help="Priv protocol")]
PrivKeyOpt = Annotated[str | None, typer.Option("--priv-key", help="Priv passphrase")]
SecLevelOpt = Annotated[
    SecurityLevel | None, typer.Option("--security-level", help="Security level")
]
PortOpt = Annotated[int | None, typer.Option("--port", help="UDP port")]
TimeoutOpt = Annotated[int | None, typer.Option("--timeout", help="Timeout seconds")]
RetriesOpt = Annotated[int | None, typer.Option("--retries", help="Number of retries")]


def build_usm_from_cli(
    profile: str | None,
    username: str | None,
    auth_protocol: AuthProtocol | None,
    auth_key: str | None,
    priv_protocol: PrivProtocol | None,
    priv_key: str | None,
    security_level: SecurityLevel | None,
    port: int | None,
    timeout: int | None,
    retries: int | None,
) -> tuple[UsmUserData, Credentials]:
    """Resolve credentials from CLI options and build a USM user object."""
    overrides = {
        "username": username,
        "auth_protocol": auth_protocol,
        "auth_key": auth_key,
        "priv_protocol": priv_protocol,
        "priv_key": priv_key,
        "security_level": security_level,
        "port": port,
        "timeout": timeout,
        "retries": retries,
    }
    try:
        creds = resolve_credentials(profile_name=profile, cli_overrides=overrides)
        return build_usm_user(creds), creds
    except KeyError as e:
        typer.echo(f"Error: profile {e} not found", err=True)
        raise typer.Exit(1) from e
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e
