import pytest


@pytest.fixture(scope="function", params=[1], ids=["v1"])
def protocol_version(request):
    return request.param
