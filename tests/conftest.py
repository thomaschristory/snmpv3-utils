import pytest
from pysnmp.hlapi.v3arch.asyncio import UsmUserData, usmNoAuthProtocol, usmNoPrivProtocol


@pytest.fixture
def usm_no_auth():
    return UsmUserData("public", authProtocol=usmNoAuthProtocol, privProtocol=usmNoPrivProtocol)


@pytest.fixture
def oid_sysdescr():
    return "1.3.6.1.2.1.1.1.0"

