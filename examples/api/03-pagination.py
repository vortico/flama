import string
import typing

from pydantic import BaseModel, validator

import flama


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
    {"id": 1, "name": "Canna", "age": 7},
    {"id": 2, "name": "Sandy", "age": 12},
    {"id": 3, "name": "Bobby", "age": 3},
    {"id": 4, "name": "Rex", "age": 5},
    {"id": 5, "name": "Toby", "age": 2},
]


app = flama.Flama(
    title="My 🔥 API",
    version="1.0",
    description="My API with pagination",
    docs="/docs/",
    schema="/schema/",
)


@app.route("/puppy/", methods=["GET"])
@app.paginator.page_number(schema_name="Puppy")
def puppies(name: str = None, **kwargs) -> typing.List[Puppy]:
    """
    tags:
        - puppy
    summary:
        List puppies.
    description:
        List the puppies collection. There is an optional query parameter that
        specifies a name for filtering the collection based on it.
    responses:
        200:
            description: List puppies.
    """
    result = PUPPIES
    if name:
        result = filter(lambda x: x["name"] == name, result)

    return result


@app.route("/puppy-offset/", methods=["GET"])
@app.paginator.limit_offset(schema_name="Puppy")
def puppies_offset(name: str, **kwargs) -> typing.List[Puppy]:
    """
    tags:
        - puppy
    summary:
        List puppies with offset pagination.
    description:
        List the puppies collection using offset pagination, so that
        the client can specify the number of items to skip and the
        number of items to return.

    responses:
        200:
            description: List puppies.
    """
    result = PUPPIES
    if name:
        return filter(lambda x: x["name"] == name, result)

    return result


if __name__ == "__main__":
    flama.run(flama_app=app, server_host="0.0.0.0", server_port=8000)
