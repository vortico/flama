import datetime
import typing
import uuid

import pytest
import sqlalchemy
import typesystem
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy_utils import create_database, database_exists, drop_database
from starlette.testclient import TestClient

from flama import pagination
from flama.applications import Flama
from flama.resources.crud import CRUDListDropResource, CRUDListResource
from flama.resources.resource import resource_method
from tests.conftest import DATABASE_URL


@pytest.fixture
def app(app):
    # Remove schema and docs endpoint from base fixture
    return Flama(schema=None, docs=None, redoc=None)


@pytest.mark.skip
class TestCaseResource:
    @pytest.fixture(scope="function")
    def resource(self, puppy_model, puppy_schema, database):
        database_ = database

        class PuppyResource(metaclass=CRUDListDropResource):
            database = database_

            name = "puppy"
            verbose_name = "Puppy"

            model = puppy_model
            input_schema = puppy_schema
            output_schema = puppy_schema
            methods = ("create", "retrieve", "update", "delete", "list", "drop")

            @resource_method("/", methods=["GET"], name="puppy-list")
            @pagination.page_number(schema_name="PuppyResource")
            async def list(
                self, name: typing.Optional[str] = None, custom_id__le: typing.Optional[int] = None, **kwargs
            ) -> puppy_schema:
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

    @pytest.fixture(scope="function", autouse=True)
    def add_resources(self, app, resource):
        app.add_resource("/", resource)

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
        created_result = puppy.copy()
        created_result["custom_id"] = None
        expected_result = [puppy.copy()]
        expected_result[0]["custom_id"] = expected_puppy_id

        # Successfully create a new record
        response = client.post("/puppy/", json=puppy)
        assert response.status_code == 201, response.json()
        created_puppy = response.json()
        assert created_puppy == created_result

        # List all the existing records
        response = client.get("/puppy/")
        assert response.status_code == 200, response.json()
        assert response.json()["data"] == expected_result

    def test_retrieve(self, client, puppy):
        expected_puppy_id = 1
        created_result = puppy.copy()
        created_result["custom_id"] = None
        expected_result = puppy.copy()
        expected_result["custom_id"] = expected_puppy_id

        # Successfully create a new record
        response = client.post("/puppy/", json=puppy)
        assert response.status_code == 201, response.json()
        created_puppy = response.json()
        assert created_puppy == created_result

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
        created_result = puppy.copy()
        created_result["custom_id"] = None
        expected_puppy = another_puppy.copy()
        expected_puppy["custom_id"] = expected_puppy_id
        expected_result = [expected_puppy]

        # Successfully create a new record
        response = client.post("/puppy/", json=puppy)
        assert response.status_code == 201, response.json()
        created_puppy = response.json()
        assert created_puppy == created_result

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
        created_result = puppy.copy()
        created_result["custom_id"] = None
        expected_puppy = puppy.copy()
        expected_puppy["custom_id"] = expected_puppy_id

        # Successfully create a new record
        response = client.post("/puppy/", json=puppy)
        assert response.status_code == 201, response.json()
        created_puppy = response.json()
        assert created_puppy == created_result

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
        created_result_1 = puppy.copy()
        created_result_1["custom_id"] = None
        created_result_2 = another_puppy.copy()
        created_result_2["custom_id"] = None
        expected_result = [puppy.copy(), another_puppy.copy()]
        expected_result[0]["custom_id"] = expected_puppy_id
        expected_result[1]["custom_id"] = expected_another_puppy_id

        # Successfully create a new record
        response = client.post("/puppy/", json=puppy)
        assert response.status_code == 201, response.json()
        created_puppy = response.json()
        assert created_puppy == created_result_1

        # Successfully create another new record
        response = client.post("/puppy/", json=another_puppy)
        assert response.status_code == 201, response.json()
        created_second_puppy = response.json()
        assert created_second_puppy == created_result_2

        # List all the existing records
        response = client.get("/puppy/")
        assert response.status_code == 200, response.json()
        assert response.json()["data"] == expected_result

    def test_list_filter(self, client, puppy, another_puppy):
        expected_puppy_id = 1
        created_result_1 = puppy.copy()
        created_result_1["custom_id"] = None
        created_result_2 = another_puppy.copy()
        created_result_2["custom_id"] = None
        expected_result = [puppy.copy()]
        expected_result[0]["custom_id"] = expected_puppy_id

        # Successfully create a new record
        response = client.post("/puppy/", json=puppy)
        assert response.status_code == 201, response.json()
        created_puppy = response.json()
        assert created_puppy == created_result_1

        # Successfully create another new record
        response = client.post("/puppy/", json=another_puppy)
        assert response.status_code == 201, response.json()
        created_second_puppy = response.json()
        assert created_second_puppy == created_result_2

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
        created_result_1 = puppy.copy()
        created_result_1["custom_id"] = None
        created_result_2 = another_puppy.copy()
        created_result_2["custom_id"] = None
        expected_result = [puppy.copy(), another_puppy.copy()]
        expected_result[0]["custom_id"] = expected_puppy_id
        expected_result[1]["custom_id"] = expected_another_puppy_id

        # Successfully create a new record
        response = client.post("/puppy/", json=puppy)
        assert response.status_code == 201, response.json()
        created_puppy = response.json()
        assert created_puppy == created_result_1

        # Successfully create a new record
        response = client.post("/puppy/", json=another_puppy)
        assert response.status_code == 201, response.json()
        created_puppy = response.json()
        assert created_puppy == created_result_2

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

        schema_ = typesystem.Schema(
            fields={
                "custom_id": typesystem.fields.UUID(),
                "name": typesystem.fields.String(),
            }
        )

        @app.resource("/")
        class CustomUUIDResource(metaclass=CRUDListResource):
            database = database_
            model = model_
            schema = schema_

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

        schema_ = typesystem.Schema(
            fields={
                "custom_id": typesystem.fields.DateTime(),
                "name": typesystem.fields.String(),
            }
        )

        @app.resource("/")
        class CustomDatetimeResource(metaclass=CRUDListResource):
            database = database_
            model = model_
            schema = schema_

            name = "custom_id_datetime"

        now = datetime.datetime.utcnow().replace(microsecond=0, tzinfo=None)
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
