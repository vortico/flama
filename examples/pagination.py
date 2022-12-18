import string
import typing

from pydantic import BaseModel, validator

import flama
from flama import Flama


class Puppy(BaseModel):
    id: int
    name: str
    age: int

    @validator("age")
    def minimum_age_validation(cls, v):
        if v < 0:
            raise ValueError("Age must be positive")

        return v


PUPPIES = [{"id": 1, "name": "Canna", "age": 7}, {"id": 2, "name": "Sandy", "age": 12}]


app = Flama(
    title="Puppy Register",  # API title
    version="0.1",  # API version
    description="A register of puppies",  # API description
)


@app.route("/number/", methods=["GET"])
@app.paginator.page_number
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


@app.route("/alphabet/", methods=["GET"])
@app.paginator.limit_offset
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


@app.route("/puppy/", methods=["GET"])
@app.paginator.page_number
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


if __name__ == "__main__":
    flama.run(app, host="0.0.0.0", port=8000)
