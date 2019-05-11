import asyncio
import datetime
import typing
import uuid

import databases
import marshmallow
import pytest
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy_utils import create_database, database_exists, drop_database
from starlette.testclient import TestClient

from flama.applications.flama import Flama
from flama.pagination import Paginator
from flama.resources import CRUDListDropResource, CRUDListResource, CRUDResource, resource_method
from flama.types.data_structures import Model, PrimaryKey

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

        class PuppyResource(metaclass=CRUDListResource):
            database = database_

            name = "puppy"
            verbose_name = "Puppy"

            model = model_
            schema = schema_

        return PuppyResource

    @pytest.fixture(scope="function")
    def app(self):
        return Flama(schema=None, docs=None, redoc=None)

    def test_meta_attributes(self, resource, model, database, schema):
        assert not hasattr(resource, "name")
        assert not hasattr(resource, "verbose_name")
        assert not hasattr(resource, "schema")
        assert hasattr(resource, "database")
        assert isinstance(getattr(resource, "database"), property)
        assert hasattr(resource, "model")
        assert isinstance(getattr(resource, "model"), property)
        assert hasattr(resource, "_meta")
        assert resource._meta.database == database
        assert resource._meta.name == "puppy"
        assert resource._meta.verbose_name == "Puppy"
        assert resource._meta.model == Model(table=model, primary_key=PrimaryKey(name="custom_id", type=int))
        assert resource._meta.input_schema == schema
        assert resource._meta.output_schema == schema
        assert resource._meta.columns == ["custom_id"]
        assert resource._meta.order == "custom_id"

    def test_meta_from_inheritance(self, model, schema, database):
        model_ = model
        schema_ = schema
        database_ = database

        class MetadataMixin:
            database = database_
            model = model_
            schema = schema_

        class PuppyResource(MetadataMixin, metaclass=CRUDListResource):
            pass

        assert PuppyResource._meta.name == "puppyresource"
        assert PuppyResource._meta.verbose_name == "puppyresource"
        assert PuppyResource._meta.order == "custom_id"
        assert PuppyResource._meta.columns == ["custom_id"]
        assert PuppyResource._meta.database == database_
        assert PuppyResource._meta.model == Model(table=model, primary_key=PrimaryKey(name="custom_id", type=int))
        assert PuppyResource._meta.input_schema == schema_
        assert PuppyResource._meta.output_schema == schema_

    def test_crud_resource(self, model, schema, database, app):
        model_ = model
        schema_ = schema
        database_ = database

        @app.resource("/")
        class PuppyResource(metaclass=CRUDResource):
            database = database_

            name = "puppy"
            verbose_name = "Puppy"

            model = model_
            schema = schema_

        expected_routes = [
            ("/puppy/", {"POST"}, "puppy-create"),
            ("/puppy/{element_id}/", {"GET", "HEAD"}, "puppy-retrieve"),
            ("/puppy/{element_id}/", {"PUT"}, "puppy-update"),
            ("/puppy/{element_id}/", {"DELETE"}, "puppy-delete"),
        ]

        assert [(i.path, i.methods, i.name) for i in app.routes] == expected_routes

    def test_crud_list_resource(self, model, schema, database, app):
        model_ = model
        schema_ = schema
        database_ = database

        class PuppyResource(metaclass=CRUDListResource):
            database = database_

            name = "puppy"
            verbose_name = "Puppy"

            model = model_
            schema = schema_

        resource = PuppyResource()

        expected_routes = [
            ("/puppy/", resource.create, {"POST"}, "puppy-create"),
            ("/puppy/{element_id}/", resource.retrieve, {"GET", "HEAD"}, "puppy-retrieve"),
            ("/puppy/{element_id}/", resource.update, {"PUT"}, "puppy-update"),
            ("/puppy/{element_id}/", resource.delete, {"DELETE"}, "puppy-delete"),
            ("/puppy/", resource.list, {"GET", "HEAD"}, "puppy-list"),
        ]

        app.add_resource("/", resource)

        assert hasattr(resource, "create")
        assert hasattr(resource, "retrieve")
        assert hasattr(resource, "update")
        assert hasattr(resource, "delete")
        assert hasattr(resource, "list")
        assert [(i.path, i.endpoint, i.methods, i.name) for i in app.routes] == expected_routes

    def test_crud_list_drop_resource(self, model, schema, database, app):
        model_ = model
        schema_ = schema
        database_ = database

        class PuppyResource(metaclass=CRUDListDropResource):
            database = database_

            name = "puppy"
            verbose_name = "Puppy"

            model = model_
            schema = schema_

        resource = PuppyResource()

        expected_routes = [
            ("/puppy/", resource.create, {"POST"}, "puppy-create"),
            ("/puppy/{element_id}/", resource.retrieve, {"GET", "HEAD"}, "puppy-retrieve"),
            ("/puppy/{element_id}/", resource.update, {"PUT"}, "puppy-update"),
            ("/puppy/{element_id}/", resource.delete, {"DELETE"}, "puppy-delete"),
            ("/puppy/", resource.list, {"GET", "HEAD"}, "puppy-list"),
            ("/puppy/", resource.drop, {"DELETE"}, "puppy-drop"),
        ]

        app.add_resource("/", resource)

        assert hasattr(resource, "create")
        assert hasattr(resource, "retrieve")
        assert hasattr(resource, "update")
        assert hasattr(resource, "delete")
        assert hasattr(resource, "list")
        assert hasattr(resource, "drop")
        assert [(i.path, i.endpoint, i.methods, i.name) for i in app.routes] == expected_routes

    def test_override_method(self, resource):
        class SpecializedPuppyResource(resource):
            @resource_method("/")
            def list(self):
                raise ValueError

        assert hasattr(SpecializedPuppyResource, "create")
        assert hasattr(SpecializedPuppyResource, "retrieve")
        assert hasattr(SpecializedPuppyResource, "update")
        assert hasattr(SpecializedPuppyResource, "delete")
        assert hasattr(SpecializedPuppyResource, "list")
        assert len(SpecializedPuppyResource.routes) == 5
        with pytest.raises(ValueError):
            SpecializedPuppyResource().list()

    def test_new_no_database(self, model, schema):
        model_ = model
        schema_ = schema

        with pytest.raises(AttributeError, match=r"PuppyResource needs to define attribute 'database'"):

            class PuppyResource(metaclass=CRUDListResource):
                model = model_
                schema = schema_

    def test_new_no_model(self, schema, database):
        schema_ = schema
        database_ = database

        with pytest.raises(AttributeError, match=r"PuppyResource needs to define attribute 'model'"):

            class PuppyResource(metaclass=CRUDListResource):
                database = database_
                schema = schema_

    def test_invalid_no_model(self, schema, database):
        schema_ = schema
        database_ = database

        with pytest.raises(
            AttributeError, match=r"PuppyResource model must be a valid SQLAlchemy Table instance or a Model instance"
        ):

            class PuppyResource(metaclass=CRUDListResource):
                database = database_
                schema = schema_
                model = None

    def test_new_no_name(self, model, schema, database):
        model_ = model
        schema_ = schema
        database_ = database

        class PuppyResource(metaclass=CRUDListResource):
            database = database_
            model = model_
            schema = schema_

        assert PuppyResource._meta.name == "puppyresource"

    def test_new_wrong_name(self, model, schema, database):
        model_ = model
        schema_ = schema
        database_ = database

        with pytest.raises(AttributeError, match=r"Invalid resource name '123foo'"):

            class PuppyResource(metaclass=CRUDListResource):
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

            class PuppyResource(metaclass=CRUDListResource):
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

            class PuppyResource(metaclass=CRUDListResource):
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

            class PuppyResource(metaclass=CRUDListResource):
                database = database_
                model = model_
                input_schema = schema_

    def test_resource_model_no_pk(self, database_metadata, schema, database):
        model_ = sqlalchemy.Table("no_pk", database_metadata, sqlalchemy.Column("integer", sqlalchemy.Integer))
        schema_ = schema
        database_ = database

        with pytest.raises(AttributeError, match=r"PuppyResource model must define a single-column primary key"):

            class PuppyResource(metaclass=CRUDListResource):
                database = database_

                model = model_
                schema = schema_

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

            class PuppyResource(metaclass=CRUDListResource):
                database = database_

                model = model_
                schema = schema_

    def test_resource_model_invalid_type_pk(self, database_metadata, schema, database):
        model_ = sqlalchemy.Table(
            "invalid_pk", database_metadata, sqlalchemy.Column("id", sqlalchemy.PickleType, primary_key=True)
        )
        schema_ = schema
        database_ = database

        with pytest.raises(
            AttributeError,
            match=r"PuppyResource model primary key must be any of Integer, String, Date, DateTime, UUID",
        ):

            class PuppyResource(metaclass=CRUDListResource):
                database = database_

                model = model_
                schema = schema_


