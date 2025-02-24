import datetime
import typing as t
from unittest.mock import patch

import marshmallow
import pydantic
import pytest
import typesystem

from flama import exceptions
from flama.schemas.validation import output_validation


class TestCaseSchemaValidateOutput:
    @pytest.fixture(scope="function")
    def product_schema(self, app):
        from flama import schemas

        if schemas.lib == pydantic:

            def rating_validator(cls, x):
                assert x >= 0
                return x

            schema = pydantic.create_model(
                "Product",
                name=(str, ...),
                rating=(int, ...),
                created=(t.Optional[datetime.datetime], ...),
                __validators__={"rating": rating_validator},
            )
        elif schemas.lib == typesystem:
            schema = typesystem.Schema(
                title="Product",
                fields={
                    "name": typesystem.fields.String(title="name"),
                    "rating": typesystem.fields.Integer(title="rating", minimum=0),
                    "created": typesystem.fields.DateTime(title="created", allow_null=True),
                },
            )
        elif schemas.lib == marshmallow:
            schema = type(
                "Product",
                (marshmallow.Schema,),
                {
                    "name": marshmallow.fields.String(),
                    "rating": marshmallow.fields.Integer(validate=marshmallow.validate.Range(min=0)),
                    "created": marshmallow.fields.DateTime(allow_none=True),
                },
            )
        else:
            raise ValueError("Wrong schema lib")

        return schema

    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app, product_schema):
        @app.route("/product", methods=["GET"])
        @output_validation()
        def validate_product() -> product_schema:
            return {
                "name": "foo",
                "rating": 0,
                "created": datetime.datetime(2018, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc),
            }

        @app.route("/many-products", methods=["GET"])
        @output_validation()
        def validate_many_products() -> product_schema:
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

        @app.route("/validation-error")
        @output_validation()
        def output_validation_error() -> product_schema:
            return {"name": "foo", "rating": -1}

        class CustomValidationError(exceptions.ValidationError): ...

        @app.route("/custom-error")
        @output_validation(error_cls=CustomValidationError, error_status_code=502)
        def validate_custom_error() -> product_schema:
            return {"name": "foo", "rating": -1}

    @pytest.mark.parametrize(
        ["path", "status_code", "expected_response"],
        [
            pytest.param(
                "/product",
                200,
                {
                    "name": "foo",
                    "rating": 0,
                    "created": "2018-01-01T00:00:00+00:00",
                },
                id="single_item",
            ),
            pytest.param(
                "/many-products",
                200,
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
                id="many_items",
            ),
            pytest.param(
                "/validation-error",
                500,
                None,
                id="validation_error",
            ),
            pytest.param(
                "/custom-error",
                502,
                None,
                id="custom_error",
            ),
        ],
    )
    async def test_validation(self, client, path, status_code, expected_response):
        response = await client.get(path)
        assert response.status_code == status_code, response.json()
        if status_code == 200:
            assert response.json() == expected_response

    async def test_validation_uncontrolled_error(self, client):
        with patch(
            "flama.schemas.validation.schemas.adapter.dump",
            side_effect=[
                Exception,
                {
                    "detail": "Error serializing response before validation: Exception",
                    "error": "ValidationError",
                    "status_code": 500,
                },
            ],
        ):
            response = await client.get("/product")
            assert response.status_code == 500
            assert response.json() == {
                "detail": "Error serializing response before validation: Exception",
                "error": "ValidationError",
                "status_code": 500,
            }

    def test_function_without_return_schema(self):
        with pytest.raises(TypeError, match=r"Invalid return signature for function .*"):

            @output_validation()
            def foo(): ...
