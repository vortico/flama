import datetime
import typing as t

import marshmallow
import marshmallow.validate
import pydantic
import pytest

from flama import types
from flama.schemas.libs._libraries import libraries
from tests._utils import assert_recursive_contains

utc = datetime.UTC


class TestCaseSchemaValidation:
    @pytest.fixture(scope="function")
    def product_schema(self, app):
        if libraries.default.name == "pydantic":
            schema = pydantic.create_model(
                "Product",
                name=(str, ...),
                rating=(int | None, None),
                created=(datetime.datetime | None, None),
            )
        elif libraries.default.name == "marshmallow":
            schema = type(
                "Product",
                (marshmallow.Schema,),
                {
                    "name": marshmallow.fields.String(),
                    "rating": marshmallow.fields.Integer(allow_none=True),
                    "created": marshmallow.fields.DateTime(allow_none=True),
                },
            )
        else:
            raise ValueError(f"Wrong schema lib: {libraries.default.name}")

        return schema

    @pytest.fixture(scope="function")
    def reviewed_product_schema(self, app, product_schema):
        if libraries.default.name == "pydantic":
            schema = pydantic.create_model("ReviewedProduct", reviewer=(str, ...), __base__=product_schema)
        elif libraries.default.name == "marshmallow":
            schema = type("ReviewedProduct", (product_schema,), {"reviewer": marshmallow.fields.String()})
        else:
            raise ValueError(f"Wrong schema lib: {libraries.default.name}")

        return schema

    @pytest.fixture(scope="function")
    def location_schema(self, app):
        if libraries.default.name == "pydantic":

            def latitude_validator(cls, x):
                assert -90 <= x <= 90
                return x

            def longitude_validator(cls, x):
                assert -180 <= x <= 180
                return x

            schema = pydantic.create_model(
                "Location",
                latitude=(float, ...),
                longitude=(float, ...),
                __validators__={"latitude": latitude_validator, "longitude": longitude_validator},
            )
        elif libraries.default.name == "marshmallow":
            schema = type(
                "Location",
                (marshmallow.Schema,),
                {
                    "latitude": marshmallow.fields.Float(validate=marshmallow.validate.Range(min=-90, max=90)),
                    "longitude": marshmallow.fields.Float(validate=marshmallow.validate.Range(min=-180, max=180)),
                },
            )
        else:
            raise ValueError(f"Wrong schema lib: {libraries.default.name}")
        return schema

    @pytest.fixture(scope="function")
    def place_schema(self, app, location_schema):
        if libraries.default.name == "pydantic":
            schema = pydantic.create_model("Place", location=(location_schema, ...), name=(str, ...))
        elif libraries.default.name == "marshmallow":
            schema = type(
                "Place",
                (marshmallow.Schema,),
                {"location": marshmallow.fields.Nested(location_schema), "name": marshmallow.fields.String()},
            )
        else:
            raise ValueError(f"Wrong schema lib: {libraries.default.name}")
        return schema

    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app, product_schema, reviewed_product_schema, place_schema):
        @app.route("/product", methods=["POST"])
        def product_identity(
            product: t.Annotated[types.Schema, types.SchemaMetadata(product_schema)],
        ) -> t.Annotated[types.Schema, types.SchemaMetadata(product_schema)]:
            return product

        @app.route("/reviewed-product", methods=["POST"])
        def reviewed_product_identity(
            reviewed_product: t.Annotated[types.Schema, types.SchemaMetadata(reviewed_product_schema)],
        ) -> t.Annotated[types.Schema, types.SchemaMetadata(reviewed_product_schema)]:
            return reviewed_product

        @app.route("/place", methods=["POST"])
        def place_identity(
            place: t.Annotated[types.Schema, types.SchemaMetadata(place_schema)],
        ) -> t.Annotated[types.Schema, types.SchemaMetadata(place_schema)]:
            return place

        @app.route("/many-products", methods=["GET"])
        def many_products(
            products: t.Annotated[types.SchemaList, types.SchemaMetadata(product_schema)],
        ) -> t.Annotated[types.SchemaList, types.SchemaMetadata(product_schema)]:
            return products

        @app.route("/partial-product", methods=["GET"])
        def partial_product(
            product: t.Annotated[types.Schema, types.SchemaMetadata(product_schema, partial=True)],
        ) -> t.Annotated[types.Schema, types.SchemaMetadata(product_schema, partial=True)]:
            return product

        @app.route("/serialization-error")
        def serialization_error() -> t.Annotated[types.Schema, types.SchemaMetadata(product_schema)]:
            return {"rating": "foo", "created": "bar"}

        @app.route("/alias-product", methods=["POST"])
        def alias_product(product: types.Schema[product_schema]) -> types.Output[product_schema]:
            return product

        @app.route("/alias-many-products", methods=["POST"])
        def alias_many_products(products: types.SchemaList[product_schema]) -> types.OutputList[product_schema]:
            return products

    @pytest.mark.parametrize(
        ["path", "method", "json_data", "expected_output", "status_code"],
        [
            pytest.param(
                "/product",
                "post",
                {
                    "name": "foo",
                    "rating": 0,
                    "created": "2018-01-01T00:00:00+00:00",
                },
                {
                    "name": "foo",
                    "rating": 0,
                    "created": "2018-01-01T00:00:00+00:00",
                },
                200,
                id="simple_schema",
            ),
            pytest.param(
                "/reviewed-product",
                "post",
                {
                    "name": "foo",
                    "rating": 0,
                    "created": "2018-01-01T00:00:00+00:00",
                    "reviewer": "bar",
                },
                {
                    "name": "foo",
                    "rating": 0,
                    "created": "2018-01-01T00:00:00+00:00",
                    "reviewer": "bar",
                },
                200,
                id="inherited_schema",
            ),
            pytest.param(
                "/place",
                "post",
                {"name": "foo", "location": {"latitude": 0.0, "longitude": 0.0}},
                {"name": "foo", "location": {"latitude": 0.0, "longitude": 0.0}},
                200,
                id="nested_schema",
            ),
            pytest.param(
                "/many-products",
                "get",
                [
                    {
                        "name": "foo",
                        "rating": 0,
                        "created": "2018-01-01T00:00:00+00:00",
                    },
                    {
                        "name": "bar",
                        "rating": 1,
                        "created": "2018-01-01T00:00:00+00:00",
                    },
                ],
                [
                    {
                        "name": "foo",
                        "rating": 0,
                        "created": "2018-01-01T00:00:00+00:00",
                    },
                    {
                        "name": "bar",
                        "rating": 1,
                        "created": "2018-01-01T00:00:00+00:00",
                    },
                ],
                200,
                id="array_schema",
            ),
            pytest.param(
                "/partial-product",
                "get",
                {"name": "foo"},
                {"name": "foo"},
                200,
                id="partial_schema",
            ),
            pytest.param(
                "/serialization-error",
                "get",
                None,
                {"status": 500, "detail": "The response cannot be serialised"},
                500,
                id="serialization_error",
            ),
            pytest.param(
                "/alias-product",
                "post",
                {"name": "foo", "rating": 0, "created": "2018-01-01T00:00:00+00:00"},
                {"name": "foo", "rating": 0, "created": "2018-01-01T00:00:00+00:00"},
                200,
                id="alias_schema",
            ),
            pytest.param(
                "/alias-product",
                "post",
                {"rating": "foo"},
                {"status": 400, "detail": "The request is not valid"},
                400,
                id="alias_schema_invalid",
            ),
            pytest.param(
                "/alias-many-products",
                "post",
                [{"name": "foo", "rating": 0}, {"name": "bar", "rating": 1}],
                [{"name": "foo", "rating": 0}, {"name": "bar", "rating": 1}],
                200,
                id="alias_array_schema",
            ),
        ],
    )
    async def test_schemas(self, client, path, method, json_data, expected_output, status_code):

        response = await client.request(method, path, json=json_data)
        assert response.status_code == status_code, response.json()
        assert_recursive_contains(expected_output, response.json())


