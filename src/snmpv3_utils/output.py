# src/snmpv3_utils/output.py
"""Output formatting — rich tables and JSON.

All functions accept an optional `console` parameter for testing.
The `fmt` parameter controls output format: RICH (default) or JSON.
"""

import json
import time
from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from enum import StrEnum
from typing import Any

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
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


@contextmanager
def stress_progress(
    host: str,
    count: int,
    duration: int | None,
) -> Generator[Callable[[int, int | None], None], None, None]:
    """Context manager for stress test Rich progress bar.

    Yields a callback ``(dispatched, total) -> None`` that updates the bar.
    """
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn(
            "{task.completed}/{task.total}" if duration is None else "{task.completed} sent"
        ),
        TextColumn("[green]{task.fields[rate]}/s"),
    )
    total_val = count if duration is None else None
    task_id = progress.add_task(f"Stress testing {host}", total=total_val, rate="0")

    start_time = time.monotonic()

    def _on_progress(dispatched: int, total: int | None) -> None:
        elapsed = time.monotonic() - start_time
        current_rate = f"{dispatched / elapsed:.1f}" if elapsed > 0 else "0"
        progress.update(task_id, completed=dispatched, rate=current_rate)

    progress.start()
    try:
        yield _on_progress
    finally:
        progress.stop()


def print_trap_received(
    record: Mapping[str, Any],
    fmt: OutputFormat = OutputFormat.RICH,
    console: Console | None = None,
) -> None:
    """Print a single received trap. Called once per arriving trap (streaming).

    Rich: header line with timestamp and host, followed by OID/Value table if varbinds present.
    JSON: one JSON object per line, newline-delimited.
    """
    if fmt == OutputFormat.JSON:
        print(json.dumps(record))
        return
    c = console or _default_console
    c.print(f"[bold]{record['timestamp']}[/bold] Trap from [cyan]{record['host']}[/cyan]")
    varbinds = record.get("varbinds", [])
    if varbinds:
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("OID")
        table.add_column("Value")
        for vb in varbinds:
            table.add_row(str(vb["oid"]), str(vb["value"]))
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
