import datetime
import typing as t
import uuid

import marshmallow
import pydantic
import pytest
import sqlalchemy
import typesystem
import typesystem.fields
from sqlalchemy.dialects import postgresql

from flama.applications import Flama
from flama.resources.crud import CRUDResource
from flama.resources.routing import ResourceRoute
from flama.resources.workers import FlamaWorker
from flama.schemas import SchemaMetadata, SchemaType
from flama.sqlalchemy import SQLAlchemyModule
from tests.conftest import DATABASE_URL


@pytest.fixture(scope="function")
def app(app):
    # Remove schema and docs endpoint from base fixture
    return Flama(
        schema=None, docs=None, modules={SQLAlchemyModule("sqlite+aiosqlite://")}, schema_library=app.schema_library
    )


@pytest.fixture(scope="function", autouse=True)
def add_resources(app, resource):
    app.resources.add_resource("/puppy/", resource)

    yield

    app.resources.remove_repository(resource._meta.name)


@pytest.fixture(scope="function")
def puppy():
    return {"name": "canna", "age": 2, "owner": "Perdy"}


@pytest.fixture(scope="function")
def another_puppy():
    return {"name": "sandy", "age": 6, "owner": "Perdy"}


class TestCaseCRUDResource:
    @pytest.fixture(scope="function")
    def resource(self, app: Flama, puppy_model, puppy_schema):
        class PuppyResource(CRUDResource):
            name = "puppy"
            verbose_name = "Puppy"

            model = puppy_model
            input_schema = puppy_schema
            output_schema = puppy_schema

            @app.resources.method("/", methods=["GET"], name="list", pagination="page_number")
            async def list(
                self,
                worker: FlamaWorker,
                order_by: t.Optional[str] = None,
                order_direction: str = "asc",
                name: t.Optional[str] = None,
                custom_id__le: t.Optional[int] = None,
                **kwargs,
            ) -> t.Annotated[list[SchemaType], SchemaMetadata(puppy_schema)]:
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
                    return [
                        x
                        async for x in worker.repositories[self._meta.name].list(
                            *clauses,
                            order_by=order_by,
                            order_direction=t.cast(t.Literal["asc", "desc"], order_direction),
                            **filters,
                        )
                    ]

        return PuppyResource()

    @pytest.fixture(scope="function")
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

    @pytest.fixture(scope="function")
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

        return schema_

    @pytest.fixture(scope="function")
    def custom_id_datetime_resource(self, custom_id_datetime_model, custom_id_datetime_schema, app):
        class CustomUUIDResource(CRUDResource):
            model = custom_id_datetime_model
            schema = custom_id_datetime_schema

            name = "custom_id_datetime"

        app.resources.add_resource("/custom_id_datetime/", CustomUUIDResource)

        yield CustomUUIDResource

        app.resources.remove_repository(CustomUUIDResource._meta.name)

    @pytest.fixture(scope="function")
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

    @pytest.fixture(scope="function")
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

        return schema_

    @pytest.fixture(scope="function")
    def custom_id_uuid_resource(self, custom_id_uuid_model, custom_id_uuid_schema, app):
        class CustomUUIDResource(CRUDResource):
            model = custom_id_uuid_model
            schema = custom_id_uuid_schema

            name = "custom_id_uuid"

        app.resources.add_resource("/custom_id_datetime/", CustomUUIDResource)

        yield CustomUUIDResource

        del app.resources.worker._repositories[CustomUUIDResource._meta.name]

    def test_crud_resource(self, resource, app):
        expected_routes = [
            ("/", resource.list, {"GET", "HEAD"}, "list"),
            ("/", resource.create, {"POST"}, "create"),
            ("/{resource_id}/", resource.retrieve, {"GET", "HEAD"}, "retrieve"),
            ("/{resource_id}/", resource.update, {"PUT"}, "update"),
            ("/{resource_id}/", resource.partial_update, {"PATCH"}, "partial-update"),
            ("/{resource_id}/", resource.delete, {"DELETE"}, "delete"),
            ("/", resource.replace, {"PUT"}, "replace"),
            ("/", resource.partial_replace, {"PATCH"}, "partial-replace"),
            ("/", resource.drop, {"DELETE"}, "drop"),
        ]

        assert hasattr(resource, "create")
        assert hasattr(resource, "retrieve")
        assert hasattr(resource, "update")
        assert hasattr(resource, "partial_update")
        assert hasattr(resource, "delete")
        assert hasattr(resource, "list")
        assert hasattr(resource, "replace")
        assert hasattr(resource, "partial_replace")
        assert hasattr(resource, "drop")
        assert len(app.routes) == 1
        assert isinstance(app.routes[0], ResourceRoute)
        resource_route = app.routes[0]
        assert [
            (i.path, i.endpoint.__wrapped__ if i.endpoint._meta.pagination else i.endpoint, i.methods, i.name)
            for i in resource_route.routes
        ] == expected_routes

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

    async def test_create_already_exists(self, client, puppy):
        expected_puppy_id = 1
        expected_puppy = puppy.copy()
        expected_puppy["custom_id"] = expected_puppy_id

        # Create a new record
        response = await client.request("post", "/puppy/", json=puppy)
        assert response.status_code == 201, response.json()
        created_puppy = response.json()
        assert created_puppy == expected_puppy

        # Fails if resource exists
        response = await client.request("post", "/puppy/", json=expected_puppy)
        assert response.status_code == 400, response.json()

    async def test_create_wrong_data(self, client, puppy):
        wrong_puppy = puppy.copy()
        wrong_puppy["age"] = "wrong"

        # Fails if wrong input data
        response = await client.request("post", "/puppy/", json=wrong_puppy)
        assert response.status_code == 400, response.json()

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
        another_puppy.pop("owner")
        expected_puppy["custom_id"] = expected_puppy_id
        expected_puppy["owner"] = None  # Replaced by default

        # Successfully create a new record
        response = await client.request("post", "/puppy/", json=puppy)
        assert response.status_code == 201, response.json()
        assert response.json() == created_puppy

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

    async def test_update_wrong_data(self, client, puppy):
        expected_puppy_id = 1
        created_puppy = puppy.copy()
        created_puppy["custom_id"] = expected_puppy_id
        wrong_puppy = puppy.copy()
        wrong_puppy["age"] = "wrong"

        # Successfully create a new record
        response = await client.request("post", "/puppy/", json=puppy)
        assert response.status_code == 201, response.json()
        assert response.json() == created_puppy

        # Update record
        response = await client.request("put", f"/puppy/{expected_puppy_id}/", json=wrong_puppy)
        assert response.status_code == 400, response.json()

    async def test_partial_update(self, client, puppy, another_puppy):
        expected_puppy_id = 1
        created_puppy = puppy.copy()
        created_puppy["custom_id"] = expected_puppy_id
        expected_puppy = another_puppy.copy()
        another_puppy.pop("owner")
        expected_puppy["custom_id"] = expected_puppy_id
        expected_puppy["owner"] = created_puppy["owner"]  # Not replaced

        # Successfully create a new record
        response = await client.request("post", "/puppy/", json=puppy)
        assert response.status_code == 201, response.json()
        assert response.json() == created_puppy

        # Update record
        response = await client.request("patch", f"/puppy/{expected_puppy_id}/", json=another_puppy)
        assert response.status_code == 200, response.json()
        assert response.json() == expected_puppy

        # List all the existing records
        response = await client.request("get", f"/puppy/{expected_puppy_id}/")
        assert response.status_code == 200, response.json()
        assert response.json() == expected_puppy

    async def test_partial_update_not_found(self, client, puppy):
        # Update wrong record
        response = await client.request("patch", "/puppy/42/", json=puppy)
        assert response.status_code == 404, response.json()

    async def test_partial_update_wrong_id_type(self, client, puppy):
        # Update wrong record
        response = await client.request("patch", "/puppy/foo/", json=puppy)
        assert response.status_code == 400, response.json()

    async def test_partial_update_wrong_data(self, client, puppy):
        expected_puppy_id = 1
        created_puppy = puppy.copy()
        created_puppy["custom_id"] = expected_puppy_id
        wrong_puppy = puppy.copy()
        wrong_puppy["age"] = "wrong"

        # Successfully create a new record
        response = await client.request("post", "/puppy/", json=puppy)
        assert response.status_code == 201, response.json()
        assert response.json() == created_puppy

        # Update record
        response = await client.request("patch", f"/puppy/{expected_puppy_id}/", json=wrong_puppy)
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

    async def test_list(self, client, puppy, another_puppy):
        # Successfully create a new record
        response = await client.request("post", "/puppy/", json=puppy)
        assert response.status_code == 201, response.json()

        # Successfully create another new record
        response = await client.request("post", "/puppy/", json=another_puppy)
        assert response.status_code == 201, response.json()

        # List all the existing records
        response = await client.request("get", "/puppy/")
        assert response.status_code == 200, response.json()
        assert response.json()["data"] == [{"custom_id": 1, **puppy}, {"custom_id": 2, **another_puppy}]

    async def test_list_order(self, client, puppy, another_puppy):
        # Successfully create a new record
        response = await client.request("post", "/puppy/", json=puppy)
        assert response.status_code == 201, response.json()

        # Successfully create another new record
        response = await client.request("post", "/puppy/", json=another_puppy)
        assert response.status_code == 201, response.json()

        # List all the existing records
        response = await client.request("get", "/puppy/", params={"order_by": "name", "order_direction": "desc"})
        assert response.status_code == 200, response.json()
        assert response.json()["data"] == [{"custom_id": 2, **another_puppy}, {"custom_id": 1, **puppy}]

    async def test_list_filter(self, client, puppy, another_puppy):
        # Successfully create a new record
        response = await client.request("post", "/puppy/", json=puppy)
        assert response.status_code == 201, response.json()

        # Successfully create another new record
        response = await client.request("post", "/puppy/", json=another_puppy)
        assert response.status_code == 201, response.json()

        # Filter and found something
        response = await client.request("get", "/puppy/", params={"name": "canna", "custom_id__le": 1})
        assert response.status_code == 200, response.json()
        assert response.json()["data"] == [{"custom_id": 1, **puppy}]

        # Filter without results
        response = await client.request("get", "/puppy/", params={"name": "canna", "custom_id__le": 0})
        assert response.status_code == 200, response.json()
        assert response.json()["data"] == []

    async def test_replace(self, client, puppy, another_puppy):
        # Successfully create a new record
        response = await client.request("post", "/puppy/", json=puppy)
        assert response.status_code == 201, response.json()

        # Successfully create a new record
        response = await client.request("post", "/puppy/", json=another_puppy)
        assert response.status_code == 201, response.json()

        # List all the existing records
        response = await client.request("get", "/puppy/")
        assert response.status_code == 200, response.json()
        assert response.json()["data"] == [{"custom_id": 1, **puppy}, {"custom_id": 2, **another_puppy}]

        # Replace collection
        response = await client.request(
            "put", "/puppy/", json=[{"custom_id": 2, **puppy}, {"custom_id": 3, **another_puppy}]
        )
        assert response.status_code == 200, response.json()
        assert response.json() == [{"custom_id": 2, **puppy}, {"custom_id": 3, **another_puppy}]

        # List all the existing records
        response = await client.request("get", "/puppy/")
        assert response.status_code == 200, response.json()
        assert response.json()["data"] == [{"custom_id": 2, **puppy}, {"custom_id": 3, **another_puppy}]

    async def test_replace_wrong_data(self, client, puppy):
        wrong_puppy = puppy.copy()
        wrong_puppy["age"] = "wrong"

        # Successfully create a new record
        response = await client.request("post", "/puppy/", json=puppy)
        assert response.status_code == 201, response.json()

        # List all the existing records
        response = await client.request("get", "/puppy/")
        assert response.status_code == 200, response.json()
        assert response.json()["data"] == [{"custom_id": 1, **puppy}]

        # Fails if wrong input data
        response = await client.request("put", "/puppy/", json=[{"custom_id": 2, **wrong_puppy}])
        assert response.status_code == 400, response.json()

        # Collection remains the same
        response = await client.request("get", "/puppy/")
        assert response.status_code == 200, response.json()
        assert response.json()["data"] == [{"custom_id": 1, **puppy}]

    async def test_partial_replace(self, client, puppy, another_puppy):
        # Successfully create a new record
        response = await client.request("post", "/puppy/", json=puppy)
        assert response.status_code == 201, response.json()

        # Successfully create a new record
        response = await client.request("post", "/puppy/", json=another_puppy)
        assert response.status_code == 201, response.json()

        # List all the existing records
        response = await client.request("get", "/puppy/")
        assert response.status_code == 200, response.json()
        assert response.json()["data"] == [{"custom_id": 1, **puppy}, {"custom_id": 2, **another_puppy}]

        # Partial replace collection
        response = await client.request(
            "patch", "/puppy/", json=[{"custom_id": 2, **puppy}, {"custom_id": 3, **another_puppy}]
        )
        assert response.status_code == 200, response.json()
        assert response.json() == [{"custom_id": 2, **puppy}, {"custom_id": 3, **another_puppy}]

        # List all the existing records
        response = await client.request("get", "/puppy/")
        assert response.status_code == 200, response.json()
        assert response.json()["data"] == [
            {"custom_id": 1, **puppy},
            {"custom_id": 2, **puppy},
            {"custom_id": 3, **another_puppy},
        ]

    async def test_partial_replace_wrong_data(self, client, puppy):
        wrong_puppy = puppy.copy()
        wrong_puppy["age"] = "wrong"

        # Successfully create a new record
        response = await client.request("post", "/puppy/", json=puppy)
        assert response.status_code == 201, response.json()

        # List all the existing records
        response = await client.request("get", "/puppy/")
        assert response.status_code == 200, response.json()
        assert response.json()["data"] == [{"custom_id": 1, **puppy}]

        # Partial replace collection
        response = await client.request("patch", "/puppy/", json=[{"custom_id": 2, **wrong_puppy}])
        assert response.status_code == 400, response.json()

        # Collection remains the same
        response = await client.request("get", "/puppy/")
        assert response.status_code == 200, response.json()
        assert response.json()["data"] == [{"custom_id": 1, **puppy}]

    async def test_drop(self, client, puppy, another_puppy):
        # Successfully create a new record
        response = await client.request("post", "/puppy/", json=puppy)
        assert response.status_code == 201, response.json()

        # Successfully create a new record
        response = await client.request("post", "/puppy/", json=another_puppy)
        assert response.status_code == 201, response.json()

        # List all the existing records
        response = await client.request("get", "/puppy/")
        assert response.status_code == 200, response.json()
        assert response.json()["data"] == [{"custom_id": 1, **puppy}, {"custom_id": 2, **another_puppy}]

        # Drop collection
        response = await client.request("delete", "/puppy/", json=[puppy])
        assert response.status_code == 204, response.json()
        assert response.json() == {"deleted": 2}

        # List all the existing records
        response = await client.request("get", "/puppy/")
        assert response.status_code == 200, response.json()
        assert response.json()["data"] == []
