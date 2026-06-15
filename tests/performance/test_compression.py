"""Benchmark: response compression overhead.

Measures the per-request cost of `CompressionMiddleware` negotiating and encoding a compressible response body
(brotli/gzip) plus the negotiation-miss fallback (identity), through a full Flama application.
"""

import pytest

from flama import Flama
from flama.client import Client
from flama.middleware import CompressionMiddleware

pytestmark = pytest.mark.benchmark(group="compression")

LARGE_LIST = [
    {"id": i, "name": f"Item {i}", "price": float(i) * 9.99, "description": f"Description for item {i}"}
    for i in range(1000)
]


class TestCaseCompression:
    @pytest.fixture(scope="class")
    @classmethod
    def client(cls, loop):
        app = Flama(schema=None, docs=None, middleware=[CompressionMiddleware(minimum_size=500)])

        @app.route("/large/")
        def large():
            return LARGE_LIST

        client = Client(app=app)
        loop.run_until_complete(client.__aenter__())
        yield client
        loop.run_until_complete(client.__aexit__(None, None, None))

    @pytest.mark.parametrize(
        "encoding",
        [
            pytest.param("br", id="brotli"),
            pytest.param("gzip", id="gzip"),
            pytest.param("identity", id="identity"),
        ],
    )
    def test_request(self, benchmark, client, loop, encoding):
        def run():
            loop.run_until_complete(client.get("/large/", headers={"accept-encoding": encoding}))

        benchmark(run)
