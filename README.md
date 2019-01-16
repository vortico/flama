# Starlette API
[![Build Status](https://travis-ci.org/PeRDy/starlette-api.svg?branch=master)](https://travis-ci.org/PeRDy/starlette-api)
[![codecov](https://codecov.io/gh/PeRDy/starlette-api/branch/master/graph/badge.svg)](https://codecov.io/gh/PeRDy/starlette-api)
[![PyPI version](https://badge.fury.io/py/starlette-api.svg)](https://badge.fury.io/py/starlette-api)

* **Version:** 0.2.1
* **Status:** Production/Stable
* **Author:** José Antonio Perdiguero López

## Introduction

That library aims to bring a layer on top of Starlette framework to provide useful mechanism for building APIs. It's 
based on API Star, inheriting some nice ideas like:

* **Schema system** based on [Marshmallow](https://github.com/marshmallow-code/marshmallow/) that allows to **declare**
the inputs and outputs of endpoints and provides a reliable way of **validate** data against those schemas.
* **Dependency Injection** that ease the process of managing parameters needed in endpoints.
* **Components** as the base of the plugin ecosystem, allowing you to create custom or use those already defined in 
your endpoints, injected as parameters.
* **Starlette ASGI** objects like `Request`, `Response`, `Session` and so on are defined as components and ready to be 
injected in your endpoints.

## Requirements

* Python 3.6+
* Starlette 0.9+

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
app = Starlette()


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

That library started mainly as extracted pieces from [APIStar](https://github.com/encode/apistar) and adapted to work 
with [Starlette](https://github.com/encode/starlette).

## Contributing

This project is absolutely open to contributions so if you have a nice idea, create an issue to let the community 
discuss it.