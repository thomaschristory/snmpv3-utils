# src/snmpv3_utils/cli/main.py
"""Root CLI application — registers all subcommand groups."""

from importlib.metadata import version

import typer

from snmpv3_utils.cli import auth, profile, query, trap

app = typer.Typer(
    name="snmpv3",
    help="SNMPv3 testing utility — GET, WALK, SET, traps, credential testing.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(version("snmpv3-utils"))
        raise typer.Exit()


@app.callback()
def main(
    _version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
    verbose: int = typer.Option(
        0,
        "--verbose",
        "-v",
        count=True,
        help="Increase verbosity (-v for info, -vv for debug).",
    ),
) -> None:
    from snmpv3_utils.debug import configure_logging

    configure_logging(verbose)


app.add_typer(
    query.app, name="query", help="SNMP query operations (get, getnext, walk, bulk, set)."
)  # noqa: E501
app.add_typer(trap.app, name="trap", help="Trap operations (send, listen).")
app.add_typer(auth.app, name="auth", help="Credential testing (check, bulk).")
app.add_typer(profile.app, name="profile", help="Manage credential profiles.")


if __name__ == "__main__":
    app()
