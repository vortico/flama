import databases
import sqlalchemy
from pydantic import BaseModel
from sqlalchemy import create_engine

import flama
from flama import Flama
from flama.resources.crud import CRUDListResourceType

DATABASE_URL = "sqlite:///resource.db"

database = databases.Database(DATABASE_URL)

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


class PuppyResource(metaclass=CRUDListResourceType):
    database = database

    name = "puppy"
    verbose_name = "Puppy"

    model = PuppyModel
    schema = PuppySchema


app = Flama(
    title="Puppy Register",  # API title
    version="0.1",  # API version
    description="A register of puppies",  # API description
)

app.add_resource("/", PuppyResource)


@app.on_event("startup")
async def startup():
    engine = create_engine(DATABASE_URL)
    metadata.create_all(engine)  # Create the tables.
    await database.connect()


@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()


if __name__ == "__main__":
    flama.run(app, host="0.0.0.0", port=8000)
