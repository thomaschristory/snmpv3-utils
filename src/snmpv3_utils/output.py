# src/snmpv3_utils/output.py
"""Output formatting — rich tables and JSON.

All functions accept an optional `console` parameter for testing.
The `fmt` parameter controls output format: RICH (default) or JSON.
"""

import json
from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Any

from rich.console import Console
from rich.table import Table

_default_console = Console()
_error_console = Console(stderr=True)


class OutputFormat(StrEnum):
    RICH = "rich"
    JSON = "json"


def print_single(
    record: Mapping[str, Any],
    fmt: OutputFormat = OutputFormat.RICH,
    console: Console | None = None,
) -> None:
    """Print a single result record."""
    if fmt == OutputFormat.JSON:
        print(json.dumps(record))
        return
    c = console or _default_console
    table = Table(show_header=True, header_style="bold cyan")
    for key in record:
        table.add_column(key.capitalize())
    table.add_row(*[str(v) for v in record.values()])
    c.print(table)


def print_records(
    records: Sequence[Mapping[str, Any]],
    fmt: OutputFormat = OutputFormat.RICH,
    console: Console | None = None,
) -> None:
    """Print a list of result records as a table or JSON array."""
    if not records:
        return
    if fmt == OutputFormat.JSON:
        print(json.dumps(records))
        return
    c = console or _default_console
    table = Table(show_header=True, header_style="bold cyan")
    for key in records[0]:
        table.add_column(key.capitalize())
    for record in records:
        table.add_row(*[str(v) for v in record.values()])
    c.print(table)


def print_error(
    record: Mapping[str, Any],
    fmt: OutputFormat = OutputFormat.RICH,
    console: Console | None = None,
) -> None:
    """Print an error record. Rich shows it in red on stderr; JSON goes to stdout."""
    if fmt == OutputFormat.JSON:
        print(json.dumps(record))
        return
    c = console or _error_console
    c.print(f"[bold red]Error:[/bold red] {record.get('error', record)}")
