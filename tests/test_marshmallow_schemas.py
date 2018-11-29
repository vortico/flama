import datetime

import pytest
from starlette.testclient import TestClient

import marshmallow
from marshmallow import Schema, fields, validate
from starlette_api.applications import Starlette

utc = datetime.timezone.utc


class Product(Schema):
    name = fields.String(validate=validate.Length(max=10))
    rating = fields.Integer(missing=None, validate=validate.Range(min=0, max=100))
    created = fields.DateTime()


class ReviewedProduct(Product):
    reviewer = fields.String(validate=validate.Length(max=20))


class Location(Schema):
    latitude = fields.Number(validate=validate.Range(max=90.0, min=-90.0))
    longitude = fields.Number(validate=validate.Range(max=180.0, min=-180.0))


class Place(Schema):
    location = fields.Nested(Location)
    name = fields.String(validate=validate.Length(max=100))


app = Starlette()


@app.route("/product", methods=["POST"])
def product_identity(product: Product) -> Product:
    return product


@app.route("/reviewed-product", methods=["POST"])
def reviewed_product_identity(reviewed_product: ReviewedProduct) -> ReviewedProduct:
    return reviewed_product


@app.route("/place", methods=["POST"])
def place_identity(place: Place) -> Place:
    return place


@app.route("/many-products", methods=["GET"])
def many_products() -> Product(many=True):
    return [
        {"name": "foo", "rating": 0, "created": datetime.datetime(2018, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)},
        {"name": "bar", "rating": 1, "created": datetime.datetime(2018, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)},
    ]


@app.route("/serialization-error")
def serialization_error() -> Product:
    return {"rating": "foo", "created": "bar"}


@pytest.fixture
def client():
    return TestClient(app)


class TestCaseMarshmallowSchema:
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
        with pytest.raises(marshmallow.exceptions.ValidationError):
            client.get("/serialization-error")
