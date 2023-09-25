import datetime
import typing
import uuid

import marshmallow
import pydantic
import pytest
import sqlalchemy
import typesystem
import typesystem.fields
from sqlalchemy.dialects import postgresql

from flama.applications import Flama
from flama.resources.crud import CRUDListDropResourceType, CRUDListResourceType, CRUDResourceType
from flama.resources.rest import RESTResource
from flama.resources.routing import ResourceRoute, resource_method
from flama.resources.workers import FlamaWorker
from flama.sqlalchemy import SQLAlchemyModule
from tests.conftest import DATABASE_URL


@pytest.fixture
def app(app):
    # Remove schema and docs endpoint from base fixture
    return Flama(schema=None, docs=None, modules={SQLAlchemyModule("sqlite+aiosqlite://")})


@pytest.fixture(scope="function", autouse=True)
def add_resources(app, resource):
    app.resources.add_resource("/puppy/", resource)


@pytest.fixture
def puppy():
    return {"name": "canna"}


@pytest.fixture
def another_puppy():
    return {"name": "sandy"}


class TestCaseCRUDResource:
    @pytest.fixture
    def resource(self, puppy_model, puppy_schema):
        class PuppyResource(RESTResource, metaclass=CRUDResourceType):
            name = "puppy"
            verbose_name = "Puppy"

            model = puppy_model
            input_schema = puppy_schema
            output_schema = puppy_schema

        return PuppyResource()

    @pytest.fixture
    async def custom_id_datetime_model(self, app):
        table = sqlalchemy.Table(
            "custom_id_datetime",
            app.sqlalchemy.metadata,
            sqlalchemy.Column("custom_id", sqlalchemy.DateTime, primary_key=True),
            sqlalchemy.Column("name", sqlalchemy.String),
        )

        async with app.sqlalchemy.engine.begin() as connection:
            await connection.run_sync(app.sqlalchemy.metadata.create_all, tables=[table])

        yield table

        async with app.sqlalchemy.engine.begin() as connection:
            await connection.run_sync(app.sqlalchemy.metadata.drop_all, tables=[table])

    @pytest.fixture
    def custom_id_datetime_schema(self, app):
        from flama import schemas

        if schemas.lib == pydantic:
            schema_ = pydantic.create_model("CustomIDDatetime", custom_id=(datetime.datetime, ...), name=(str, ...))
        elif schemas.lib == typesystem:
            schema_ = typesystem.Schema(
                title="CustomIDDatetime",
                fields={
                    "custom_id": typesystem.fields.DateTime(),
                    "name": typesystem.fields.String(),
                },
            )
        elif schemas.lib == marshmallow:
            schema_ = type(
                "CustomIDDatetime",
                (marshmallow.Schema,),
                {
                    "custom_id": marshmallow.fields.DateTime(),
                    "name": marshmallow.fields.String(),
                },
            )
        else:
            raise ValueError("Wrong schema lib")

        app.schema.schemas["CustomIDDatetime"] = schema_
        return schema_

    @pytest.fixture
    def custom_id_datetime_resource(self, custom_id_datetime_model, custom_id_datetime_schema):
        class CustomUUIDResource(RESTResource, metaclass=CRUDListResourceType):
            model = custom_id_datetime_model
            schema = custom_id_datetime_schema

            name = "custom_id_datetime"

        return CustomUUIDResource

    @pytest.fixture
    async def custom_id_uuid_model(self, app):
        table = sqlalchemy.Table(
            "custom_id_uuid",
            app.database.metadata,
            sqlalchemy.Column("custom_id", postgresql.UUID, primary_key=True),
            sqlalchemy.Column("name", sqlalchemy.String),
        )

        async with app.database.engine.begin() as connection:
            await connection.run_sync(app.database.metadata.create_all, tables=[table])

        yield table

        async with app.database.engine.begin() as connection:
            await connection.run_sync(app.database.metadata.drop_all, tables=[table])

    @pytest.fixture
    def custom_id_uuid_schema(self, app):
        from flama import schemas

        if schemas.lib == pydantic:
            schema_ = pydantic.create_model("CustomIDUUID", custom_id=(uuid.UUID, ...), name=(str, ...))
        elif schemas.lib == typesystem:
            schema_ = typesystem.Schema(
                title="CustomIDUUID",
                fields={
                    "custom_id": typesystem.fields.UUID(),
                    "name": typesystem.fields.String(),
                },
            )
        elif schemas.lib == marshmallow:
            schema_ = type(
                "CustomIDUUID",
                (marshmallow.Schema,),
                {
                    "custom_id": marshmallow.fields.UUID(),
                    "name": marshmallow.fields.String(),
                },
            )
        else:
            raise ValueError("Wrong schema lib")

        app.schema.schemas["CustomIDUUID"] = schema_
        return schema_

    @pytest.fixture
    def custom_id_uuid_resource(self, custom_id_uuid_model, custom_id_uuid_schema):
        class CustomUUIDResource(RESTResource, metaclass=CRUDListResourceType):
            model = custom_id_uuid_model
            schema = custom_id_uuid_schema

            name = "custom_id_uuid"

        return CustomUUIDResource

    def test_crud_resource(self, resource, puppy_model, puppy_schema, app):
        expected_routes = [
            ("/", resource.create, {"POST"}, "puppy-create"),
            ("/{element_id}/", resource.retrieve, {"GET", "HEAD"}, "puppy-retrieve"),
            ("/{element_id}/", resource.update, {"PUT"}, "puppy-update"),
            ("/{element_id}/", resource.delete, {"DELETE"}, "puppy-delete"),
        ]

        assert len(app.routes) == 1
        assert isinstance(app.routes[0], ResourceRoute)
        resource_route = app.routes[0]
        assert [(i.path, i.endpoint, i.methods, i.name) for i in resource_route.routes] == expected_routes

    async def test_create(self, client, puppy):
        expected_puppy_id = 1
        expected_puppy = puppy.copy()
        expected_puppy["custom_id"] = expected_puppy_id

        # Successfully create a new record
        response = await client.request("post", "/puppy/", json=puppy)
        assert response.status_code == 201, response.json()
        created_puppy = response.json()
        assert created_puppy == expected_puppy

        # List all the existing records
        response = await client.request("get", f"/puppy/{expected_puppy_id}/")
        assert response.status_code == 200, response.json()
        assert response.json() == expected_puppy

    async def test_retrieve(self, client, puppy):
        expected_puppy_id = 1
        expected_result = puppy.copy()
        expected_result["custom_id"] = expected_puppy_id

        # Successfully create a new record
        response = await client.request("post", "/puppy/", json=puppy)
        assert response.status_code == 201, response.json()
        created_puppy = response.json()
        assert created_puppy == expected_result

        # Retrieve same record
        response = await client.request("get", f"/puppy/{expected_puppy_id}/")
        assert response.status_code == 200, response.json()
        assert response.json() == expected_result

    async def test_retrieve_not_found(self, client):
        # Retrieve wrong record
        response = await client.request("get", "/puppy/42/")
        assert response.status_code == 404, response.json()

    async def test_retrieve_wrong_id_type(self, client):
        # Retrieve wrong record
        response = await client.request("get", "/puppy/foo/")
        assert response.status_code == 400, response.json()

    async def test_update(self, client, puppy, another_puppy):
        expected_puppy_id = 1
        created_puppy = puppy.copy()
        created_puppy["custom_id"] = expected_puppy_id
        expected_puppy = another_puppy.copy()
        expected_puppy["custom_id"] = expected_puppy_id

        # Successfully create a new record
        response = await client.request("post", "/puppy/", json=puppy)
        assert response.status_code == 201, response.json()
        created_puppy = response.json()
        assert created_puppy == created_puppy

        # Update record
        response = await client.request("put", f"/puppy/{expected_puppy_id}/", json=another_puppy)
        assert response.status_code == 200, response.json()
        assert response.json() == expected_puppy

        # List all the existing records
        response = await client.request("get", f"/puppy/{expected_puppy_id}/")
        assert response.status_code == 200, response.json()
        assert response.json() == expected_puppy

    async def test_update_not_found(self, client, puppy):
        # Update wrong record
        response = await client.request("put", "/puppy/42/", json=puppy)
        assert response.status_code == 404, response.json()

    async def test_update_wrong_id_type(self, client, puppy):
        # Update wrong record
        response = await client.request("put", "/puppy/foo/", json=puppy)
        assert response.status_code == 400, response.json()

    async def test_delete(self, client, puppy):
        expected_puppy_id = 1
        expected_puppy = puppy.copy()
        expected_puppy["custom_id"] = expected_puppy_id

        # Successfully create a new record
        response = await client.request("post", "/puppy/", json=puppy)
        assert response.status_code == 201, response.json()
        created_puppy = response.json()
        assert created_puppy == expected_puppy

        # Retrieve same record
        response = await client.request("get", f"/puppy/{expected_puppy_id}/")
        assert response.status_code == 200, response.json()
        assert response.json() == expected_puppy

        # Delete record
        response = await client.request("delete", f"/puppy/{expected_puppy_id}/")
        assert response.status_code == 204, response.json()

        # Retrieve deleted record
        response = await client.request("get", f"/puppy/{expected_puppy_id}/")
        assert response.status_code == 404, response.json()

    async def test_delete_wrong_id_type(self, client):
        # Delete wrong record
        response = await client.request("delete", "/puppy/foo/")
        assert response.status_code == 400, response.json()

    async def test_delete_not_found(self, client, puppy):
        # Delete wrong record
        response = await client.request("delete", "/puppy/42/", json=puppy)
        assert response.status_code == 404, response.json()

    @pytest.mark.skipif(not DATABASE_URL.startswith("postgresql"), reason="Only valid for PostgreSQL backend")
    async def test_id_uuid(self, app, client, custom_id_uuid_resource):
        app.resources.add_resource("/custom_id_datetime/", custom_id_uuid_resource)

        data = {"custom_id": str(uuid.uuid4()), "name": "foo"}
        expected_result = data.copy()

        # Successfully create a new record
        response = await client.request("post", "/custom_id_uuid/", json=data)
        assert response.status_code == 201, response.content
        assert response.json() == expected_result, response.json()

        # Retrieve same record
        response = await client.request("get", f"/custom_id_uuid/{data['custom_id']}/")
        assert response.status_code == 200, response.json()
        assert response.json() == expected_result

    async def test_id_datetime(self, client, app, custom_id_datetime_resource):
        app.resources.add_resource("/custom_id_datetime/", custom_id_datetime_resource)

        data = {"custom_id": "2018-01-01T00:00:00", "name": "foo"}
        expected_result = data.copy()

        # Successfully create a new record
        response = await client.request("post", "/custom_id_datetime/", json=data)
        assert response.status_code == 201, response.content
        assert response.json() == expected_result, response.json()

        # Retrieve same record
        response = await client.request("get", f"/custom_id_datetime/{data['custom_id']}/")
        assert response.status_code == 200, response.json()
        assert response.json() == expected_result


