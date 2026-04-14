"""Benchmark: Middleware overhead.

Measures per-request cost as middleware stack depth increases (0, 5, 10 layers)
through a full Flama application.
"""

import pytest

from flama import Flama, types
from flama.client import Client
from flama.middleware import Middleware

pytestmark = pytest.mark.benchmark(group="middleware")


class NoopMiddleware(Middleware):
    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        await self.app(scope, receive, send)


def _build_app(n_middleware: int) -> Flama:
    middleware = [NoopMiddleware() for _ in range(n_middleware)]
    app = Flama(schema=None, docs=None, middleware=middleware)

    @app.route("/plain/")
    def plain():
        return {"message": "hello"}

    return app


class TestCaseMiddleware:
    @pytest.fixture(scope="class")
    def client_0(self, loop):
        client = Client(app=_build_app(0))
        loop.run_until_complete(client.__aenter__())
        yield client
        loop.run_until_complete(client.__aexit__(None, None, None))

    @pytest.fixture(scope="class")
    def client_5(self, loop):
        client = Client(app=_build_app(5))
        loop.run_until_complete(client.__aenter__())
        yield client
        loop.run_until_complete(client.__aexit__(None, None, None))

    @pytest.fixture(scope="class")
    def client_10(self, loop):
        client = Client(app=_build_app(10))
        loop.run_until_complete(client.__aenter__())
        yield client
        loop.run_until_complete(client.__aexit__(None, None, None))

    def _bench_get(self, benchmark, loop, client, path):
        def run():
            loop.run_until_complete(client.get(path))

        benchmark(run)

    def test_no_middleware(self, benchmark, client_0, loop):
        self._bench_get(benchmark, loop, client_0, "/plain/")

    def test_5_middleware(self, benchmark, client_5, loop):
        self._bench_get(benchmark, loop, client_5, "/plain/")

    def test_10_middleware(self, benchmark, client_10, loop):
        self._bench_get(benchmark, loop, client_10, "/plain/")
