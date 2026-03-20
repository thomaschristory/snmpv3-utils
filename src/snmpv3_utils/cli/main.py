# src/snmpv3_utils/cli/main.py
"""Root CLI application — registers all subcommand groups."""
import typer

from snmpv3_utils.cli import auth, profile, query, trap

app = typer.Typer(
    name="snmpv3",
    help="SNMPv3 testing utility — GET, WALK, SET, traps, credential testing.",
    no_args_is_help=True,
)

app.add_typer(query.app, name="query", help="SNMP query operations (get, getnext, walk, bulk, set).")  # noqa: E501
app.add_typer(trap.app, name="trap", help="Trap operations (send, listen).")
app.add_typer(auth.app, name="auth", help="Credential testing (check, bulk).")
app.add_typer(profile.app, name="profile", help="Manage credential profiles.")


if __name__ == "__main__":
    app()
