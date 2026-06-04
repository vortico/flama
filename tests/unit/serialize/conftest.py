import pytest


@pytest.fixture(scope="function", params=[1, 2], ids=["v1", "v2"])
def protocol_version(request):
    return request.param
