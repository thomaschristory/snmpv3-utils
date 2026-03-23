# tests/test_output.py
import json
from io import StringIO

from rich.console import Console

from snmpv3_utils.output import (
    OutputFormat,
    print_error,
    print_records,
    print_single,
    print_trap_received,
)


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


class TestPrintTrapReceived:
    def test_rich_output_contains_host_and_timestamp(self):
        record = {
            "host": "10.0.0.1",
            "timestamp": "2026-03-23T12:00:00",
            "varbinds": [{"oid": "1.3.6.1.2.1.1.3.0", "value": "12345"}],
        }
        buf = StringIO()
        console = Console(file=buf, highlight=False)
        print_trap_received(record, fmt=OutputFormat.RICH, console=console)
        output = buf.getvalue()
        assert "10.0.0.1" in output
        assert "2026-03-23T12:00:00" in output
        assert "1.3.6.1.2.1.1.3.0" in output
        assert "12345" in output

    def test_rich_output_with_multiple_varbinds(self):
        record = {
            "host": "10.0.0.2",
            "timestamp": "2026-03-23T12:00:00",
            "varbinds": [
                {"oid": "1.3.6.1.2.1.1.3.0", "value": "999"},
                {"oid": "1.3.6.1.6.3.1.1.4.1.0", "value": "1.3.6.1.6.3.1.1.5.1"},
            ],
        }
        buf = StringIO()
        console = Console(file=buf, highlight=False)
        print_trap_received(record, fmt=OutputFormat.RICH, console=console)
        output = buf.getvalue()
        assert "1.3.6.1.2.1.1.3.0" in output
        assert "1.3.6.1.6.3.1.1.4.1.0" in output

    def test_json_output_is_valid_json_with_correct_keys(self, capsys):
        record = {
            "host": "10.0.0.3",
            "timestamp": "2026-03-23T12:00:00",
            "varbinds": [{"oid": "1.3.6.1.2.1.1.3.0", "value": "0"}],
        }
        print_trap_received(record, fmt=OutputFormat.JSON)
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["host"] == "10.0.0.3"
        assert parsed["timestamp"] == "2026-03-23T12:00:00"
        assert isinstance(parsed["varbinds"], list)
        assert parsed["varbinds"][0]["oid"] == "1.3.6.1.2.1.1.3.0"

    def test_json_output_with_empty_varbinds(self, capsys):
        record = {
            "host": "10.0.0.4",
            "timestamp": "2026-03-23T12:00:00",
            "varbinds": [],
        }
        print_trap_received(record, fmt=OutputFormat.JSON)
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["varbinds"] == []
