"""Benchmark: Schema validation performance.

Measures pydantic input validation and output serialization overhead through
schema-typed Flama endpoints.
"""

import typing as t

import pydantic
import pytest

from flama import Flama, types
from flama.client import Client

pytestmark = pytest.mark.benchmark(group="schema")


class SmallModel(pydantic.BaseModel):
    name: str
    price: float
    in_stock: bool = True
    quantity: int = 0
    tags: str | None = None


class MediumModel(pydantic.BaseModel):
    id: int
    name: str
    description: str
    price: float
    discount: float = 0.0
    in_stock: bool = True
    quantity: int = 0
    category: str = ""
    brand: str = ""
    sku: str = ""
    weight: float = 0.0
    length: float = 0.0
    width: float = 0.0
    height: float = 0.0
    color: str = ""
    material: str = ""
    rating: float = 0.0
    reviews: int = 0
    featured: bool = False
    tags: str | None = None


SMALL_DATA = {"name": "Widget", "price": 9.99, "in_stock": True, "quantity": 5, "tags": "sale"}
MEDIUM_DATA = {
    "id": 1,
    "name": "Widget",
    "description": "A fine widget",
    "price": 9.99,
    "discount": 1.0,
    "in_stock": True,
    "quantity": 5,
    "category": "tools",
    "brand": "Acme",
    "sku": "ACM-001",
    "weight": 0.5,
    "length": 10.0,
    "width": 5.0,
    "height": 3.0,
    "color": "red",
    "material": "steel",
    "rating": 4.5,
    "reviews": 42,
    "featured": True,
    "tags": "sale",
}

ITEMS_DB: dict[int, dict] = {1: {**SMALL_DATA, "id": 1}, 2: {**MEDIUM_DATA}}


def _build_app() -> Flama:
    app = Flama(schema=None, docs=None, schema_library="pydantic")

    @app.route("/small/{item_id:int}/")
    def get_small(item_id: int) -> t.Annotated[types.Schema, types.SchemaMetadata(SmallModel)]:
        return ITEMS_DB[1]

    @app.route("/small/", methods=["POST"])
    def post_small(
        item: t.Annotated[types.Schema, types.SchemaMetadata(SmallModel)],
    ) -> t.Annotated[types.Schema, types.SchemaMetadata(SmallModel)]:
        return {**item, "id": 1}

    @app.route("/medium/{item_id:int}/")
    def get_medium(item_id: int) -> t.Annotated[types.Schema, types.SchemaMetadata(MediumModel)]:
        return ITEMS_DB[2]

    @app.route("/medium/", methods=["POST"])
    def post_medium(
        item: t.Annotated[types.Schema, types.SchemaMetadata(MediumModel)],
    ) -> t.Annotated[types.Schema, types.SchemaMetadata(MediumModel)]:
        return {**item}

    return app


class TestCaseSchemaSmall:
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

    def _bench_post(self, benchmark, loop, client, path, payload):
        def run():
            loop.run_until_complete(client.post(path, json=payload))

        benchmark(run)

    def test_get(self, benchmark, client, loop):
        self._bench_get(benchmark, loop, client, "/small/1/")

    def test_post(self, benchmark, client, loop):
        self._bench_post(benchmark, loop, client, "/small/", SMALL_DATA)


class TestCaseSchemaMedium:
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

    def _bench_post(self, benchmark, loop, client, path, payload):
        def run():
            loop.run_until_complete(client.post(path, json=payload))

        benchmark(run)

    def test_get(self, benchmark, client, loop):
        self._bench_get(benchmark, loop, client, "/medium/2/")

    def test_post(self, benchmark, client, loop):
        self._bench_post(benchmark, loop, client, "/medium/", MEDIUM_DATA)