class TestCaseResource:
    @pytest.fixture(scope="class")
    def resource(self, model, schema, database):
        model_ = model
        schema_ = schema
        database_ = database

        class PuppyResource(metaclass=CRUDListDropResource):
            database = database_

            name = "puppy"
            verbose_name = "Puppy"

            model = model_
            input_schema = schema_
            output_schema = schema_
            methods = ("create", "retrieve", "update", "delete", "list", "drop")

            @resource_method("/", methods=["GET"], name="puppy-list")
            @Paginator.page_number
            async def list(
                self, name: typing.Optional[str] = None, custom_id__le: typing.Optional[int] = None, **kwargs
            ) -> schema_(many=True):
                """
                description: Custom list method with filtering by name.
                """
                clauses = []

                if custom_id__le is not None:
                    clauses.append(self.model.c.custom_id <= custom_id__le)

                filters = {}

                if name is not None:
                    filters["name"] = name

                return await self._filter(*clauses, **filters)

        return PuppyResource()

    @pytest.fixture(scope="class")
    def app(self, resource):
        app_ = Flama()
        app_.add_resource("/", resource)
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
        assert created_puppy == puppy

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
        assert created_puppy == puppy

        # Retrieve same record
        response = client.get(f"/puppy/{expected_puppy_id}/")
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
        expected_puppy = another_puppy.copy()
        expected_puppy["custom_id"] = expected_puppy_id
        expected_result = [expected_puppy]

        # Successfully create a new record
        response = client.post("/puppy/", json=puppy)
        assert response.status_code == 201, response.json()
        created_puppy = response.json()
        assert created_puppy == puppy

        # Update record
        response = client.put(f"/puppy/{expected_puppy_id}/", json=another_puppy)
        assert response.status_code == 200, response.json()
        assert response.json() == expected_result[0]

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
        assert created_puppy == puppy

        # Retrieve same record
        response = client.get(f"/puppy/{expected_puppy_id}/")
        assert response.status_code == 200, response.json()
        assert response.json() == expected_puppy

        # Delete record
        response = client.delete(f"/puppy/{expected_puppy_id}/")
        assert response.status_code == 204, response.json()

        # Retrieve deleted record
        response = client.get(f"/puppy/{expected_puppy_id}/")
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
        assert created_puppy == puppy

        # Successfully create another new record
        response = client.post("/puppy/", json=another_puppy)
        assert response.status_code == 201, response.json()
        created_second_puppy = response.json()
        assert created_second_puppy == another_puppy

        # List all the existing records
        response = client.get("/puppy/")
        assert response.status_code == 200, response.json()
        assert response.json()["data"] == expected_result

    def test_list_filter(self, client, puppy, another_puppy):
        expected_puppy_id = 1
        expected_result = [puppy.copy()]
        expected_result[0]["custom_id"] = expected_puppy_id

        # Successfully create a new record
        response = client.post("/puppy/", json=puppy)
        assert response.status_code == 201, response.json()
        created_puppy = response.json()
        assert created_puppy == puppy

        # Successfully create another new record
        response = client.post("/puppy/", json=another_puppy)
        assert response.status_code == 201, response.json()
        created_second_puppy = response.json()
        assert created_second_puppy == another_puppy

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
        assert created_puppy == puppy

        # Successfully create a new record
        response = client.post("/puppy/", json=another_puppy)
        assert response.status_code == 201, response.json()
        created_puppy = response.json()
        assert created_puppy == another_puppy

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

    @pytest.mark.skipif(not DATABASE_URL.startswith("postgresql"), reason="Only valid for PostgreSQL backend")
    def test_id_uuid(self, database, database_metadata, client, app):
        database_ = database
        model_ = sqlalchemy.Table(
            "custom_id_uuid",
            database_metadata,
            sqlalchemy.Column("custom_id", postgresql.UUID, primary_key=True),
            sqlalchemy.Column("name", sqlalchemy.String),
        )
        database_metadata.create_all(create_engine(DATABASE_URL))

        class Schema(marshmallow.Schema):
            custom_id = marshmallow.fields.UUID()
            name = marshmallow.fields.String()

        @app.resource("/")
        class CustomUUIDResource(metaclass=CRUDListResource):
            database = database_
            model = model_
            schema = Schema

            name = "custom_id_uuid"

        data = {"custom_id": str(uuid.uuid4()), "name": "foo"}
        expected_result = data.copy()

        # Successfully create a new record
        response = client.post("/custom_id_uuid/", json=data)
        assert response.status_code == 201, response.content
        assert response.json() == expected_result, response.json()

        # Retrieve same record
        response = client.get(f"/custom_id_uuid/{data['custom_id']}/")
        assert response.status_code == 200, response.json()
        assert response.json() == expected_result

    def test_id_datetime(self, database, database_metadata, client, app):
        database_ = database
        model_ = sqlalchemy.Table(
            "custom_id_datetime",
            database_metadata,
            sqlalchemy.Column("custom_id", sqlalchemy.DateTime, primary_key=True),
            sqlalchemy.Column("name", sqlalchemy.String),
        )
        database_metadata.create_all(create_engine(DATABASE_URL))

        class Schema(marshmallow.Schema):
            custom_id = marshmallow.fields.DateTime()
            name = marshmallow.fields.String()

        @app.resource("/")
        class CustomDatetimeResource(metaclass=CRUDListResource):
            database = database_
            model = model_
            schema = Schema

            name = "custom_id_datetime"

        now = datetime.datetime.utcnow().replace(microsecond=0, tzinfo=datetime.timezone.utc)
        data = {"custom_id": now.isoformat(), "name": "foo"}
        expected_result = data.copy()

        # Successfully create a new record
        response = client.post("/custom_id_datetime/", json=data)
        assert response.status_code == 201, response.content
        assert response.json() == expected_result, response.json()

        # Retrieve same record
        response = client.get(f"/custom_id_datetime/{data['custom_id']}/")
        assert response.status_code == 200, response.json()
        assert response.json() == expected_result
