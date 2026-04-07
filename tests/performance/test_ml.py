"""Benchmark: ML model inference performance.

Measures end-to-end prediction latency for sklearn, pytorch, and tensorflow
models served through flama's model resource system via a full Flama application.
"""

import pytest

from flama import Flama
from flama.client import Client

pytestmark = pytest.mark.benchmark(group="ml")

PREDICT_PAYLOAD = {"input": [[0, 1], [1, 0]]}


def _build_ml_app(model_path, route_path: str) -> Flama:
    app = Flama(schema=None, docs=None, schema_library="pydantic")
    app.models.add_model(route_path, model=str(model_path), name="bench_model")
    return app


class TestCaseSklearn:
    @pytest.fixture(scope="class")
    def client(self, sklearn_model_path, loop):
        app = _build_ml_app(sklearn_model_path, "/sklearn/")
        client = Client(app=app)
        loop.run_until_complete(client.__aenter__())
        yield client
        loop.run_until_complete(client.__aexit__(None, None, None))

    def _bench_get(self, benchmark, loop, client, path):
        def run():
            loop.run_until_complete(client.get(path))

        benchmark(run)

    def _bench_post(self, benchmark, loop, client, path, payload):
        def run():
            loop.run_until_complete(client.post(path, json=payload))

        benchmark(run)

    def test_predict(self, benchmark, client, loop):
        self._bench_post(benchmark, loop, client, "/sklearn/predict/", PREDICT_PAYLOAD)

    def test_inspect(self, benchmark, client, loop):
        self._bench_get(benchmark, loop, client, "/sklearn/")


class TestCasePyTorch:
    @pytest.fixture(scope="class")
    def client(self, torch_model_path, loop):
        app = _build_ml_app(torch_model_path, "/torch/")
        client = Client(app=app)
        loop.run_until_complete(client.__aenter__())
        yield client
        loop.run_until_complete(client.__aexit__(None, None, None))

    def _bench_get(self, benchmark, loop, client, path):
        def run():
            loop.run_until_complete(client.get(path))

        benchmark(run)

    def _bench_post(self, benchmark, loop, client, path, payload):
        def run():
            loop.run_until_complete(client.post(path, json=payload))

        benchmark(run)

    def test_predict(self, benchmark, client, loop):
        self._bench_post(benchmark, loop, client, "/torch/predict/", PREDICT_PAYLOAD)

    def test_inspect(self, benchmark, client, loop):
        self._bench_get(benchmark, loop, client, "/torch/")


class TestCaseTensorFlow:
    @pytest.fixture(scope="class")
    def client(self, tensorflow_model_path, loop):
        app = _build_ml_app(tensorflow_model_path, "/tf/")
        client = Client(app=app)
        loop.run_until_complete(client.__aenter__())
        yield client
        loop.run_until_complete(client.__aexit__(None, None, None))

    def _bench_get(self, benchmark, loop, client, path):
        def run():
            loop.run_until_complete(client.get(path))

        benchmark(run)

    def _bench_post(self, benchmark, loop, client, path, payload):
        def run():
            loop.run_until_complete(client.post(path, json=payload))

        benchmark(run)

    def test_predict(self, benchmark, client, loop):
        self._bench_post(benchmark, loop, client, "/tf/predict/", PREDICT_PAYLOAD)

    def test_inspect(self, benchmark, client, loop):
        self._bench_get(benchmark, loop, client, "/tf/")
