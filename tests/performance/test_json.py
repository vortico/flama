"""Benchmark: JSON response performance.

Measures end-to-end JSON serialization latency at different payload sizes
through a full Flama application.
"""

import datetime
import uuid

import pytest

from flama import Flama
from flama.client import Client

pytestmark = pytest.mark.benchmark(group="json")

SMALL_DICT = {"id": 1, "name": "item", "price": 9.99, "active": True, "tags": None}

NESTED_DICT = {
    "user": {
        "id": 1,
        "name": "Alice",
        "profile": {"bio": "Hello world", "age": 30, "verified": True},
        "settings": {"theme": "dark", "lang": "en", "notifications": {"email": True, "push": False}},
    },
    "items": [{"id": i, "name": f"item_{i}", "price": float(i) * 1.5} for i in range(10)],
}

LARGE_LIST = [
    {"id": i, "name": f"Item {i}", "price": float(i) * 9.99, "description": f"Description for item {i}"}
    for i in range(1000)
]

COMPLEX_TYPES = {
    "uuid": str(uuid.UUID("12345678-1234-5678-1234-567812345678")),
    "timestamp": datetime.datetime(2025, 1, 15, 12, 30, 0).isoformat(),
    "date": datetime.date(2025, 1, 15).isoformat(),
    "items": [{"id": i, "created": datetime.datetime(2025, 1, i + 1).isoformat()} for i in range(10)],
}


def _build_app() -> Flama:
    app = Flama(schema=None, docs=None)

    @app.route("/small/")
    def small():
        return SMALL_DICT

    @app.route("/nested/")
    def nested():
        return NESTED_DICT

    @app.route("/large/")
    def large():
        return LARGE_LIST

    @app.route("/complex/")
    def complex_types():
        return COMPLEX_TYPES

    return app


class TestCaseJsonPayloadSize:
    @pytest.fixture(scope="class")
    def client(self, loop):
        app = _build_app()
        client = Client(app=app)
        loop.run_until_complete(client.__aenter__())
        yield client
        loop.run_until_complete(client.__aexit__(None, None, None))

    def _bench_get(self, benchmark, loop, client, path):
        def run():
            loop.run_until_complete(client.get(path))

        benchmark(run)

    def test_small_dict(self, benchmark, client, loop):
        self._bench_get(benchmark, loop, client, "/small/")

    def test_nested_dict(self, benchmark, client, loop):
        self._bench_get(benchmark, loop, client, "/nested/")

    def test_large_list(self, benchmark, client, loop):
        self._bench_get(benchmark, loop, client, "/large/")

    def test_complex_types(self, benchmark, client, loop):
        self._bench_get(benchmark, loop, client, "/complex/")
