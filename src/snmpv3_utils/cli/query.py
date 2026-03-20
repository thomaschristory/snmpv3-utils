# src/snmpv3_utils/cli/query.py
"""CLI commands for snmpv3 query *."""

from typing import Annotated

import typer
from pysnmp.hlapi.v3arch.asyncio import UsmUserData

from snmpv3_utils.config import resolve_credentials
from snmpv3_utils.core.query import bulk as core_bulk
from snmpv3_utils.core.query import get as core_get
from snmpv3_utils.core.query import getnext as core_getnext
from snmpv3_utils.core.query import set_oid as core_set
from snmpv3_utils.core.query import walk as core_walk
from snmpv3_utils.output import OutputFormat, print_error, print_records, print_single
from snmpv3_utils.security import (
    AuthProtocol,
    Credentials,
    PrivProtocol,
    SecurityLevel,
    build_usm_user,
)

app = typer.Typer(no_args_is_help=True)

# Reusable credential option annotations
_UsernameOpt = Annotated[str | None, typer.Option("--username", "-u", help="SNMPv3 username")]
_AuthProtoOpt = Annotated[
    AuthProtocol | None, typer.Option("--auth-protocol", help="Auth protocol")
]  # noqa: E501
_AuthKeyOpt = Annotated[str | None, typer.Option("--auth-key", help="Auth passphrase")]
_PrivProtoOpt = Annotated[
    PrivProtocol | None, typer.Option("--priv-protocol", help="Priv protocol")
]  # noqa: E501
_PrivKeyOpt = Annotated[str | None, typer.Option("--priv-key", help="Priv passphrase")]
_SecLevelOpt = Annotated[
    SecurityLevel | None, typer.Option("--security-level", help="Security level")
]  # noqa: E501
_ProfileOpt = Annotated[str | None, typer.Option("--profile", "-p", help="Credential profile name")]  # noqa: E501
_FormatOpt = Annotated[OutputFormat, typer.Option("--format", "-f", help="Output format")]
_PortOpt = Annotated[int | None, typer.Option("--port", help="UDP port")]
_TimeoutOpt = Annotated[int | None, typer.Option("--timeout", help="Timeout seconds")]
_RetriesOpt = Annotated[int | None, typer.Option("--retries", help="Number of retries")]


def _build_usm(  # noqa: E501
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
    creds = resolve_credentials(profile_name=profile, cli_overrides=overrides)
    return build_usm_user(creds), creds


@app.command()
def get(
    host: str,
    oid: str,
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
    """Fetch a single OID value."""
    usm, creds = _build_usm(
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
    )  # noqa: E501
    result = core_get(host, oid, usm, port=creds.port, timeout=creds.timeout, retries=creds.retries)
    if "error" in result:
        print_error(result, fmt=fmt)
        raise typer.Exit(1)
    print_single(result, fmt=fmt)


@app.command()
def getnext(
    host: str,
    oid: str,
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
    """Return the next OID after the given one (single GETNEXT step)."""
    usm, creds = _build_usm(
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
    )  # noqa: E501
    result = core_getnext(
        host, oid, usm, port=creds.port, timeout=creds.timeout, retries=creds.retries
    )  # noqa: E501
    if "error" in result:
        print_error(result, fmt=fmt)
        raise typer.Exit(1)
    print_single(result, fmt=fmt)


@app.command()
def walk(
    host: str,
    oid: str,
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
    """Traverse the MIB subtree rooted at oid."""
    usm, creds = _build_usm(
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
    )  # noqa: E501
    results = core_walk(
        host, oid, usm, port=creds.port, timeout=creds.timeout, retries=creds.retries
    )  # noqa: E501
    if results and "error" in results[0]:
        print_error(results[0], fmt=fmt)
        raise typer.Exit(1)
    print_records(results, fmt=fmt)


@app.command()
def bulk(
    host: str,
    oid: str,
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
    max_repetitions: Annotated[
        int, typer.Option("--max-repetitions", help="Max repetitions for GETBULK")
    ] = 25,  # noqa: E501
    fmt: _FormatOpt = OutputFormat.RICH,
) -> None:
    """GETBULK retrieval of a MIB subtree."""
    usm, creds = _build_usm(
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
    )  # noqa: E501
    results = core_bulk(
        host,
        oid,
        usm,
        port=creds.port,
        timeout=creds.timeout,
        retries=creds.retries,
        max_repetitions=max_repetitions,
    )  # noqa: E501
    if results and "error" in results[0]:
        print_error(results[0], fmt=fmt)
        raise typer.Exit(1)
    print_records(results, fmt=fmt)


@app.command(name="set")
def set_cmd(
    host: str,
    oid: str,
    value: str,
    type_: Annotated[str, typer.Option("--type", help="Value type: int | str | hex")] = "str",
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
    """Set an OID value. --type int|str|hex required."""
    usm, creds = _build_usm(
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
    )  # noqa: E501
    result = core_set(
        host, oid, value, type_, usm, port=creds.port, timeout=creds.timeout, retries=creds.retries
    )  # noqa: E501
    if "error" in result:
        print_error(result, fmt=fmt)
        raise typer.Exit(1)
    print_single(result, fmt=fmt)