class TestCaseCRUDListResource:
    @pytest.fixture
    def resource(self, puppy_model, puppy_schema):
        class PuppyResource(RESTResource, metaclass=CRUDListResourceType):
            name = "puppy"
            verbose_name = "Puppy"

            model = puppy_model
            input_schema = puppy_schema
            output_schema = puppy_schema

            @resource_method("/", methods=["GET"], name="puppy-list", pagination="page_number")
            async def list(
                self,
                worker: FlamaWorker,
                name: typing.Optional[str] = None,
                custom_id__le: typing.Optional[int] = None,
                **kwargs,
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

                async with worker:
                    return await worker.repositories[self._meta.name].list(*clauses, **filters)

        return PuppyResource()

    def test_crud_list_resource(self, resource, puppy_model, puppy_schema, app):
        expected_routes = [
            ("/", resource.list, {"GET", "HEAD"}, "puppy-list"),
            ("/", resource.create, {"POST"}, "puppy-create"),
            ("/{element_id}/", resource.retrieve, {"GET", "HEAD"}, "puppy-retrieve"),
            ("/{element_id}/", resource.update, {"PUT"}, "puppy-update"),
            ("/{element_id}/", resource.delete, {"DELETE"}, "puppy-delete"),
        ]

        assert hasattr(resource, "create")
        assert hasattr(resource, "retrieve")
        assert hasattr(resource, "update")
        assert hasattr(resource, "delete")
        assert hasattr(resource, "list")
        assert len(app.routes) == 1
        assert isinstance(app.routes[0], ResourceRoute)
        resource_route = app.routes[0]
        assert [(i.path, i.endpoint, i.methods, i.name) for i in resource_route.routes] == expected_routes

    def test_override_method(self, app, resource):
        class SpecializedPuppyResource(type(resource)):
            @resource_method("/")
            def list(self):
                return ["foo", "bar"]

        assert hasattr(SpecializedPuppyResource, "create")
        assert hasattr(SpecializedPuppyResource, "retrieve")
        assert hasattr(SpecializedPuppyResource, "update")
        assert hasattr(SpecializedPuppyResource, "delete")
        assert hasattr(SpecializedPuppyResource, "list")
        assert len(SpecializedPuppyResource.routes) == 5

        assert SpecializedPuppyResource().list() == ["foo", "bar"]

    async def test_list(self, client, puppy, another_puppy):
        expected_puppy_id = 1
        expected_another_puppy_id = 2
        created_result_1 = puppy.copy()
        created_result_1["custom_id"] = expected_puppy_id
        created_result_2 = another_puppy.copy()
        created_result_2["custom_id"] = expected_another_puppy_id
        expected_result = [puppy.copy(), another_puppy.copy()]
        expected_result[0]["custom_id"] = expected_puppy_id
        expected_result[1]["custom_id"] = expected_another_puppy_id

        # Successfully create a new record
        response = await client.request("post", "/puppy/", json=puppy)
        assert response.status_code == 201, response.json()
        created_puppy = response.json()
        assert created_puppy == created_result_1

        # Successfully create another new record
        response = await client.request("post", "/puppy/", json=another_puppy)
        assert response.status_code == 201, response.json()
        created_second_puppy = response.json()
        assert created_second_puppy == created_result_2

        # List all the existing records
        response = await client.request("get", "/puppy/")
        assert response.status_code == 200, response.json()
        assert response.json()["data"] == expected_result

    async def test_list_filter(self, client, puppy, another_puppy):
        expected_puppy_id = 1
        expected_another_puppy_id = 2
        created_result_1 = puppy.copy()
        created_result_1["custom_id"] = expected_puppy_id
        created_result_2 = another_puppy.copy()
        created_result_2["custom_id"] = expected_another_puppy_id
        expected_result = [puppy.copy()]
        expected_result[0]["custom_id"] = expected_puppy_id

        # Successfully create a new record
        response = await client.request("post", "/puppy/", json=puppy)
        assert response.status_code == 201, response.json()
        created_puppy = response.json()
        assert created_puppy == created_result_1

        # Successfully create another new record
        response = await client.request("post", "/puppy/", json=another_puppy)
        assert response.status_code == 201, response.json()
        created_second_puppy = response.json()
        assert created_second_puppy == created_result_2

        # Filter and found something
        response = await client.request("get", "/puppy/", params={"name": "canna", "custom_id__le": 1})
        assert response.status_code == 200, response.json()
        assert response.json()["data"] == expected_result

        # Filter without results
        response = await client.request("get", "/puppy/", params={"name": "canna", "custom_id__le": 0})
        assert response.status_code == 200, response.json()
        assert response.json()["data"] == []


class TestCaseCRUDListDropResource:
    @pytest.fixture
    def resource(self, puppy_model, puppy_schema):
        class PuppyResource(RESTResource, metaclass=CRUDListDropResourceType):
            name = "puppy"
            verbose_name = "Puppy"

            model = puppy_model
            input_schema = puppy_schema
            output_schema = puppy_schema

        return PuppyResource()

    def test_crud_list_drop_resource(self, resource, puppy_model, puppy_schema, app):
        expected_routes = [
            ("/", resource.create, {"POST"}, "puppy-create"),
            ("/{element_id}/", resource.retrieve, {"GET", "HEAD"}, "puppy-retrieve"),
            ("/{element_id}/", resource.update, {"PUT"}, "puppy-update"),
            ("/{element_id}/", resource.delete, {"DELETE"}, "puppy-delete"),
            ("/", resource.list, {"GET", "HEAD"}, "puppy-list"),
            ("/", resource.drop, {"DELETE"}, "puppy-drop"),
        ]

        assert hasattr(resource, "create")
        assert hasattr(resource, "retrieve")
        assert hasattr(resource, "update")
        assert hasattr(resource, "delete")
        assert hasattr(resource, "list")
        assert hasattr(resource, "drop")
        assert len(app.routes) == 1
        assert isinstance(app.routes[0], ResourceRoute)
        resource_route = app.routes[0]
        assert [(i.path, i.endpoint, i.methods, i.name) for i in resource_route.routes] == expected_routes

    async def test_drop(self, client, puppy, another_puppy):
        expected_puppy_id = 1
        expected_another_puppy_id = 2
        created_result_1 = puppy.copy()
        created_result_1["custom_id"] = expected_puppy_id
        created_result_2 = another_puppy.copy()
        created_result_2["custom_id"] = expected_another_puppy_id
        expected_result = [puppy.copy(), another_puppy.copy()]
        expected_result[0]["custom_id"] = expected_puppy_id
        expected_result[1]["custom_id"] = expected_another_puppy_id

        # Successfully create a new record
        response = await client.request("post", "/puppy/", json=puppy)
        assert response.status_code == 201, response.json()
        created_puppy = response.json()
        assert created_puppy == created_result_1

        # Successfully create a new record
        response = await client.request("post", "/puppy/", json=another_puppy)
        assert response.status_code == 201, response.json()
        created_puppy = response.json()
        assert created_puppy == created_result_2

        # List all the existing records
        response = await client.request("get", "/puppy/")
        assert response.status_code == 200, response.json()
        assert response.json()["data"] == expected_result

        # Drop collection
        response = await client.request("delete", "/puppy/", json=[puppy])
        assert response.status_code == 204, response.json()
        assert response.json() == {"deleted": 2}

        # List all the existing records
        response = await client.request("get", "/puppy/")
        assert response.status_code == 200, response.json()
        assert response.json()["data"] == []
