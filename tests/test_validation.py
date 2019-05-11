import datetime

import pytest
from marshmallow import Schema, fields, validate
from starlette.testclient import TestClient

from flama import exceptions
from flama.applications.flama import Flama
from flama.validation import output_validation

utc = datetime.timezone.utc


class Product(Schema):
    name = fields.String(validate=validate.Length(max=10), required=True)
    rating = fields.Integer(missing=None, validate=validate.Range(min=0, max=100))
    created = fields.DateTime()


app = Flama()


@app.route("/product", methods=["GET"])
@output_validation()
def validate_product() -> Product:
    return {"name": "foo", "rating": 0, "created": datetime.datetime(2018, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)}


@app.route("/many-products", methods=["GET"])
@output_validation()
def validate_many_products() -> Product(many=True):
    return [
        {"name": "foo", "rating": 0, "created": datetime.datetime(2018, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)},
        {"name": "bar", "rating": 1, "created": datetime.datetime(2018, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)},
    ]


@app.route("/deserialization-error")
@output_validation()
def validate_deserialization_error() -> Product:
    return {"rating": "foo", "created": "bar"}


@app.route("/validation-error")
@output_validation()
def output_validation_error() -> Product:
    return {"foo": "bar"}


@app.route("/custom-error")
@output_validation(error_cls=exceptions.ValidationError, error_status_code=502)
def validate_custom_error() -> Product:
    return {"rating": "foo", "created": "bar"}


@pytest.fixture
def client():
    return TestClient(app)


class TestCaseMarshmallowSchemaValidateOutput:
    def test_single_item(self, client):
        response = client.get("/product")
        assert response.status_code == 200, response.json()
        assert response.json() == {
            "name": "foo",
            "rating": 0,
            "created": datetime.datetime(2018, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc).isoformat(),
        }

    def test_many_items(self, client):
        products = [
            {
                "name": "foo",
                "rating": 0,
                "created": datetime.datetime(2018, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc).isoformat(),
            },
            {
                "name": "bar",
                "rating": 1,
                "created": datetime.datetime(2018, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc).isoformat(),
            },
        ]
        response = client.get("/many-products")
        assert response.status_code == 200, response.json()
        body = response.json()
        assert body == products

    def test_deserialization_error(self, client):
        expected_response = {
            "detail": {"created": ['"bar" cannot be formatted as a datetime.'], "rating": ["Not a valid integer."]},
            "error": "OutputValidationError",
            "status_code": 500,
        }

        response = client.get("/deserialization-error")

        assert response.status_code == 500
        assert response.json() == expected_response

    def test_validation_error(self, client):
        expected_response = {
            "detail": {"name": ["Missing data for required field."]},
            "error": "OutputValidationError",
            "status_code": 500,
        }

        response = client.get("/validation-error")

        assert response.status_code == 500
        assert response.json() == expected_response

    def test_custom_error(self, client):
        expected_response = {
            "detail": {"created": ['"bar" cannot be formatted as a datetime.'], "rating": ["Not a valid integer."]},
            "error": "ValidationError",
            "status_code": 502,
        }

        response = client.get("/custom-error")

        assert response.status_code == 502
        assert response.json() == expected_response

    def test_function_without_return_schema(self):
        with pytest.raises(AssertionError, match="Return annotation must be a valid marshmallow schema"):

            @output_validation()
            def foo():
                ...
