import pytest


@pytest.fixture(scope="function", params=["bz2", "lzma", "zlib", "zstd"])
def compression_format(request):
    return request.param


@pytest.fixture(scope="function", params=[1], ids=["v1"])
def protocol_version(request):
    return request.param
