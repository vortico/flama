import http
from pydantic import BaseModel, validator

import flama
from flama.http import APIResponse
from flama.types import Schema


class Puppy(BaseModel):
    id: int
    name: str
    age: int

    @validator("age")
    def minimum_age_validation(cls, v):
        """Validates that the age is not negative."""
        if v < 0:
            raise ValueError("Age must be positive")

        return v


PUPPIES = [
    {"id": 1, "name": "Bobby", "age": 3},
    {"id": 2, "name": "Rex", "age": 5},
    {"id": 3, "name": "Toby", "age": 2},
]


app = flama.Flama(
    title="My 🔥 API",
    version="1.0",
    description="My API with schema validation",
    docs="/docs/",
    schema="/schema/",
)


@app.route("/puppy/", methods=["GET"])
def list_puppies(name: str = None):
    """
    tags:
        - puppy
    summary:
        List puppies.
    description:
        List the collection of puppies. There is an optional query parameter that
        specifies a name for filtering the collection based on it.
    responses:
        200:
            description: List puppies.
    """
    if name is None:
        return PUPPIES

    puppies = [puppy for puppy in PUPPIES if puppy["name"] == name]

    if not puppies:
        return APIResponse(status_code=http.HTTPStatus.NOT_FOUND)  # type: ignore

    return puppies


@app.route("/puppy/", methods=["POST"])
def create_puppy(puppy: Schema[Puppy]):
    """
    tags:
        - puppy
    summary:
        Create a new puppy.
    description:
        Create a new puppy using data validated from request body and add it
        to the collection.
    responses:
        200:
            description: Puppy created successfully.
    """
    if puppy["id"] in [p["id"] for p in PUPPIES]:
        return APIResponse(status_code=http.HTTPStatus.CONFLICT)  # type: ignore

    PUPPIES.append(puppy)
    return puppy


@app.route("/puppy/{id:int}/", methods=["GET"])
def get_puppy(id: int) -> Puppy:
    """
    tags:
        - puppy
    summary:
        Get a puppy.
    description:
        Get a puppy from the collection.
    responses:
        200:
            description: Puppy retrieved successfully.
    """
    puppies = [puppy for puppy in PUPPIES if puppy["id"] == id]
    if not puppies:
        return APIResponse(status_code=http.HTTPStatus.NOT_FOUND)  # type: ignore

    return puppies[0]


@app.route("/puppy/{id:int}/", methods=["DELETE"])
def delete_puppy(id: int):
    """
    tags:
        - puppy
    summary:
        Delete a puppy.
    description:
        Delete a puppy from the collection.
    responses:
        200:
            description: Puppy deleted successfully.
    """
    puppies = [puppy for puppy in PUPPIES if puppy["id"] == id]
    if not puppies:
        return APIResponse(status_code=http.HTTPStatus.NOT_FOUND)

    for puppy in puppies:
        PUPPIES.remove(puppy)
    return APIResponse(status_code=http.HTTPStatus.OK)


app.schema.register_schema("Puppy", Puppy)

if __name__ == "__main__":
    flama.run(flama_app=app, server_host="0.0.0.0", server_port=8000)
