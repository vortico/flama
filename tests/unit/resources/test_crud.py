import datetime
import enum
import typing as t
import uuid

import marshmallow
import pydantic
import pytest
import sqlalchemy
import typesystem
import typesystem.fields
from sqlalchemy.dialects import postgresql

from flama import types
from flama.resources.crud import CRUDResource
from flama.resources.exceptions import ResourceFilterInvalid
from flama.resources.routing import ResourceRoute
from flama.resources.workers import FlamaWorker
from tests.unit.resources.conftest import Model

DATABASE_URL = "sqlite+aiosqlite://"


class _Status(enum.Enum):
    """A column type a query string can carry, unlike the other non-primitive ones."""

    available = "available"
    broken = "broken"


@pytest.fixture(scope="function")
def puppy():
    return {"name": "canna", "age": 2, "owner": "Perdy"}


@pytest.fixture(scope="function")
def another_puppy():
    return {"name": "sandy", "age": 6, "owner": "Perdy"}


class TestCaseCRUDResource:
    @pytest.fixture(scope="function")
    async def custom_id_datetime_model(self, app):
        if app.schema.schema_library.name == "pydantic":
            schema = pydantic.create_model("CustomIDDatetime", custom_id=(datetime.datetime, ...), name=(str, ...))
        elif app.schema.schema_library.name == "typesystem":
            schema = typesystem.Schema(
                title="CustomIDDatetime",
                fields={
                    "custom_id": typesystem.fields.DateTime(),
                    "name": typesystem.fields.String(),
                },
            )
        elif app.schema.schema_library.name == "marshmallow":
            schema = type(
                "CustomIDDatetime",
                (marshmallow.Schema,),
                {
                    "custom_id": marshmallow.fields.DateTime(),
                    "name": marshmallow.fields.String(),
                },
            )
        else:
            raise ValueError("Wrong schema lib")

        model = sqlalchemy.Table(
            "custom_id_datetime",
            app.sqlalchemy.metadata,
            sqlalchemy.Column("custom_id", sqlalchemy.DateTime, primary_key=True),
            sqlalchemy.Column("name", sqlalchemy.String),
        )

        return Model(model=model, schema=schema, name="custom_id_datetime")

    @pytest.fixture(scope="function")
    def custom_id_uuid_model(self, app):
        if app.schema.schema_library.name == "pydantic":
            schema = pydantic.create_model("CustomIDUUID", custom_id=(uuid.UUID, ...), name=(str, ...))
        elif app.schema.schema_library.name == "typesystem":
            schema = typesystem.Schema(
                title="CustomIDUUID",
                fields={
                    "custom_id": typesystem.fields.UUID(),
                    "name": typesystem.fields.String(),
                },
            )
        elif app.schema.schema_library.name == "marshmallow":
            schema = type(
                "CustomIDUUID",
                (marshmallow.Schema,),
                {
                    "custom_id": marshmallow.fields.UUID(),
                    "name": marshmallow.fields.String(),
                },
            )
        else:
            raise ValueError("Wrong schema lib")

        model = sqlalchemy.Table(
            "custom_id_uuid",
            app.sqlalchemy.metadata,
            sqlalchemy.Column("custom_id", postgresql.UUID, primary_key=True),
            sqlalchemy.Column("name", sqlalchemy.String),
        )

        return Model(model=model, schema=schema, name="custom_id_uuid")

    @pytest.fixture(scope="function")
    async def tables(self, tables, custom_id_datetime_model, custom_id_uuid_model):
        return tables + [custom_id_datetime_model.model, custom_id_uuid_model.model]

    @pytest.fixture(scope="function")
    def puppy_resource(self, app, puppy_model):
        class PuppyResource(CRUDResource):
            name = puppy_model.name
            verbose_name = "Puppy"

            model = puppy_model.model
            input_schema = puppy_model.schema
            output_schema = puppy_model.schema

            @app.resources.method("/", methods=["GET"], name="list", pagination="page_number")
            async def list(
                self,
                worker: FlamaWorker,
                order_by: str | None = None,
                order_direction: str = "asc",
                name: str | None = None,
                custom_id__le: int | None = None,
                **kwargs,
            ) -> t.Annotated[types.SchemaList, types.SchemaMetadata(puppy_model.schema)]:
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
    def custom_id_datetime_resource(self, custom_id_datetime_model):
        class CustomUUIDResource(CRUDResource):
            model = custom_id_datetime_model.model
            schema = custom_id_datetime_model.schema
            name = custom_id_datetime_model.name

        return CustomUUIDResource()

    @pytest.fixture(scope="function")
    def custom_id_uuid_resource(self, custom_id_uuid_model):
        class CustomUUIDResource(CRUDResource):
            model = custom_id_uuid_model.model
            schema = custom_id_uuid_model.schema
            name = custom_id_uuid_model.name

        return CustomUUIDResource()

    @pytest.fixture(scope="function", autouse=True)
    def add_resources(self, app, puppy_resource, custom_id_datetime_resource, custom_id_uuid_resource):
        app.resources.add_resource("/puppy/", puppy_resource)
        app.resources.add_resource("/custom_id_datetime/", custom_id_datetime_resource)
        app.resources.add_resource("/custom_id_uuid/", custom_id_uuid_resource)

    def test_crud_resource(self, puppy_resource, client):
        expected_routes = [
            ("/", puppy_resource.list, {"GET", "HEAD"}, "list"),
            ("/", puppy_resource.create, {"POST"}, "create"),
            ("/{resource_id}/", puppy_resource.retrieve, {"GET", "HEAD"}, "retrieve"),
            ("/{resource_id}/", puppy_resource.update, {"PUT"}, "update"),
            ("/{resource_id}/", puppy_resource.partial_update, {"PATCH"}, "partial-update"),
            ("/{resource_id}/", puppy_resource.delete, {"DELETE"}, "delete"),
            ("/", puppy_resource.replace, {"PUT"}, "replace"),
            ("/", puppy_resource.partial_replace, {"PATCH"}, "partial-replace"),
            ("/", puppy_resource.drop, {"DELETE"}, "drop"),
        ]

        assert hasattr(puppy_resource, "create")
        assert hasattr(puppy_resource, "retrieve")
        assert hasattr(puppy_resource, "update")
        assert hasattr(puppy_resource, "partial_update")
        assert hasattr(puppy_resource, "delete")
        assert hasattr(puppy_resource, "list")
        assert hasattr(puppy_resource, "replace")
        assert hasattr(puppy_resource, "partial_replace")
        assert hasattr(puppy_resource, "drop")

        route = next((route for route in client.app.routes if route.path == "/puppy/"), None)
        assert route
        assert isinstance(route, ResourceRoute)
        assert [
            (i.path, getattr(i.endpoint, "__wrapped__", i.endpoint), i.methods, i.name) for i in route.routes
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

    @pytest.mark.parametrize(
        ["method", "send_body", "skip_typesystem"],
        [
            pytest.param("get", False, False, id="retrieve"),
            pytest.param("put", True, False, id="update"),
            pytest.param("patch", True, True, id="partial_update"),
            pytest.param("delete", True, False, id="delete"),
        ],
    )
    async def test_not_found(self, client, puppy, method, send_body, skip_typesystem):
        if skip_typesystem and client.app.schema.schema_library.name == "typesystem":
            pytest.skip("Typesystem does not support partial validation")

        # Operate on a record that does not exist
        response = await client.request(method, "/puppy/42/", json=puppy if send_body else None)
        assert response.status_code == 404, response.json()

    @pytest.mark.parametrize(
        ["method", "send_body", "skip_typesystem"],
        [
            pytest.param("get", False, False, id="retrieve"),
            pytest.param("put", True, False, id="update"),
            pytest.param("patch", True, True, id="partial_update"),
            pytest.param("delete", False, False, id="delete"),
        ],
    )
    async def test_wrong_id_type(self, client, puppy, method, send_body, skip_typesystem):
        if skip_typesystem and client.app.schema.schema_library.name == "typesystem":
            pytest.skip("Typesystem does not support partial validation")

        # Operate on a record whose id does not match the primary-key type
        response = await client.request(method, "/puppy/foo/", json=puppy if send_body else None)
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
        if client.app.schema.schema_library.name == "typesystem":
            pytest.skip("Typesystem does not support partial validation")

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

    async def test_partial_update_wrong_data(self, client, puppy):
        if client.app.schema.schema_library.name == "typesystem":
            pytest.skip("Typesystem does not support partial validation")

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

    async def test_list_default_handler(self, client):
        # The puppy resource overrides "list"; the custom-id resource exercises the default CRUD list handler
        await client.request("post", "/custom_id_datetime/", json={"custom_id": "2018-01-01T00:00:00", "name": "a"})
        await client.request("post", "/custom_id_datetime/", json={"custom_id": "2019-01-01T00:00:00", "name": "b"})

        response = await client.request("get", "/custom_id_datetime/")
        assert response.status_code == 200, response.json()
        assert response.json()["data"] == [
            {"custom_id": "2018-01-01T00:00:00", "name": "a"},
            {"custom_id": "2019-01-01T00:00:00", "name": "b"},
        ]

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

    async def test_replace_integrity_error(self, client, puppy, another_puppy):
        # Two records sharing the same primary key make the bulk create fail the integrity constraint
        response = await client.request(
            "put", "/puppy/", json=[{"custom_id": 1, **puppy}, {"custom_id": 1, **another_puppy}]
        )
        assert response.status_code == 400, response.json()

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

    async def test_partial_replace_integrity_error(self, client, puppy, another_puppy):
        # Two records sharing the same primary key make the bulk create fail the integrity constraint
        response = await client.request(
            "patch", "/puppy/", json=[{"custom_id": 1, **puppy}, {"custom_id": 1, **another_puppy}]
        )
        assert response.status_code == 400, response.json()

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


class TestCaseCRUDUniqueConstraint:
    """Cover the ``IntegrityError`` -> 400 branches of the single-resource ``update`` / ``partial_update``
    handlers, which only fire when a UNIQUE *non* primary-key column collides with another row (a
    primary-key collision can't happen on these handlers because the id is pinned by the path).
    """

    @pytest.fixture(scope="function")
    async def unique_name_model(self, app):
        if app.schema.schema_library.name == "pydantic":
            schema = pydantic.create_model("UniqueName", custom_id=(int | None, None), name=(str, ...))
        elif app.schema.schema_library.name == "typesystem":
            schema = typesystem.Schema(
                title="UniqueName",
                fields={"custom_id": typesystem.Integer(allow_null=True), "name": typesystem.String()},
            )
        elif app.schema.schema_library.name == "marshmallow":
            schema = type(
                "UniqueName",
                (marshmallow.Schema,),
                {"custom_id": marshmallow.fields.Integer(allow_none=True), "name": marshmallow.fields.String()},
            )
        else:
            raise ValueError("Wrong schema lib")

        model = sqlalchemy.Table(
            "unique_name",
            app.sqlalchemy.metadata,
            sqlalchemy.Column("custom_id", sqlalchemy.Integer, primary_key=True, autoincrement=True),
            sqlalchemy.Column("name", sqlalchemy.String, nullable=False, unique=True),
        )

        return Model(model=model, schema=schema, name="unique_name")

    @pytest.fixture(scope="function")
    async def tables(self, unique_name_model):
        return [unique_name_model.model]

    @pytest.fixture(scope="function", autouse=True)
    def add_resource(self, app, unique_name_model):
        class UniqueNameResource(CRUDResource):
            model = unique_name_model.model
            schema = unique_name_model.schema
            name = unique_name_model.name

        app.resources.add_resource("/unique_name/", UniqueNameResource())

    async def test_update_integrity_error(self, client):
        assert (await client.request("post", "/unique_name/", json={"name": "a"})).status_code == 201
        assert (await client.request("post", "/unique_name/", json={"name": "b"})).status_code == 201

        # PUT deletes row 2 and recreates it with a name already owned by row 1
        response = await client.request("put", "/unique_name/2/", json={"name": "a"})
        assert response.status_code == 400, response.json()

    async def test_partial_update_integrity_error(self, client):
        if client.app.schema.schema_library.name == "typesystem":
            pytest.skip("Typesystem does not support partial validation")

        assert (await client.request("post", "/unique_name/", json={"name": "a"})).status_code == 201
        assert (await client.request("post", "/unique_name/", json={"name": "b"})).status_code == 201

        # PATCH row 2's name to one already owned by row 1
        response = await client.request("patch", "/unique_name/2/", json={"name": "a"})
        assert response.status_code == 400, response.json()


class TestCaseCRUDFilters:
    """A collection is filtered through the columns a query string can carry, and only through those."""

    @pytest.fixture(scope="function")
    async def gadget_model(self, app):
        if app.schema.schema_library.name == "pydantic":
            schema = pydantic.create_model("Gadget", custom_id=(int | None, None), name=(str, ...))
        elif app.schema.schema_library.name == "typesystem":
            schema = typesystem.Schema(
                title="Gadget",
                fields={"custom_id": typesystem.Integer(allow_null=True), "name": typesystem.String()},
            )
        elif app.schema.schema_library.name == "marshmallow":
            schema = type(
                "Gadget",
                (marshmallow.Schema,),
                {"custom_id": marshmallow.fields.Integer(allow_none=True), "name": marshmallow.fields.String()},
            )
        else:
            raise ValueError("Wrong schema lib")

        model = sqlalchemy.Table(
            "gadget",
            app.sqlalchemy.metadata,
            sqlalchemy.Column("custom_id", sqlalchemy.Integer, primary_key=True, autoincrement=True),
            sqlalchemy.Column("name", sqlalchemy.String, nullable=False),
            sqlalchemy.Column("status", sqlalchemy.Enum(_Status), nullable=True),
            # None of these can be written in a query string, so none of them is a filter.
            sqlalchemy.Column("payload", sqlalchemy.JSON, nullable=True),
            sqlalchemy.Column("blob", sqlalchemy.LargeBinary, nullable=True),
            sqlalchemy.Column("span", sqlalchemy.Interval, nullable=True),
        )

        return Model(model=model, schema=schema, name="gadget")

    @pytest.fixture(scope="function")
    async def tables(self, gadget_model):
        return [gadget_model.model]

    @pytest.fixture(scope="function", autouse=True)
    def add_resource(self, app, gadget_model):
        class GadgetResource(CRUDResource):
            model = gadget_model.model
            schema = gadget_model.schema
            name = gadget_model.name

        app.resources.add_resource("/gadget/", GadgetResource())

    def test_only_expressible_columns_become_filters(self, app):
        resource_route = next(route for route in app.routes if route.path == "/gadget/")
        list_route = next(route for route in resource_route.routes if route.path == "/" and "GET" in route.methods)

        # The primary key is served by the retrieve route, and the remaining columns have no query string
        # representation, so neither kind is offered alongside the ordering and pagination parameters.
        assert sorted(list_route.parameters.query["GET"]) == [
            "count",
            "name",
            "order_by",
            "order_direction",
            "page",
            "page_size",
            "status",
        ]

    async def test_list_serves_a_table_holding_columns_that_cannot_be_filters(self, client):
        """A column nobody filters by must not break the requests that never mention it."""
        response = await client.request("get", "/gadget/")

        assert response.status_code == 200, response.json()
        assert response.json()["data"] == []


class TestCaseCRUDDeclaredFilters:
    """A resource declaring its filters is filtered by those columns, through those operators, and no other."""

    @pytest.fixture(scope="function")
    async def widget_model(self, app):
        if app.schema.schema_library.name == "pydantic":
            schema = pydantic.create_model(
                "Widget", custom_id=(int | None, None), name=(str, ...), age=(int | None, None)
            )
        elif app.schema.schema_library.name == "typesystem":
            schema = typesystem.Schema(
                title="Widget",
                fields={
                    "custom_id": typesystem.Integer(allow_null=True),
                    "name": typesystem.String(),
                    "age": typesystem.Integer(allow_null=True),
                },
            )
        elif app.schema.schema_library.name == "marshmallow":
            schema = type(
                "Widget",
                (marshmallow.Schema,),
                {
                    "custom_id": marshmallow.fields.Integer(allow_none=True),
                    "name": marshmallow.fields.String(),
                    "age": marshmallow.fields.Integer(allow_none=True),
                },
            )
        else:
            raise ValueError("Wrong schema lib")

        model = sqlalchemy.Table(
            "widget",
            app.sqlalchemy.metadata,
            sqlalchemy.Column("custom_id", sqlalchemy.Integer, primary_key=True, autoincrement=True),
            sqlalchemy.Column("name", sqlalchemy.String, nullable=False),
            sqlalchemy.Column("age", sqlalchemy.Integer, nullable=True),
            sqlalchemy.Column("secret", sqlalchemy.String, nullable=True),
        )

        return Model(model=model, schema=schema, name="widget")

    @pytest.fixture(scope="function")
    async def tables(self, widget_model):
        return [widget_model.model]

    @pytest.fixture(scope="function", autouse=True)
    def add_resource(self, app, widget_model):
        class WidgetResource(CRUDResource):
            model = widget_model.model
            schema = widget_model.schema
            name = widget_model.name

            filters = {"name": ("eq", "contains"), "age": ("eq", "gte", "lte", "in", "isnull")}

        app.resources.add_resource("/widget/", WidgetResource())

    def test_declaration_narrows_the_surface(self, app):
        resource_route = next(route for route in app.routes if route.path == "/widget/")
        list_route = next(route for route in resource_route.routes if route.path == "/" and "GET" in route.methods)

        # `secret` is a perfectly filterable column that the resource chose not to offer.
        assert sorted(list_route.parameters.query["GET"]) == [
            "age",
            "count",
            "name",
            "order_by",
            "order_direction",
            "page",
            "page_size",
        ]

    @pytest.fixture(scope="function")
    async def widgets(self, client):
        for name, age in (("alpha", 2), ("beta", 6), ("gamma", 11), ("delta", None)):
            response = await client.request("post", "/widget/", json={"name": name, "age": age})
            assert response.status_code == 201, response.json()

    @pytest.mark.parametrize(
        ["query", "expected"],
        [
            pytest.param({}, ["alpha", "beta", "gamma", "delta"], id="unfiltered"),
            pytest.param({"age": "6"}, ["beta"], id="bare_value_is_equality"),
            pytest.param({"age": "gte:6"}, ["beta", "gamma"], id="operator"),
            # Naming a column twice narrows it, which is how a range is asked for.
            pytest.param({"age": ["gte:6", "lte:10"]}, ["beta"], id="range"),
            # Naming it twice with an aggregating operator offers alternatives instead.
            pytest.param({"age": ["in:2", "in:11"]}, ["alpha", "gamma"], id="membership"),
            pytest.param({"age": "isnull"}, ["delta"], id="null"),
            pytest.param({"age": "not:isnull"}, ["alpha", "beta", "gamma"], id="not_null"),
            pytest.param({"name": "contains:mm"}, ["gamma"], id="pattern"),
            pytest.param({"name": "not:contains:a"}, [], id="negated_pattern"),
            pytest.param({"name": "beta", "age": "gte:6"}, ["beta"], id="two_columns"),
        ],
    )
    async def test_list_filter(self, client, widgets, query, expected):
        response = await client.request("get", "/widget/", params=query)

        assert response.status_code == 200, response.json()
        assert [x["name"] for x in response.json()["data"]] == expected

    @pytest.mark.parametrize(
        ["query", "detail"],
        [
            pytest.param(
                {"name": "gte:x"},
                {"name": ["Operator 'gte' is not available, expected one of: 'eq', 'contains'."]},
                id="operator_not_granted",
            ),
            pytest.param({"age": "gte"}, {"age": ["Operator 'gte' expects a value."]}, id="value_missing"),
            pytest.param(
                {"age": "isnull:yes"}, {"age": ["Operator 'isnull' expects no value."]}, id="value_unexpected"
            ),
            # The wording comes from the schema library, so only the refusal itself is shared by all three.
            pytest.param({"age": "gte:old"}, None, id="value_the_column_cannot_hold"),
        ],
    )
    async def test_list_filter_rejected(self, client, widgets, query, detail):
        response = await client.request("get", "/widget/", params=query)

        assert response.status_code == 400, response.json()

        if detail is not None:
            assert response.json()["detail"] == detail

    def test_declaring_an_impossible_filter_fails_where_it_is_declared(self, app, widget_model):
        with pytest.raises(
            ResourceFilterInvalid,
            match="BrokenResource cannot be filtered by 'age' because operator 'contains' cannot compare what it holds",
        ):

            class BrokenResource(CRUDResource):
                model = widget_model.model
                schema = widget_model.schema
                name = "broken"

                filters = {"age": ("contains",)}
