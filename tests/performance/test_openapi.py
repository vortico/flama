"""Benchmark: OpenAPI document generation.

Measures the cost of generating the OpenAPI specification for an application with many distinct schema-typed
routes, exercising the schema registry, generator, and ``$defs`` bundling.
"""

import typing as t

import pydantic
import pytest

from flama import Flama, types
from flama.client import Client

pytestmark = pytest.mark.benchmark(group="schema")

N_MODELS = 50
_EXTRA_FIELDS = {f"field_{i}": (str, "") for i in range(8)}


class TestCaseOpenAPIGeneration:
    @pytest.fixture(scope="class")
    def client(self, loop):
        app = Flama(schema="/schema/", docs=None, schema_library="pydantic")
        for i in range(N_MODELS):
            model = pydantic.create_model(
                f"Model{i}", id=(int, ...), name=(str, ...), price=(float, 0.0), **_EXTRA_FIELDS
            )

            def handler():
                return {}

            handler.__annotations__["return"] = t.Annotated[types.Schema, types.SchemaMetadata(model)]
            app.add_route(f"/m{i}/", handler, methods=["GET"], name=f"get_{i}")

        client = Client(app=app)
        loop.run_until_complete(client.__aenter__())
        yield client
        loop.run_until_complete(client.__aexit__(None, None, None))

    def test_request(self, benchmark, client, loop):
        def run():
            loop.run_until_complete(client.get("/schema/"))

        benchmark(run)
