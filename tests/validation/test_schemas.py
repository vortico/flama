import datetime

import marshmallow
import marshmallow.validate
import pytest
import typesystem

from tests.conftest import assert_recursive_contains

utc = datetime.timezone.utc


class TestCaseSchemaValidation:
    @pytest.fixture(scope="function")
    def product_schema(self, app):
        from flama import schemas

        if schemas.lib == typesystem:
            schema = typesystem.Schema(
                fields={
                    "name": typesystem.fields.String(),
                    "rating": typesystem.fields.Integer(allow_null=True),
                    "created": typesystem.fields.DateTime(allow_null=True),
                }
            )
        elif schemas.lib == marshmallow:
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

        app.schema.schemas["Product"] = schema
        return schema

    @pytest.fixture(scope="function")
    def product_array_schema(self, app, product_schema):
        from flama import schemas

        if schemas.lib == typesystem:
            schema = typesystem.fields.Array(typesystem.Reference("Product", app.schema.schemas))
        elif schemas.lib == marshmallow:
            schema = product_schema(many=True)
        else:
            raise ValueError("Wrong schema lib")

        return schema

    @pytest.fixture(scope="function")
    def reviewed_product_schema(self, app, product_schema):
        from flama import schemas

        if schemas.lib == typesystem:
            schema = typesystem.Schema(fields={**product_schema.fields, **{"reviewer": typesystem.fields.String()}})
        elif schemas.lib == marshmallow:
            schema = type("ReviewedProduct", (product_schema,), {"reviewer": marshmallow.fields.String()})
        else:
            raise ValueError("Wrong schema lib")

        app.schema.schemas["ReviewedProduct"] = schema
        return schema

    @pytest.fixture(scope="function")
    def location_schema(self, app):
        from flama import schemas

        if schemas.lib == typesystem:
            schema = typesystem.Schema(
                fields={
                    "latitude": typesystem.fields.Number(minimum=-90, maximum=90),
                    "longitude": typesystem.fields.Number(minimum=-180, maximum=180),
                }
            )
        elif schemas.lib == marshmallow:
            schema = type(
                "Location",
                (marshmallow.Schema,),
                {
                    "latitude": marshmallow.fields.Number(validate=marshmallow.validate.Range(min=-90, max=90)),
                    "longitude": marshmallow.fields.Number(validate=marshmallow.validate.Range(min=-180, max=180)),
                },
            )
        else:
            raise ValueError("Wrong schema lib")

        app.schema.schemas["Location"] = schema
        return schema

    @pytest.fixture(scope="function")
    def place_schema(self, app, location_schema):
        from flama import schemas

        if schemas.lib == typesystem:
            schema = typesystem.Schema(
                fields={
                    "location": typesystem.Reference("Location", app.schema.schemas),
                    "name": typesystem.String(),
                }
            )
        elif schemas.lib == marshmallow:
            schema = type(
                "Place",
                (marshmallow.Schema,),
                {"location": marshmallow.fields.Nested(location_schema), "name": marshmallow.fields.String()},
            )
        else:
            raise ValueError("Wrong schema lib")
        app.schema.schemas["Place"] = schema
        return schema

    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(
        self, app, product_schema, product_array_schema, reviewed_product_schema, location_schema, place_schema
    ):
        @app.route("/product", methods=["POST"])
        def product_identity(product: product_schema) -> product_schema:
            return product

        @app.route("/reviewed-product", methods=["POST"])
        def reviewed_product_identity(reviewed_product: reviewed_product_schema) -> reviewed_product_schema:
            return reviewed_product

        @app.route("/place", methods=["POST"])
        def place_identity(place: place_schema) -> place_schema:
            return place

        @app.route("/many-products", methods=["GET"])
        def many_products() -> product_array_schema:
            return [
                {
                    "name": "foo",
                    "rating": 0,
                    "created": datetime.datetime(2018, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc),
                },
                {
                    "name": "bar",
                    "rating": 1,
                    "created": datetime.datetime(2018, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc),
                },
            ]

        @app.route("/serialization-error")
        def serialization_error() -> product_schema:
            return {"rating": "foo", "created": "bar"}

    @pytest.mark.parametrize(
        "path,method,test_input,expected_output,status_code",
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
                None,
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
    def test_schemas(self, client, path, method, test_input, expected_output, status_code):
        response = client.request(method, path, json=test_input)
        assert response.status_code == status_code, response.json()
        assert_recursive_contains(expected_output, response.json())
