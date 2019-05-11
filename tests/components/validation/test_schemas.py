import datetime

import marshmallow
import pytest
from marshmallow import ValidationError, validate
from starlette.testclient import TestClient

from flama.applications.flama import Flama

utc = datetime.timezone.utc


class Product(marshmallow.Schema):
    name = marshmallow.fields.String(validate=validate.Length(max=10))
    rating = marshmallow.fields.Integer(missing=None, validate=validate.Range(min=0, max=100))
    created = marshmallow.fields.DateTime()


class ReviewedProduct(Product):
    reviewer = marshmallow.fields.String(validate=validate.Length(max=20))


class Location(marshmallow.Schema):
    latitude = marshmallow.fields.Number(validate=validate.Range(max=90.0, min=-90.0))
    longitude = marshmallow.fields.Number(validate=validate.Range(max=180.0, min=-180.0))


class Place(marshmallow.Schema):
    location = marshmallow.fields.Nested(Location)
    name = marshmallow.fields.String(validate=validate.Length(max=100))


class TestCaseSchemaValidation:
    @pytest.fixture(scope="class")
    def app(self):
        app_ = Flama()

        @app_.route("/product", methods=["POST"])
        def product_identity(product: Product) -> Product:
            return product

        @app_.route("/reviewed-product", methods=["POST"])
        def reviewed_product_identity(reviewed_product: ReviewedProduct) -> ReviewedProduct:
            return reviewed_product

        @app_.route("/place", methods=["POST"])
        def place_identity(place: Place) -> Place:
            return place

        @app_.route("/many-products", methods=["GET"])
        def many_products() -> Product(many=True):
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

        @app_.route("/serialization-error")
        def serialization_error() -> Product:
            return {"rating": "foo", "created": "bar"}

        return app_

    @pytest.fixture(scope="function")
    def client(self, app):
        return TestClient(app)

    def test_simple_schema(self, client):
        product = {
            "name": "foo",
            "rating": 0,
            "created": datetime.datetime(2018, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc).isoformat(),
        }
        response = client.post("/product", json=product)
        assert response.status_code == 200, response.json()
        body = response.json()
        assert body == product

    def test_inherited_schema(self, client):
        product = {
            "name": "foo",
            "rating": 0,
            "created": datetime.datetime(2018, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc).isoformat(),
            "reviewer": "bar",
        }
        response = client.post("/reviewed-product", json=product)
        assert response.status_code == 200, response.json()
        body = response.json()
        assert body == product

    def test_nested_schema(self, client):
        place = {"name": "foo", "location": {"latitude": 0.0, "longitude": 0.0}}
        response = client.post("/place", json=place)
        assert response.status_code == 200, response.json()
        body = response.json()
        assert body == place

    def test_schema_instance(self, client):
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

    def test_serialization_error(self, client):
        with pytest.raises(ValidationError):
            client.get("/serialization-error")
