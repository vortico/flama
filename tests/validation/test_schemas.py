import datetime
import typing as t

import marshmallow
import marshmallow.validate
import pydantic
import pytest
import typesystem
import typesystem.fields

from flama import schemas
from tests.asserts import assert_recursive_contains

utc = datetime.timezone.utc


class TestCaseSchemaValidation:
    @pytest.fixture(scope="function")
    def product_schema(self, app):
        if app.schema.schema_library.lib == pydantic:
            schema = pydantic.create_model(
                "Product",
                name=(str, ...),
                rating=(t.Optional[int], None),
                created=(t.Optional[datetime.datetime], None),
            )
        elif app.schema.schema_library.lib == typesystem:
            schema = typesystem.Schema(
                title="Product",
                fields={
                    "name": typesystem.fields.String(),
                    "rating": typesystem.fields.Integer(allow_null=True),
                    "created": typesystem.fields.DateTime(allow_null=True),
                },
            )
        elif app.schema.schema_library.lib == marshmallow:
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
            raise ValueError("Wrong schema lib")

        return schema

    @pytest.fixture(scope="function")
    def reviewed_product_schema(self, app, product_schema):
        if app.schema.schema_library.lib == pydantic:
            schema = pydantic.create_model("ReviewedProduct", reviewer=(str, ...), __base__=product_schema)
        elif app.schema.schema_library.lib == typesystem:
            schema = typesystem.Schema(
                title="ReviewedProduct", fields={**product_schema.fields, **{"reviewer": typesystem.fields.String()}}
            )
        elif app.schema.schema_library.lib == marshmallow:
            schema = type("ReviewedProduct", (product_schema,), {"reviewer": marshmallow.fields.String()})
        else:
            raise ValueError("Wrong schema lib")

        return schema

    @pytest.fixture(scope="function")
    def location_schema(self, app):
        if app.schema.schema_library.lib == pydantic:

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
        elif app.schema.schema_library.lib == typesystem:
            schema = typesystem.Schema(
                fields={
                    "latitude": typesystem.fields.Number(minimum=-90, maximum=90),
                    "longitude": typesystem.fields.Number(minimum=-180, maximum=180),
                }
            )
        elif app.schema.schema_library.lib == marshmallow:
            schema = type(
                "Location",
                (marshmallow.Schema,),
                {
                    "latitude": marshmallow.fields.Float(validate=marshmallow.validate.Range(min=-90, max=90)),
                    "longitude": marshmallow.fields.Float(validate=marshmallow.validate.Range(min=-180, max=180)),
                },
            )
        else:
            raise ValueError("Wrong schema lib")
        return schema

    @pytest.fixture(scope="function")
    def place_schema(self, app, location_schema):
        if app.schema.schema_library.lib == pydantic:
            schema = pydantic.create_model("Place", location=(location_schema, ...), name=(str, ...))
        elif app.schema.schema_library.lib == typesystem:
            schema = typesystem.Schema(
                fields={
                    "location": typesystem.Reference("Location", typesystem.Definitions({"Location": location_schema})),
                    "name": typesystem.String(),
                }
            )
        elif app.schema.schema_library.lib == marshmallow:
            schema = type(
                "Place",
                (marshmallow.Schema,),
                {"location": marshmallow.fields.Nested(location_schema), "name": marshmallow.fields.String()},
            )
        else:
            raise ValueError("Wrong schema lib")
        return schema

    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app, product_schema, reviewed_product_schema, place_schema):
        @app.route("/product", methods=["POST"])
        def product_identity(
            product: t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(product_schema)],
        ) -> t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(product_schema)]:
            return product

        @app.route("/reviewed-product", methods=["POST"])
        def reviewed_product_identity(
            reviewed_product: t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(reviewed_product_schema)],
        ) -> t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(reviewed_product_schema)]:
            return reviewed_product

        @app.route("/place", methods=["POST"])
        def place_identity(
            place: t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(place_schema)],
        ) -> t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(place_schema)]:
            return place

        @app.route("/many-products", methods=["GET"])
        def many_products(
            products: t.Annotated[list[schemas.SchemaType], schemas.SchemaMetadata(product_schema)],
        ) -> t.Annotated[list[schemas.SchemaType], schemas.SchemaMetadata(product_schema)]:
            return products

        @app.route("/partial-product", methods=["GET"])
        def partial_product(
            product: t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(product_schema, partial=True)],
        ) -> t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(product_schema, partial=True)]:
            return product

        @app.route("/serialization-error")
        def serialization_error() -> t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(product_schema)]:
            return {"rating": "foo", "created": "bar"}

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
                {
                    "error": "SerializationError",
                    "status_code": 500,
                },
                500,
                id="serialization_error",
            ),
        ],
    )
    async def test_schemas(self, client, path, method, json_data, expected_output, status_code):
        response = await client.request(method, path, json=json_data)
        assert response.status_code == status_code, response.json()
        assert_recursive_contains(expected_output, response.json())
