import string

import uvicorn
from marshmallow import Schema, fields, validate

from flama import pagination
from flama.applications import Flama


class Puppy(Schema):
    id = fields.Integer()
    name = fields.String()
    age = fields.Integer(validate=validate.Range(min=0))


PUPPIES = [{"id": 1, "name": "Canna", "age": 7}, {"id": 2, "name": "Sandy", "age": 12}]


app = Flama(
    title="Puppy Register",  # API title
    version="0.1",  # API version
    description="A register of puppies",  # API description
)


@app.route("/number/", methods=["GET"])
@pagination.page_number
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
@pagination.limit_offset
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
@pagination.page_number
def puppies(name: str = None, **kwargs) -> Puppy(many=True):
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
    uvicorn.run(app, host="0.0.0.0", port=8000)
