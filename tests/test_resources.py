import asyncio
import typing
from unittest.mock import Mock, call

import databases
import marshmallow
import pytest
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy_utils import create_database, database_exists, drop_database
from starlette.testclient import TestClient

from starlette_api.applications import Starlette
from starlette_api.pagination import Paginator
from starlette_api.resources import Resource

DATABASE_URL = "sqlite:///test.db"


@pytest.yield_fixture(scope="module")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def database_metadata():
    return sqlalchemy.MetaData()


@pytest.fixture(scope="module")
async def database():
    async with databases.Database(DATABASE_URL) as db:
        yield db


@pytest.fixture(scope="module")
def schema():
    class PuppySchema(marshmallow.Schema):
        custom_id = marshmallow.fields.Integer(dump_only=True)
        name = marshmallow.fields.String()

    return PuppySchema


@pytest.fixture(scope="module")
def model(database_metadata):
    model_ = sqlalchemy.Table(
        "puppy",
        database_metadata,
        sqlalchemy.Column("custom_id", sqlalchemy.Integer, primary_key=True, autoincrement=True),
        sqlalchemy.Column("name", sqlalchemy.String),
    )

    return model_


class TestCaseBaseResource:
    @pytest.fixture(scope="function")
    def resource(self, model, schema, database):
        model_ = model
        schema_ = schema
        database_ = database

        class PuppyResource(metaclass=Resource):
            database = database_

            name = "puppy"
            verbose_name = "Puppy"

            model = model_
            input_schema = schema_
            output_schema = schema_

        return PuppyResource

    @pytest.fixture(scope="function")
    def app_mock(self):
        return Mock(spec=Starlette)

    def test_new_default_methods(self, resource, app_mock):
        expected_calls = [
            call(methods=["POST"], name="create", path="/puppy/", route=resource.create),
            call(methods=["GET"], name="retrieve", path="/puppy/{element_id}/", route=resource.retrieve),
            call(methods=["PUT"], name="update", path="/puppy/{element_id}/", route=resource.update),
            call(methods=["DELETE"], name="delete", path="/puppy/{element_id}/", route=resource.delete),
            call(methods=["GET"], name="list", path="/puppy/", route=resource.list),
        ]

        resource.add_routes(app_mock)

        assert hasattr(resource, "create")
        assert hasattr(resource, "retrieve")
        assert hasattr(resource, "update")
        assert hasattr(resource, "delete")
        assert hasattr(resource, "list")
        assert len(resource.routes) == 5
        assert app_mock.add_route.call_args_list == expected_calls

    def test_new_explicit_methods(self, model, schema, database, app_mock):
        model_ = model
        schema_ = schema
        database_ = database

        class PuppyResource(metaclass=Resource):
            database = database_

            name = "puppy"
            verbose_name = "Puppy"

            model = model_
            input_schema = schema_
            output_schema = schema_
            methods = ("create", "retrieve", "update", "delete", "list", "drop")

        expected_calls = [
            call(methods=["POST"], name="create", path="/puppy/", route=PuppyResource.create),
            call(methods=["GET"], name="retrieve", path="/puppy/{element_id}/", route=PuppyResource.retrieve),
            call(methods=["PUT"], name="update", path="/puppy/{element_id}/", route=PuppyResource.update),
            call(methods=["DELETE"], name="delete", path="/puppy/{element_id}/", route=PuppyResource.delete),
            call(methods=["GET"], name="list", path="/puppy/", route=PuppyResource.list),
            call(methods=["DELETE"], name="drop", path="/puppy/", route=PuppyResource.drop),
        ]

        PuppyResource.add_routes(app_mock)

        assert hasattr(PuppyResource, "create")
        assert hasattr(PuppyResource, "retrieve")
        assert hasattr(PuppyResource, "update")
        assert hasattr(PuppyResource, "delete")
        assert hasattr(PuppyResource, "list")
        assert hasattr(PuppyResource, "drop")
        assert len(PuppyResource.routes) == 6
        assert app_mock.add_route.call_args_list == expected_calls

    def test_override_method(self, resource):
        class SpecializedPuppyResource(resource):
            @classmethod
            def list(cls):
                raise ValueError

        assert hasattr(SpecializedPuppyResource, "create")
        assert hasattr(SpecializedPuppyResource, "retrieve")
        assert hasattr(SpecializedPuppyResource, "update")
        assert hasattr(SpecializedPuppyResource, "delete")
        assert hasattr(SpecializedPuppyResource, "list")
        assert len(SpecializedPuppyResource.routes) == 5
        with pytest.raises(ValueError):
            SpecializedPuppyResource.list()

    def test_new_no_database(self, model, schema):
        model_ = model
        schema_ = schema

        with pytest.raises(AttributeError, match=r"PuppyResource needs to define attribute 'database'"):

            class PuppyResource(metaclass=Resource):
                model = model_
                schema = schema_

    def test_new_no_model(self, schema, database):
        schema_ = schema
        database_ = database

        with pytest.raises(AttributeError, match=r"PuppyResource needs to define attribute 'model'"):

            class PuppyResource(metaclass=Resource):
                database = database_
                schema = schema_

    def test_new_no_name(self, model, schema, database):
        model_ = model
        schema_ = schema
        database_ = database

        class PuppyResource(metaclass=Resource):
            database = database_
            model = model_
            schema = schema_

        assert PuppyResource.name == "puppyresource"

    def test_new_wrong_name(self, model, schema, database):
        model_ = model
        schema_ = schema
        database_ = database

        with pytest.raises(AttributeError, match=r"Invalid resource name '123foo'"):

            class PuppyResource(metaclass=Resource):
                database = database_
                model = model_
                schema = schema_
                name = "123foo"

    def test_new_no_schema(self, model, database):
        model_ = model
        database_ = database

        with pytest.raises(
            AttributeError,
            match=r"PuppyResource needs to define attribute 'schema' or the pair 'input_schema' and 'output_schema'",
        ):

            class PuppyResource(metaclass=Resource):
                database = database_
                model = model_

    def test_new_no_input_schema(self, model, schema, database):
        model_ = model
        schema_ = schema
        database_ = database

        with pytest.raises(
            AttributeError,
            match=r"PuppyResource needs to define attribute 'schema' or the pair 'input_schema' and 'output_schema'",
        ):

            class PuppyResource(metaclass=Resource):
                database = database_
                model = model_
                output_schema = schema_

    def test_new_no_output_schema(self, model, schema, database):
        model_ = model
        schema_ = schema
        database_ = database

        with pytest.raises(
            AttributeError,
            match=r"PuppyResource needs to define attribute 'schema' or the pair 'input_schema' and 'output_schema'",
        ):

            class PuppyResource(metaclass=Resource):
                database = database_
                model = model_
                input_schema = schema_

    def test_new_wrong_methods(self, model, schema, database):
        model_ = model
        schema_ = schema
        database_ = database

        with pytest.raises(AttributeError, match=r'PuppyResource custom methods not found: "foo"'):

            class PuppyResource(metaclass=Resource):
                database = database_

                model = model_
                input_schema = schema_
                output_schema = schema_
                methods = ("foo",)

    def test_resource_model_no_pk(self, database_metadata, schema, database):
        model_ = sqlalchemy.Table("no_pk", database_metadata, sqlalchemy.Column("integer", sqlalchemy.Integer))
        schema_ = schema
        database_ = database

        with pytest.raises(AttributeError, match=r"PuppyResource model must define a single-column primary key"):

            class PuppyResource(metaclass=Resource):
                database = database_

                model = model_
                input_schema = schema_
                output_schema = schema_

    def test_resource_model_multicolumn_pk(self, database_metadata, schema, database):
        model_ = sqlalchemy.Table(
            "multicolumn_pk",
            database_metadata,
            sqlalchemy.Column("integer", sqlalchemy.Integer),
            sqlalchemy.Column("string", sqlalchemy.String),
            sqlalchemy.PrimaryKeyConstraint("integer", "string"),
        )
        schema_ = schema
        database_ = database

        with pytest.raises(AttributeError, match=r"PuppyResource model must define a single-column primary key"):

            class PuppyResource(metaclass=Resource):
                database = database_

                model = model_
                input_schema = schema_
                output_schema = schema_

    def test_resource_model_invalid_type_pk(self, database_metadata, schema, database):
        model_ = sqlalchemy.Table(
            "invalid_pk", database_metadata, sqlalchemy.Column("id", sqlalchemy.DateTime, primary_key=True)
        )
        schema_ = schema
        database_ = database

        with pytest.raises(
            AttributeError, match=r"PuppyResource model primary key must be Integer or String column type"
        ):

            class PuppyResource(metaclass=Resource):
                database = database_

                model = model_
                input_schema = schema_
                output_schema = schema_


