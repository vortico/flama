import sqlalchemy
from pydantic import BaseModel

import flama
from flama import Flama
from flama.resources.crud import CRUDResource
from flama.sqlalchemy import SQLAlchemyModule

DATABASE_URL = "sqlite+aiosqlite://"

metadata = sqlalchemy.MetaData()


class PuppySchema(BaseModel):
    custom_id: int
    name: str


PuppyModel = sqlalchemy.Table(
    "puppy",
    metadata,
    sqlalchemy.Column("custom_id", sqlalchemy.Integer, primary_key=True, autoincrement=True),
    sqlalchemy.Column("name", sqlalchemy.String),
)


class PuppyResource(CRUDResource):
    name = "puppy"
    verbose_name = "Puppy"

    model = PuppyModel
    schema = PuppySchema


app = Flama(
    openapi={
        "info": {
            "title": "Puppy Register",  # API title
            "version": "0.1.0",  # API version
            "description": "A register of puppies",  # API description
        }
    },
    modules=[SQLAlchemyModule(database=DATABASE_URL)],
)

app.resources.add_resource("/", PuppyResource)


if __name__ == "__main__":
    flama.run(flama_app=app, server_host="0.0.0.0", server_port=8080)
