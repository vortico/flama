<p align="center">
  <img width="1023" height="150" src="https://raw.githubusercontent.com/perdy/starlette-api/master/docs/images/logo.png" alt='Starlette API'>
</p>
<p align="center">
    <em>API power up for Starlette.</em>
</p>
<p align="center">
<a href="https://travis-ci.org/encode/starlette">
    <img src="https://img.shields.io/circleci/project/github/PeRDy/starlette-api/master.svg" alt="Build Status">
</a>
<a href="https://codecov.io/gh/encode/starlette">
    <img src="https://codecov.io/gh/perdy/starlette-api/branch/master/graph/badge.svg" alt="Coverage">
</a>
<a href="https://pypi.org/project/starlette/">
    <img src="https://badge.fury.io/py/starlette-api.svg" alt="Package version">
</a>
</p>

---
# Introduction

Starlette API aims to bring a layer on top of Starlette to provide a fast and easy way for building highly performant REST APIs.

It is production-ready and provides the following:

* **Generic classes** for API resources that provides standard CRUD methods over SQLAlchemy tables.
* **Schema system** based on [Marshmallow](https://github.com/marshmallow-code/marshmallow/) that allows to **declare**
the inputs and outputs of endpoints and provides a reliable way of **validate** data against those schemas.
* **Dependency Injection** that ease the process of managing parameters needed in endpoints. Starlette ASGI objects 
like `Request`, `Response`, `Session` and so on are defined as components and ready to be injected in your endpoints.
* **Components** as the base of the plugin ecosystem, allowing you to create custom or use those already defined in 
your endpoints, injected as parameters.
* **Auto generated API schema** using OpenAPI standard. It uses the schema system of your endpoints to extract all the 
necessary information to generate your API Schema.
* **Auto generated docs** providing a [Swagger UI](https://swagger.io/tools/swagger-ui/) or 
[ReDoc](https://rebilly.github.io/ReDoc/) endpoint.
* **Pagination** automatically handled using multiple methods such as limit and offset, page numbers...

## Requirements

* [Python](https://www.python.org) 3.6+
* [Starlette](https://starlette.io) 0.10+

## Installation

```console
$ pip install starlette-api
```

## Example

```python
from marshmallow import Schema, fields, validate
from starlette_api.applications import Starlette


# Data Schema
class Puppy(Schema):
    id = fields.Integer()
    name = fields.String()
    age = fields.Integer(validate=validate.Range(min=0))


# Database
puppies = [
    {"id": 1, "name": "Canna", "age": 6},
    {"id": 2, "name": "Sandy", "age": 12},
]


# Application
app = Starlette(
    components=[],      # Without custom components
    title="Foo",        # API title
    version="0.1",      # API version
    description="Bar",  # API description
    schema="/schema/",  # Path to expose OpenAPI schema
    docs="/docs/",      # Path to expose Swagger UI docs
    redoc="/redoc/",    # Path to expose ReDoc docs
)


# Views
@app.route("/", methods=["GET"])
def list_puppies(name: str = None) -> Puppy(many=True):
    """
    List the puppies collection. There is an optional query parameter that 
    specifies a name for filtering the collection based on it.
    
    Request example:
    GET http://example.com/?name=Sandy
    
    Response example:
    200
    [
        {"id": 2, "name": "Sandy", "age": 12}
    ]
    """
    return [puppy for puppy in puppies if puppy["name"] == name]
    

@app.route("/", methods=["POST"])
def create_puppy(puppy: Puppy) -> Puppy:
    """
    Create a new puppy using data validated from request body and add it
    to the collection.
    
    Request example:
    POST http://example.com/
    {
        "id": 1,
        "name": "Canna",
        "age": 6
    }
    
    Response example:
    200
    {
        "id": 1,
        "name": "Canna",
        "age": 6
    }
    """
    puppies.append(puppy)
    
    return puppy
```

## Credits

That library started as an adaptation [APIStar](https://github.com/encode/apistar) to work with 
[Starlette](https://github.com/encode/starlette), but a great amount of the code has been rewritten to use 
[Marshmallow](https://github.com/marshmallow-code/marshmallow/) as the schema system, to support websockets and adding 
new functionalities like pagination, generic resources...

## Contributing

This project is absolutely open to contributions so if you have a nice idea, create an issue to let the community 
discuss it.
