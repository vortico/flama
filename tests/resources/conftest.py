from collections import namedtuple

import marshmallow
import pydantic
import pytest
import sqlalchemy
import typesystem

from flama import Flama
from flama.client import Client
from flama.resources.crud import CRUDResource
from flama.sqlalchemy import SQLAlchemyModule

Model = namedtuple("Model", ("model", "schema", "name"))


@pytest.fixture(scope="function")
def app(app):
    return Flama(
        schema=None,
        docs=None,
        modules={SQLAlchemyModule("sqlite+aiosqlite://")},
        schema_library=app.schema.schema_library.name,
    )


@pytest.fixture(scope="function")
async def puppy_model(app):
    if app.schema.schema_library.name == "pydantic":
        schema = pydantic.create_model(
            "Puppy", custom_id=(int | None, None), name=(str, ...), age=(int, ...), owner=(str | None, None)
        )
    elif app.schema.schema_library.name == "typesystem":
        schema = typesystem.Schema(
            title="Puppy",
            fields={
                "custom_id": typesystem.Integer(allow_null=True),
                "name": typesystem.String(),
                "age": typesystem.Integer(),
                "owner": typesystem.String(allow_null=True),
            },
        )
    elif app.schema.schema_library.name == "marshmallow":
        schema = type(
            "Puppy",
            (marshmallow.Schema,),
            {
                "custom_id": marshmallow.fields.Integer(allow_none=True),
                "name": marshmallow.fields.String(),
                "age": marshmallow.fields.Integer(),
                "owner": marshmallow.fields.String(allow_none=True),
            },
        )
    else:
        raise ValueError("Wrong schema lib")

    model = sqlalchemy.Table(
        "puppy",
        app.sqlalchemy.metadata,
        sqlalchemy.Column("custom_id", sqlalchemy.Integer, primary_key=True, autoincrement=True),
        sqlalchemy.Column("name", sqlalchemy.String, nullable=False),
        sqlalchemy.Column("age", sqlalchemy.Integer, nullable=False),
        sqlalchemy.Column("owner", sqlalchemy.String, nullable=True, default=None),
    )

    return Model(model=model, schema=schema, name="puppy")


@pytest.fixture(scope="function")
def puppy_resource(puppy_model):
    class PuppyResource(CRUDResource):
        name = puppy_model.name
        verbose_name = "Puppy"

        model = puppy_model.model
        schema = puppy_model.schema

    return PuppyResource()


@pytest.fixture(scope="function")
async def tables(puppy_model):
    return [puppy_model.model]


@pytest.fixture(scope="function")
async def client(app, tables):
    async with Client(app=app) as client:
        async with app.sqlalchemy.engine.begin() as connection:
            await connection.run_sync(app.sqlalchemy.metadata.create_all, tables=tables)

        yield client

        async with app.sqlalchemy.engine.begin() as connection:
            await connection.run_sync(app.sqlalchemy.metadata.drop_all, tables=tables)
