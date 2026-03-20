# tests/test_output.py
import json

from rich.console import Console

from snmpv3_utils.output import OutputFormat, print_error, print_records, print_single


def test_print_single_json(capsys):
    print_single({"oid": "1.3.6.1", "value": "Linux"}, fmt=OutputFormat.JSON)
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["oid"] == "1.3.6.1"
    assert data["value"] == "Linux"


def test_print_records_json(capsys):
    records = [
        {"oid": "1.3.6.1.2.1.1.1.0", "value": "Linux"},
        {"oid": "1.3.6.1.2.1.1.2.0", "value": "1.3.6.1"},
    ]
    print_records(records, fmt=OutputFormat.JSON)
    out = capsys.readouterr().out
    data = json.loads(out)
    assert len(data) == 2
    assert data[0]["oid"] == "1.3.6.1.2.1.1.1.0"


def test_print_error_json(capsys):
    print_error({"error": "Timeout", "host": "192.168.1.1"}, fmt=OutputFormat.JSON)
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["error"] == "Timeout"


def test_print_single_rich_does_not_crash():
    """Rich output should not raise — we don't assert exact text, just no exceptions."""
    console = Console(force_terminal=False)
    print_single({"oid": "1.3.6.1", "value": "Linux"}, fmt=OutputFormat.RICH, console=console)


def test_print_records_rich_does_not_crash():
    console = Console(force_terminal=False)
    records = [{"oid": "1.3.6.1.2.1.1.1.0", "value": "Linux"}]
    print_records(records, fmt=OutputFormat.RICH, console=console)


def test_print_error_rich_does_not_crash():
    console = Console(force_terminal=False)
    print_error({"error": "Timeout"}, fmt=OutputFormat.RICH, console=console)
