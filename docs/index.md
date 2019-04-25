<p align="center">
  <a href="https://flama.perdy.io"><img src="https://raw.githubusercontent.com/perdy/flama/master/docs/images/logo.png" alt='Flama'></a>
</p>
<p align="center">
    <em>Fire up your API with this flamethrower.</em>
</p>
<p align="center">
<a href="https://circleci.com/gh/perdy/flama">
    <img src="https://img.shields.io/circleci/project/github/perdy/flama/master.svg" alt="Build Status">
</a>
<a href="https://codecov.io/gh/perdy/flama">
    <img src="https://codecov.io/gh/perdy/flama/branch/master/graph/badge.svg" alt="Coverage">
</a>
<a href="https://pypi.org/project/flama/">
    <img src="https://badge.fury.io/py/flama.svg" alt="Package version">
</a>
</p>

---

**Documentation**: [https://flama.perdy.io](https://flama.perdy.io)

---

# Flama

Flama aims to bring a layer on top of [Starlette] to provide an **easy to learn** and **fast to develop** approach for 
building **highly performant** GraphQL and REST APIs. In the same way of Starlette is, Flama is a perfect option for 
developing **asynchronous** and **production-ready** services. 

Among other characteristics it provides the following:

* **Generic classes** for API resources that provides standard CRUD methods over SQLAlchemy tables.
* **Schema system** based on [Marshmallow] that allows to **declare** the inputs and outputs of endpoints and provides 
a reliable way of **validate** data against those schemas.
* **Dependency Injection** that ease the process of managing parameters needed in endpoints. Flama ASGI objects 
like `Request`, `Response`, `Session` and so on are defined as components and ready to be injected in your endpoints.
* **Components** as the base of the plugin ecosystem, allowing you to create custom or use those already defined in 
your endpoints, injected as parameters.
* **Auto generated API schema** using OpenAPI standard. It uses the schema system of your endpoints to extract all the 
necessary information to generate your API Schema.
* **Auto generated docs** providing a [Swagger UI] or [ReDoc] endpoint.
* **Pagination** automatically handled using multiple methods such as limit and offset, page numbers...

## Requirements

* [Python] 3.6+
* [Starlette] 0.10+
* [Marshmallow] 3.0+

## Installation

```console
$ pip install flama
```

## Example

```python
from marshmallow import Schema, fields, validate
from flama.applications import Flama


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
app = Flama(
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
    description:
        List the puppies collection. There is an optional query parameter that 
        specifies a name for filtering the collection based on it.
    responses:
        200:
            description: List puppies.
    """
    return [puppy for puppy in puppies if puppy["name"] == name]
    

@app.route("/", methods=["POST"])
def create_puppy(puppy: Puppy) -> Puppy:
    """
    description:
        Create a new puppy using data validated from request body and add it 
        to the collection.
    responses:
        200:
            description: Puppy created successfully.
    """
    puppies.append(puppy)
    
    return puppy
```

## Dependencies

Following Starlette philosophy Flama reduce the number of hard dependencies to those that are used as the core:

* [`starlette`][Starlette] - Flama is a layer on top of it.
* [`marshmallow`][Marshmallow] - Flama data schemas and validation.

It does not have any more hard dependencies, but some of them are necessaries to use some features:

* [`pyyaml`][pyyaml] - Required for API Schema and Docs auto generation.
* [`apispec`][apispec] - Required for API Schema and Docs auto generation.
* [`python-forge`][python-forge] - Required for pagination.
* [`sqlalchemy`][SQLAlchemy] - Required for Generic API resources.
* [`databases`][databases] - Required for Generic API resources.

You can install all of these with `pip3 install flama[full]`.

## Credits

That library is heavily inspired by [APIStar] server in an attempt to bring a good amount of it essence to work with 
[Starlette] as the ASGI framework and [Marshmallow] as the schema system.

## Contributing

This project is absolutely open to contributions so if you have a nice idea, create an issue to let the community 
discuss it.

[Python]: https://www.python.org
[Starlette]: https://starlette.io
[APIStar]: https://github.com/encode/apistar/tree/version-0.5.x
[Marshmallow]: https://marshmallow.readthedocs.io/
[Swagger UI]: https://swagger.io/tools/swagger-ui/
[ReDoc]: https://rebilly.github.io/ReDoc/
[pyyaml]: https://pyyaml.org/wiki/PyYAMLDocumentation
[apispec]: https://apispec.readthedocs.io/
[python-forge]: https://python-forge.readthedocs.io/
[SQLAlchemy]: https://www.sqlalchemy.org/
[databases]: https://github.com/encode/databases