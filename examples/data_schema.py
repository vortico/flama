from pydantic import BaseModel, validator

import flama
from flama import Flama

app = Flama(
    title="Puppy Register",  # API title
    version="0.1",  # API version
    description="A register of puppies",  # API description
    schema="/schema/",  # Path to expose OpenAPI schema
    docs="/docs/",  # Path to expose Docs application
)


class Puppy(BaseModel):
    id: int
    name: str
    age: int

    @validator("age")
    def minimum_age_validation(cls, v):
        if v < 0:
            raise ValueError("Age must be positive")

        return v


app.schema.register_schema("Puppy", Puppy)


def home():
    return {"hello": "world"}


def list_puppies(name: str = None) -> list[Puppy]:
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


app.add_route("/puppy/", list_puppies, methods=["GET"])
app.add_route("/puppy/", create_puppy, methods=["POST"])

if __name__ == "__main__":
    flama.run(app, host="0.0.0.0", port=8000)
