"""Tests that TypedDict types are importable and have expected keys."""

from snmpv3_utils.types import (
    AuthError,
    AuthResult,
    AuthSuccess,
    SetError,
    SetResult,
    SetSuccess,
    TrapError,
    TrapReceived,
    TrapResult,
    TrapSuccess,
    VarBindError,
    VarBindResult,
    VarBindSuccess,
)


def test_varbind_success_keys() -> None:
    record: VarBindSuccess = {"oid": "1.3.6.1.2.1.1.1.0", "value": "Linux"}
    assert set(record.keys()) == {"oid", "value"}


def test_varbind_error_keys() -> None:
    record: VarBindError = {"error": "timeout", "host": "192.168.1.1", "oid": "1.3.6.1.2.1.1.1.0"}
    assert set(record.keys()) == {"error", "host", "oid"}


def test_set_success_keys() -> None:
    record: SetSuccess = {
        "status": "ok",
        "host": "192.168.1.1",
        "oid": "1.3.6.1.2.1.1.1.0",
        "value": "42",
    }
    assert set(record.keys()) == {"status", "host", "oid", "value"}


def test_set_error_keys() -> None:
    record: SetError = {"error": "timeout", "host": "192.168.1.1", "oid": "1.3.6.1.2.1.1.1.0"}
    assert set(record.keys()) == {"error", "host", "oid"}


def test_auth_success_keys() -> None:
    record: AuthSuccess = {
        "status": "ok",
        "host": "192.168.1.1",
        "username": "admin",
        "sysdescr": "Linux",
    }
    assert set(record.keys()) == {"status", "host", "username", "sysdescr"}


def test_auth_error_keys() -> None:
    record: AuthError = {
        "status": "failed",
        "host": "192.168.1.1",
        "username": "admin",
        "error": "timeout",
    }
    assert set(record.keys()) == {"status", "host", "username", "error"}


def test_trap_success_keys() -> None:
    record: TrapSuccess = {"status": "ok", "host": "192.168.1.1", "type": "trap", "inform": False}
    assert set(record.keys()) == {"status", "host", "type", "inform"}


def test_trap_error_keys() -> None:
    record: TrapError = {"error": "timeout", "host": "192.168.1.1", "type": "trap", "inform": False}
    assert set(record.keys()) == {"error", "host", "type", "inform"}


def test_union_aliases_exist() -> None:
    """Verify union aliases are importable (type-level only)."""
    assert VarBindResult is not None
    assert SetResult is not None
    assert AuthResult is not None
    assert TrapResult is not None


def test_types_importable_from_package_root() -> None:
    """Verify all types are re-exported from snmpv3_utils."""
    from snmpv3_utils import (
        AuthError,
        AuthResult,
        AuthSuccess,
        SetError,
        SetResult,
        SetSuccess,
        TrapError,
        TrapResult,
        TrapSuccess,
        VarBindError,
        VarBindResult,
        VarBindSuccess,
    )

    for typ in (
        AuthError,
        AuthResult,
        AuthSuccess,
        SetError,
        SetResult,
        SetSuccess,
        TrapError,
        TrapResult,
        TrapSuccess,
        VarBindError,
        VarBindResult,
        VarBindSuccess,
    ):
        assert typ is not None


class TestTrapReceived:
    def test_trap_received_shape(self):
        record: TrapReceived = {
            "host": "192.168.1.1",
            "timestamp": "2026-03-23T12:00:00",
            "varbinds": [{"oid": "1.3.6.1.2.1.1.3.0", "value": "12345"}],
        }
        assert record["host"] == "192.168.1.1"
        assert record["timestamp"] == "2026-03-23T12:00:00"
        assert len(record["varbinds"]) == 1
        assert record["varbinds"][0]["oid"] == "1.3.6.1.2.1.1.3.0"

    def test_trap_received_exported_from_package(self):
        import snmpv3_utils

        assert snmpv3_utils.TrapReceived is not None
