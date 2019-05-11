import uvicorn
from marshmallow import Schema, fields, validate

from flama.applications.flama import Flama


class Puppy(Schema):
    id = fields.Integer()
    name = fields.String()
    age = fields.Integer(validate=validate.Range(min=0))


def home():
    return {"hello": "world"}


def list_puppies(name: str = None) -> Puppy(many=True):
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
    ...


def create_puppy(puppy: Puppy) -> Puppy:
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
    ...


app = Flama(
    title="Puppy Register",  # API title
    version="0.1",  # API version
    description="A register of puppies",  # API description
)

app.add_route("/", home, methods=["GET"])
app.add_route("/puppy/", list_puppies, methods=["GET"])
app.add_route("/puppy/", create_puppy, methods=["POST"])


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
