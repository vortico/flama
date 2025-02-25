import string
import typing as t

import pydantic

import flama
from flama import Flama


class Puppy(pydantic.BaseModel):
    id: int
    name: str
    age: int

    @pydantic.field_validator("age")
    def minimum_age_validation(cls, v):
        if v < 0:
            raise ValueError("Age must be positive")

        return v


PUPPIES: list[Puppy] = [Puppy(id=1, name="Canna", age=7), Puppy(id=2, name="Sandy", age=12)]


app = Flama(
    openapi={
        "info": {
            "title": "Puppy Register",  # API title
            "version": "0.1",  # API version
            "description": "A register of puppies",  # API description
        }
    },
)


@app.route("/number/", methods=["GET"], pagination="page_number")
def numbers(**kwargs):
    """
    tags:
        - numbers.
    summary:
        A sequence of numbers.
    description:
        A sequence of numbers that uses page-number pagination.
    responses:
        200:
            description: Sequence of numbers.
    """
    return list(range(100))


@app.route("/alphabet/", methods=["GET"], pagination="limit_offset")
def alphabet(**kwargs):
    """
    tags:
        - alphabet.
    summary:
        A sequence of alphabet letters.
    description:
        A sequence of alphabet letters that uses limit-offset pagination.
    responses:
        200:
            description: Sequence of alphabet letters.
    """
    return list(string.ascii_lowercase)


@app.route("/puppy/", methods=["GET"], pagination="page_number")
def puppies(name: t.Optional[str] = None, **kwargs) -> list[Puppy]:
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
        result = [x for x in result if x.name == name]

    return result


if __name__ == "__main__":
    flama.run(flama_app=app, server_host="0.0.0.0", server_port=8080)
