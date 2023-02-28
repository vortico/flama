<p align="center">
    <a href="https://flama.dev"><img src="https://raw.githubusercontent.com/vortico/flama/master/.github/logo.png" alt='Flama'></a>
</p>
<p align="center">
    <em>Fire up your models with the flame</em> &#128293;
</p>
<p align="center">
    <a href="https://github.com/vortico/flama/actions">
        <img src="https://github.com/vortico/flama/workflows/Test%20And%20Publish/badge.svg" alt="Test And Publish workflow status">
    </a>
    <a href="https://github.com/vortico/flama/actions">
        <img src="https://github.com/vortico/flama/workflows/Docker%20Push/badge.svg" alt="Docker Push workflow status">
    </a>
    <a href="https://pypi.org/project/flama/">
        <img src="https://img.shields.io/pypi/v/flama?logo=PyPI&logoColor=white" alt="Package version">
    </a>
    <a href="https://pypi.org/project/flama/">
        <img src="https://img.shields.io/pypi/pyversions/flama?logo=Python&logoColor=white" alt="PyPI - Python Version">
    </a>
</p>

---

# Flama

Flama is a python library which establishes a standard framework for
development and deployment of APIs with special focus on machine learning (ML).
The main aim of the framework is to make ridiculously simple the deployment of
ML APIs, simplifying (when possible) the entire process to a single line of
code.

The library builds on Starlette, and provides an easy-to-learn
philosophy to speed up the building of highly performant GraphQL, REST and ML APIs.
Besides, it comprises an ideal solution for the development of asynchronous
and production-ready services, offering automatic deployment for ML models.

Some remarkable characteristics:

* Generic classes for API resources with the convenience of standard CRUD methods over SQLAlchemy tables.
* A schema system (based on Marshmallow or Typesystem) which allows the declaration of inputs and outputs of endpoints
  very easily, with the convenience of reliable and automatic data-type validation.
* Dependency injection to make ease the process of managing parameters needed in endpoints via the use of `Component`s.
  Flama ASGI objects like `Request`, `Response`, `Session` and so on are defined as `Component`s ready to be injected in
  your endpoints.
* `Component`s as the base of the plugin ecosystem, allowing you to create custom or use those already defined in your
  endpoints, injected as parameters.
* Auto generated API schema using OpenAPI standard.
* Auto generated `docs`, and provides a Swagger UI and ReDoc endpoints.
* Automatic handling of pagination, with several methods at your disposal such as `limit-offset` and `page numbering`,
  to name a few.

## Installation

Flama is fully compatible with all [supported versions](https://devguide.python.org/versions/) of Python. We recommend
you to use the latest version available.

For a detailed explanation on how to install flama
visit:  [https://flama.dev/docs/getting-started/installation](https://flama.dev/docs/getting-started/installation).

## Getting Started

Visit [https://flama.dev/docs/getting-started/quickstart](https://flama.dev/docs/getting-started/quickstart) to get
started with Flama.

## Documentation

Visit [https://flama.dev/docs/](https://flama.dev/docs/) to view the full documentation.

## Example

```python
from flama import Flama

app = Flama(
    title="Hello-🔥",
    version="1.0",
    description="My first API",
)


@app.route("/")
def home():
    """
    tags:
        - Salute
    summary:
        Returns a warming message.
    description:
        This is a more detailed description of the method itself.
        Here we can give all the details required and they will appear
        automatically in the auto-generated docs.
    responses:
        200:
            description: Warming hello message!
    """
    return {"message": "Hello 🔥"}
```

This example will build and run a `Hello 🔥` API. To run it:

```commandline
flama run examples.hello_flama:app
```

## Authors

* José Antonio Perdiguero López ([@perdy](https://github.com/perdy/))
* Miguel Durán-Olivencia ([@migduroli](https://github.com/migduroli/))

## Contributing

This project is absolutely open to contributions so if you have a nice idea, please read
our [contributing docs](.github/CONTRIBUTING.md) **before submitting** a pull
request.
