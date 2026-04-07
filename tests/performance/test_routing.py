"""Benchmark: Route resolution performance.

Measures how request latency scales with route table size (10, 50, 200 routes)
using static and parametric paths through a full Flama application.
"""

import pytest

from flama import Flama
from flama.client import Client

pytestmark = pytest.mark.benchmark(group="routing")


def _noop():
    return {"ok": True}


def _build_app(n: int, pattern: str = "/resource_{i}/{{id:int}}/") -> Flama:
    app = Flama(schema=None, docs=None)
    for i in range(n):
        app.add_route(pattern.format(i=i), _noop, methods=["GET"], name=f"route_{i}")
    return app


class TestCaseStaticRoutes:
    @pytest.fixture(scope="class")
    def client(self, loop):
        app = _build_app(10, pattern="/static_{i}/")
        client = Client(app=app)
        loop.run_until_complete(client.__aenter__())
        yield client
        loop.run_until_complete(client.__aexit__(None, None, None))

    def _bench_get(self, benchmark, loop, client, path):
        def run():
            loop.run_until_complete(client.get(path))

        benchmark(run)

    def test_static_10(self, benchmark, client, loop):
        self._bench_get(benchmark, loop, client, "/static_5/")


class TestCaseRoutes10:
    @pytest.fixture(scope="class")
    def client(self, loop):
        app = _build_app(10)
        client = Client(app=app)
        loop.run_until_complete(client.__aenter__())
        yield client
        loop.run_until_complete(client.__aexit__(None, None, None))

    def _bench_get(self, benchmark, loop, client, path):
        def run():
            loop.run_until_complete(client.get(path))

        benchmark(run)

    def test_first(self, benchmark, client, loop):
        self._bench_get(benchmark, loop, client, "/resource_0/42/")

    def test_last(self, benchmark, client, loop):
        self._bench_get(benchmark, loop, client, "/resource_9/42/")


class TestCaseRoutes50:
    @pytest.fixture(scope="class")
    def client(self, loop):
        app = _build_app(50)
        client = Client(app=app)
        loop.run_until_complete(client.__aenter__())
        yield client
        loop.run_until_complete(client.__aexit__(None, None, None))

    def _bench_get(self, benchmark, loop, client, path):
        def run():
            loop.run_until_complete(client.get(path))

        benchmark(run)

    def test_first(self, benchmark, client, loop):
        self._bench_get(benchmark, loop, client, "/resource_0/42/")

    def test_last(self, benchmark, client, loop):
        self._bench_get(benchmark, loop, client, "/resource_49/42/")


class TestCaseRoutes200:
    @pytest.fixture(scope="class")
    def client(self, loop):
        app = _build_app(200)
        client = Client(app=app)
        loop.run_until_complete(client.__aenter__())
        yield client
        loop.run_until_complete(client.__aexit__(None, None, None))

    def _bench_get(self, benchmark, loop, client, path):
        def run():
            loop.run_until_complete(client.get(path))

        benchmark(run)

    def test_first(self, benchmark, client, loop):
        self._bench_get(benchmark, loop, client, "/resource_0/42/")

    def test_last(self, benchmark, client, loop):
        self._bench_get(benchmark, loop, client, "/resource_199/42/")
