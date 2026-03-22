# src/snmpv3_utils/cli/query.py
"""CLI commands for snmpv3 query *."""

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
from snmpv3_utils.core.query import bulk as core_bulk
from snmpv3_utils.core.query import get as core_get
from snmpv3_utils.core.query import getnext as core_getnext
from snmpv3_utils.core.query import set_oid as core_set
from snmpv3_utils.core.query import walk as core_walk
from snmpv3_utils.debug import translate_error
from snmpv3_utils.output import OutputFormat, print_error, print_records, print_single

app = typer.Typer(no_args_is_help=True)


@app.command()
def get(
    host: str,
    oid: str,
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
    """Fetch a single OID value."""
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
    result = core_get(host, oid, usm, port=creds.port, timeout=creds.timeout, retries=creds.retries)
    if "error" in result:
        result["error"] = translate_error(result["error"], creds)  # type: ignore[typeddict-item]
        print_error(result, fmt=fmt)
        raise typer.Exit(1)
    print_single(result, fmt=fmt)


@app.command()
def getnext(
    host: str,
    oid: str,
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
    """Return the next OID after the given one (single GETNEXT step)."""
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
    result = core_getnext(
        host, oid, usm, port=creds.port, timeout=creds.timeout, retries=creds.retries
    )
    if "error" in result:
        result["error"] = translate_error(result["error"], creds)  # type: ignore[typeddict-item]
        print_error(result, fmt=fmt)
        raise typer.Exit(1)
    print_single(result, fmt=fmt)


@app.command()
def walk(
    host: str,
    oid: str,
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
    """Traverse the MIB subtree rooted at oid."""
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
    results = core_walk(
        host, oid, usm, port=creds.port, timeout=creds.timeout, retries=creds.retries
    )
    if results and "error" in results[0]:
        results[0]["error"] = translate_error(results[0]["error"], creds)  # type: ignore[typeddict-item]
        print_error(results[0], fmt=fmt)
        raise typer.Exit(1)
    print_records(results, fmt=fmt)


@app.command()
def bulk(
    host: str,
    oid: str,
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
    max_repetitions: Annotated[
        int, typer.Option("--max-repetitions", help="Max repetitions for GETBULK")
    ] = 25,
    fmt: FormatOpt = OutputFormat.RICH,
) -> None:
    """GETBULK retrieval of a MIB subtree."""
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
    results = core_bulk(
        host,
        oid,
        usm,
        port=creds.port,
        timeout=creds.timeout,
        retries=creds.retries,
        max_repetitions=max_repetitions,
    )
    if results and "error" in results[0]:
        results[0]["error"] = translate_error(results[0]["error"], creds)  # type: ignore[typeddict-item]
        print_error(results[0], fmt=fmt)
        raise typer.Exit(1)
    print_records(results, fmt=fmt)


@app.command(name="set")
def set_cmd(
    host: str,
    oid: str,
    value: str,
    type_: Annotated[str, typer.Option("--type", help="Value type: int | str | hex")] = "str",
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
    """Set an OID value. --type int|str|hex required."""
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
    result = core_set(
        host, oid, value, type_, usm, port=creds.port, timeout=creds.timeout, retries=creds.retries
    )
    if "error" in result:
        result["error"] = translate_error(result["error"], creds)  # type: ignore[typeddict-item]
        print_error(result, fmt=fmt)
        raise typer.Exit(1)
    print_single(result, fmt=fmt)
