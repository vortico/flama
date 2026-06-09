"""Flama 2.0 example: schema validation and OpenAPI generation.

Demonstrates request/response schema validation and automatic OpenAPI generation for nested and recursive
models, with the interactive docs UI. Uses Pydantic as the active schema library.

Run it:
    flama run examples.2_0.schema:app
"""

import typing as t

import pydantic

import flama
from flama import Flama, types


class Tag(pydantic.BaseModel):
    name: str
    weight: float = 1.0


class Category(pydantic.BaseModel):
    id: int
    name: str
    subcategories: list["Category"] = []  # recursive -> self-referencing $ref in OpenAPI


class Puppy(pydantic.BaseModel):
    id: int
    name: str
    age: int = pydantic.Field(ge=0)
    category: Category
    tags: list[Tag] = []


CATEGORIES = [Category(id=1, name="hounds", subcategories=[Category(id=2, name="beagles")])]


app = Flama(
    openapi={
        "info": {
            "title": "Flama 2.0 - Schema & OpenAPI",
            "version": "2.0.0",
            "description": "Nested + recursive schema validation and OpenAPI generation",
        }
    },
    schema="/schema/",
    docs="/docs/",
    schema_library="pydantic",
)


@app.route("/puppies/", methods=["POST"], name="create_puppy")
def create_puppy(
    puppy: t.Annotated[types.Schema, types.SchemaMetadata(Puppy)],
) -> t.Annotated[types.Schema, types.SchemaMetadata(Puppy)]:
    """
    tags:
        - puppy
    summary:
        Create a puppy.
    description:
        Validate a nested puppy payload and echo it back.
    responses:
        200:
            description: The created puppy.
    """
    return puppy


@app.route("/categories/", methods=["GET"], name="list_categories")
def list_categories() -> t.Annotated[types.SchemaList, types.SchemaMetadata(Category)]:
    """
    tags:
        - category
    summary:
        List categories.
    description:
        Return the (recursive) category tree.
    responses:
        200:
            description: The category list.
    """
    return CATEGORIES


if __name__ == "__main__":
    flama.run(flama_app=app, server_host="0.0.0.0", server_port=8080)
