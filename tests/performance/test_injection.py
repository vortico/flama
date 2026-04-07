"""Benchmark: Dependency injection performance.

Measures DI resolution overhead at different chain depths (simple, nested,
multi-dependency) through a full Flama application.
"""

import pytest

from flama import Flama
from flama.client import Client
from flama.injection import Component

pytestmark = pytest.mark.benchmark(group="injection")


class TypeA: ...


class TypeB: ...


class TypeC: ...


class CompA(Component):
    def resolve(self) -> TypeA:
        return TypeA()


class CompB(Component):
    def resolve(self, a: TypeA) -> TypeB:
        return TypeB()


class CompC(Component):
    def resolve(self) -> TypeC:
        return TypeC()


def _build_app() -> Flama:
    app = Flama(schema=None, docs=None, components=[CompA(), CompB(), CompC()])

    @app.route("/simple/")
    def simple(a: TypeA):
        return {"ok": True}

    @app.route("/nested/")
    def nested(b: TypeB):
        return {"ok": True}

    @app.route("/multi/")
    def multi(a: TypeA, c: TypeC):
        return {"ok": True}

    return app


class TestCaseInjection:
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

    def test_simple(self, benchmark, client, loop):
        self._bench_get(benchmark, loop, client, "/simple/")

    def test_nested(self, benchmark, client, loop):
        self._bench_get(benchmark, loop, client, "/nested/")

    def test_multi(self, benchmark, client, loop):
        self._bench_get(benchmark, loop, client, "/multi/")
