"""Flama 2.0 example: REST resources (SQLAlchemy CRUD + pagination) and an ML resource.

Demonstrates auto-generated CRUD resources backed by SQLAlchemy with page-number pagination on the list endpoint,
plus a model resource that serves a packaged ``.flm`` model with auto inspect/predict routes.

Run it:
    flama run examples.2_0.resources:app
"""

import contextlib
import pathlib
import tempfile

import numpy as np
import sklearn.linear_model
import sqlalchemy
from pydantic import BaseModel
from sqlalchemy.pool import StaticPool

import flama
from flama import Flama
from flama.models import MLResource
from flama.resources.crud import CRUDResource
from flama.sqlalchemy import SQLAlchemyModule, metadata


class PuppySchema(BaseModel):
    id: int | None = None
    name: str


PuppyModel = sqlalchemy.Table(
    "puppy",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True, autoincrement=True),
    sqlalchemy.Column("name", sqlalchemy.String),
)


class PuppyResource(CRUDResource):
    name = "puppy"
    verbose_name = "Puppy"

    model = PuppyModel
    schema = PuppySchema


# A small packaged model served as an ML resource (auto inspect + predict routes).
_X = np.array([[0, 0], [0, 1], [1, 0], [1, 1]])
_y = np.array([0, 0, 0, 1])  # AND gate
_model = sklearn.linear_model.LogisticRegression().fit(_X, _y)
_workdir = pathlib.Path(tempfile.mkdtemp(prefix="flama2_resources_"))
MODEL_PATH = _workdir / "and.flm"
flama.dump(_model, path=MODEL_PATH, family="ml")


class AndModel(MLResource):
    name = "and_model"
    verbose_name = "AND model"
    model_path = str(MODEL_PATH)


@contextlib.asynccontextmanager
async def lifespan(app: Flama):
    # Create tables once the SQLAlchemy module is fully initialized. The user lifespan runs strictly
    # after every startup event (module init included), so the engine is guaranteed to be available
    # here. (A plain ``@app.on_event("startup")`` handler would race the module init, which runs
    # concurrently with user startup handlers.)
    async with app.sqlalchemy.engine.begin() as connection:
        await connection.run_sync(metadata.create_all)
    yield


app = Flama(
    openapi={
        "info": {
            "title": "Flama 2.0 - Resources",
            "version": "2.0.0",
            "description": "SQLAlchemy CRUD + pagination and ML resources",
        }
    },
    modules=[
        SQLAlchemyModule(
            "sqlite+aiosqlite://",
            engine_args={"connect_args": {"check_same_thread": False}, "poolclass": StaticPool},
        )
    ],
    lifespan=lifespan,
)

app.resources.add_resource("/puppy", PuppyResource)
app.models.add_model_resource("/model", AndModel)


if __name__ == "__main__":
    flama.run(flama_app=app, server_host="0.0.0.0", server_port=8080)
