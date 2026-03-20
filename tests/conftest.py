import pytest
from unittest.mock import MagicMock
from pysnmp.hlapi.v3arch.asyncio import UsmUserData, usmNoAuthProtocol, usmNoPrivProtocol


@pytest.fixture
def usm_no_auth():
    return UsmUserData("public", authProtocol=usmNoAuthProtocol, privProtocol=usmNoPrivProtocol)


@pytest.fixture
def oid_sysdescr():
    return "1.3.6.1.2.1.1.1.0"


def make_mock_var_binds(oid: str, value: str) -> list:
    """Build a mock varBinds list as returned by pysnmp hlapi."""
    obj_type = MagicMock()
    obj_type.__getitem__ = MagicMock(side_effect=lambda i: MagicMock(
        prettyPrint=MagicMock(return_value=oid if i == 0 else value)
    ))
    return [obj_type]