class TestCaseResource:
    @pytest.fixture(scope="class")
    def resource(self, model, schema, database):
        model_ = model
        schema_ = schema
        database_ = database

        class PuppyResource(metaclass=Resource):
            database = database_

            name = "puppy"
            verbose_name = "Puppy"

            model = model_
            input_schema = schema_
            output_schema = schema_
            methods = ("create", "retrieve", "update", "delete", "list", "drop")

            @classmethod
            @Paginator.page_number
            async def list(
                cls, name: typing.Optional[str] = None, custom_id__le: typing.Optional[int] = None, **kwargs
            ) -> schema_(many=True):
                """
                description: Custom list method with filtering by name.
                """
                clauses = []

                if custom_id__le is not None:
                    clauses.append(cls.model.c.custom_id <= custom_id__le)

                filters = {}

                if name is not None:
                    filters["name"] = name

                return await cls._filter(*clauses, **filters)

        return PuppyResource

    @pytest.fixture(scope="class")
    def app(self, resource):
        app_ = Starlette()
        resource.add_routes(app_)
        return app_

    @pytest.fixture
    async def client(self, database_metadata, app):
        engine = create_engine(DATABASE_URL)
        assert not database_exists(DATABASE_URL), f"Database '{DATABASE_URL}' exists. Abort tests"
        create_database(DATABASE_URL)  # Create the test database.
        database_metadata.create_all(engine)  # Create the tables.
        yield TestClient(app)
        drop_database(DATABASE_URL)  # Drop the test database.

    @pytest.fixture
    def puppy(self):
        return {"name": "canna"}

    @pytest.fixture
    def another_puppy(self):
        return {"name": "sandy"}

    def test_create(self, client, puppy):
        expected_puppy_id = 1
        expected_result = [puppy.copy()]
        expected_result[0]["custom_id"] = expected_puppy_id

        # Successfully create a new record
        response = client.post("/puppy/", json=puppy)
        assert response.status_code == 201, response.json()
        created_puppy = response.json()
        assert created_puppy["id"] == expected_puppy_id

        # List all the existing records
        response = client.get("/puppy/")
        assert response.status_code == 200, response.json()
        assert response.json()["data"] == expected_result

    def test_retrieve(self, client, puppy):
        expected_puppy_id = 1
        expected_result = puppy.copy()
        expected_result["custom_id"] = expected_puppy_id

        # Successfully create a new record
        response = client.post("/puppy/", json=puppy)
        assert response.status_code == 201, response.json()
        created_puppy = response.json()
        assert created_puppy["id"] == expected_puppy_id

        # Retrieve same record
        response = client.get(f"/puppy/{created_puppy['id']}/")
        assert response.status_code == 200, response.json()
        assert response.json() == expected_result

    def test_retrieve_not_found(self, client):
        # Retrieve wrong record
        response = client.get("/puppy/42/")
        assert response.status_code == 404, response.json()

    def test_retrieve_wrong_id_type(self, client):
        # Retrieve wrong record
        response = client.get("/puppy/foo/")
        assert response.status_code == 400, response.json()

    def test_update(self, client, puppy, another_puppy):
        expected_puppy_id = 1
        expected_result = [another_puppy.copy()]
        expected_result[0]["custom_id"] = expected_puppy_id

        # Successfully create a new record
        response = client.post("/puppy/", json=puppy)
        assert response.status_code == 201, response.json()
        created_puppy = response.json()
        assert created_puppy["id"] == expected_puppy_id

        # Update record
        response = client.put(f"/puppy/{created_puppy['id']}/", json=another_puppy)
        assert response.status_code == 200, response.json()

        # List all the existing records
        response = client.get("/puppy/")
        assert response.status_code == 200, response.json()
        assert response.json()["data"] == expected_result

    def test_update_not_found(self, client, puppy):
        # Update wrong record
        response = client.put("/puppy/42/", json=puppy)
        assert response.status_code == 404, response.json()

    def test_update_wrong_id_type(self, client, puppy):
        # Update wrong record
        response = client.put("/puppy/foo/", json=puppy)
        assert response.status_code == 400, response.json()

    def test_delete(self, client, puppy):
        expected_puppy_id = 1
        expected_puppy = puppy.copy()
        expected_puppy["custom_id"] = expected_puppy_id

        # Successfully create a new record
        response = client.post("/puppy/", json=puppy)
        assert response.status_code == 201, response.json()
        created_puppy = response.json()
        assert created_puppy["id"] == expected_puppy_id

        # Retrieve same record
        response = client.get(f"/puppy/{created_puppy['id']}/")
        assert response.status_code == 200, response.json()
        assert response.json() == expected_puppy

        # Delete record
        response = client.delete(f"/puppy/{created_puppy['id']}/")
        assert response.status_code == 204, response.json()

        # Retrieve deleted record
        response = client.get(f"/puppy/{created_puppy['id']}/")
        assert response.status_code == 404, response.json()

    def test_delete_wrong_id_type(self, client):
        # Delete wrong record
        response = client.delete("/puppy/foo/")
        assert response.status_code == 400, response.json()

    def test_delete_not_found(self, client, puppy):
        # Delete wrong record
        response = client.delete("/puppy/42/", json=puppy)
        assert response.status_code == 404, response.json()

    def test_list(self, client, puppy, another_puppy):
        expected_puppy_id = 1
        expected_another_puppy_id = 2
        expected_result = [puppy.copy(), another_puppy.copy()]
        expected_result[0]["custom_id"] = expected_puppy_id
        expected_result[1]["custom_id"] = expected_another_puppy_id

        # Successfully create a new record
        response = client.post("/puppy/", json=puppy)
        assert response.status_code == 201, response.json()
        created_puppy = response.json()
        assert created_puppy["id"] == expected_puppy_id

        # Successfully create another new record
        response = client.post("/puppy/", json=another_puppy)
        assert response.status_code == 201, response.json()
        created_second_puppy = response.json()
        assert created_second_puppy["id"] == expected_another_puppy_id

        # List all the existing records
        response = client.get("/puppy/")
        assert response.status_code == 200, response.json()
        assert response.json()["data"] == expected_result

    def test_list_filter(self, client, puppy, another_puppy):
        expected_puppy_id = 1
        expected_another_puppy_id = 2
        expected_result = [puppy.copy()]
        expected_result[0]["custom_id"] = expected_puppy_id

        # Successfully create a new record
        response = client.post("/puppy/", json=puppy)
        assert response.status_code == 201, response.json()
        created_puppy = response.json()
        assert created_puppy["id"] == expected_puppy_id

        # Successfully create another new record
        response = client.post("/puppy/", json=another_puppy)
        assert response.status_code == 201, response.json()
        created_second_puppy = response.json()
        assert created_second_puppy["id"] == expected_another_puppy_id

        # Filter and found something
        response = client.get("/puppy/", params={"name": "canna", "custom_id__le": 1})
        assert response.status_code == 200, response.json()
        assert response.json()["data"] == expected_result

        # Filter without results
        response = client.get("/puppy/", params={"name": "canna", "custom_id__le": 0})
        assert response.status_code == 200, response.json()
        assert response.json()["data"] == []

    def test_drop(self, client, puppy, another_puppy):
        expected_puppy_id = 1
        expected_another_puppy_id = 2
        expected_result = [puppy.copy(), another_puppy.copy()]
        expected_result[0]["custom_id"] = expected_puppy_id
        expected_result[1]["custom_id"] = expected_another_puppy_id

        # Successfully create a new record
        response = client.post("/puppy/", json=puppy)
        assert response.status_code == 201, response.json()
        created_puppy = response.json()
        assert created_puppy["id"] == expected_puppy_id

        # Successfully create a new record
        response = client.post("/puppy/", json=another_puppy)
        assert response.status_code == 201, response.json()
        created_puppy = response.json()
        assert created_puppy["id"] == expected_another_puppy_id

        # List all the existing records
        response = client.get("/puppy/")
        assert response.status_code == 200, response.json()
        assert response.json()["data"] == expected_result

        # Drop collection
        response = client.delete("/puppy/", json=[puppy])
        assert response.status_code == 204, response.json()
        assert response.json() == {"deleted": 2}

        # List all the existing records
        response = client.get("/puppy/")
        assert response.status_code == 200, response.json()
        assert response.json()["data"] == []
