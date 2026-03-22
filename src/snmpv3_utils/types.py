"""Typed result dictionaries for SNMP operations."""

from typing import Literal, TypeAlias, TypedDict

# --- Query operations (get, getnext, walk, bulk) ---


class VarBindSuccess(TypedDict):
    oid: str
    value: str


class VarBindError(TypedDict):
    error: str
    host: str
    oid: str


VarBindResult: TypeAlias = VarBindSuccess | VarBindError

# --- Set operation ---


class SetSuccess(TypedDict):
    status: Literal["ok"]
    host: str
    oid: str
    value: str


class SetError(TypedDict):
    error: str
    host: str
    oid: str


SetResult: TypeAlias = SetSuccess | SetError

# --- Auth operations (check_creds, bulk_check) ---


class AuthSuccess(TypedDict):
    status: Literal["ok"]
    host: str
    username: str
    sysdescr: str


class AuthError(TypedDict):
    status: Literal["failed"]
    host: str
    username: str
    error: str


AuthResult: TypeAlias = AuthSuccess | AuthError

# --- Trap operation ---


class TrapSuccess(TypedDict):
    status: Literal["ok"]
    host: str
    type: str
    inform: bool


class TrapError(TypedDict):
    error: str
    host: str
    type: str
    inform: bool


TrapResult: TypeAlias = TrapSuccess | TrapError

# --- Stress test operation ---


class StressResult(TypedDict):
    host: str
    sent: int
    errors: int
    success_rate: str
    duration_s: float
    rate_achieved: float
    error_samples: list[str]