class PydanticItem(pydantic.BaseModel):
    count: int


class MarshmallowItem(marshmallow.Schema):
    count = marshmallow.fields.Integer(required=True)


class TestCaseSchemaLibraries:
    """Schemas of both libraries served side by side, each handled by its own library."""

    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.route("/pydantic/", methods=["POST"])
        def pydantic_item(item: types.Schema[PydanticItem]) -> types.Schema[PydanticItem]:
            return item

        @app.route("/marshmallow/", methods=["POST"])
        def marshmallow_item(item: types.Schema[MarshmallowItem]) -> types.Schema[MarshmallowItem]:
            return item

        @app.route("/paginated/", methods=["GET"], pagination="page_number")
        def paginated(**kwargs) -> types.SchemaList[MarshmallowItem]:
            return [{"count": i} for i in range(3)]

        @app.route("/paginated-pydantic/", methods=["GET"], pagination="page_number")
        def paginated_pydantic(**kwargs) -> types.SchemaList[PydanticItem]:
            return [{"count": i} for i in range(3)]

    @pytest.mark.parametrize(
        ["path", "body", "status_code", "result"],
        [
            pytest.param("/pydantic/", {"count": 1}, 200, {"count": 1}, id="pydantic"),
            pytest.param(
                "/pydantic/",
                {"count": "x"},
                400,
                {
                    "errors": [
                        {
                            "detail": "Input should be a valid integer, unable to parse string as an integer",
                            "pointer": "#/count",
                        }
                    ]
                },
                id="pydantic_invalid",
            ),
            pytest.param("/marshmallow/", {"count": 1}, 200, {"count": 1}, id="marshmallow"),
            pytest.param(
                "/marshmallow/",
                {"count": "x"},
                400,
                {"errors": [{"detail": "Not a valid integer.", "pointer": "#/count"}]},
                id="marshmallow_invalid",
            ),
        ],
    )
    async def test_validation(self, client, path, body, status_code, result):
        response = await client.post(path, json=body)

        assert response.status_code == status_code, response.json()
        assert_recursive_contains(result, response.json())

    async def test_pagination(self, client):
        response = await client.get("/paginated/", params={"page_size": 2})

        assert response.status_code == 200, response.json()
        assert response.json()["data"] == [{"count": 0}, {"count": 1}]

    def test_schema(self, app):
        components = set(app.schema.schema["components"]["schemas"])

        assert {
            "PydanticItem",
            "MarshmallowItem",
            "PageNumberPaginatedPydanticItem",
            "PageNumberPaginatedMarshmallowItem",
        } <= {x.rsplit(".", 1)[1] for x in components}
        # Each library's pagination metadata is published apart, as both are in use.
        assert {
            "flama.pydantic.pagination.PageNumberMeta",
            "flama.marshmallow.pagination.PageNumberMeta",
        } <= components
        assert libraries.of(MarshmallowItem, "schema") is libraries["marshmallow"]
