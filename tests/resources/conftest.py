import typing as t

import marshmallow
import pydantic
import pytest
import sqlalchemy
import typesystem


@pytest.fixture(scope="function")
def puppy_schema(app):
    from flama import schemas

    if schemas.lib == pydantic:
        schema_ = pydantic.create_model(
            "Puppy", custom_id=(t.Optional[int], None), name=(str, ...), age=(int, ...), owner=(t.Optional[str], None)
        )
    elif schemas.lib == typesystem:
        schema_ = typesystem.Schema(
            fields={
                "custom_id": typesystem.Integer(allow_null=True),
                "name": typesystem.String(),
                "age": typesystem.Number(),
                "owner": typesystem.String(allow_null=True),
            }
        )
    elif schemas.lib == marshmallow:
        schema_ = type(
            "Puppy",
            (marshmallow.Schema,),
            {
                "custom_id": marshmallow.fields.Integer(allow_none=True),
                "name": marshmallow.fields.String(),
                "age": marshmallow.fields.Number(),
                "owner": marshmallow.fields.String(allow_none=True),
            },
        )
    else:
        raise ValueError("Wrong schema lib")

    return schema_


@pytest.fixture(scope="function")
async def puppy_model(app, client):
    table = sqlalchemy.Table(
        "puppy",
        app.sqlalchemy.metadata,
        sqlalchemy.Column("custom_id", sqlalchemy.Integer, primary_key=True, autoincrement=True),
        sqlalchemy.Column("name", sqlalchemy.String, nullable=False),
        sqlalchemy.Column("age", sqlalchemy.Integer, nullable=False),
        sqlalchemy.Column("owner", sqlalchemy.String, nullable=True, default=None),
    )

    async with app.sqlalchemy.engine.begin() as connection:
        await connection.run_sync(app.sqlalchemy.metadata.create_all, tables=[table])

    yield table

    async with app.sqlalchemy.engine.begin() as connection:
        await connection.run_sync(app.sqlalchemy.metadata.drop_all, tables=[table])
