# API Schemas

Flama includes optional support for generating [OpenAPI schemas][OpenAPI], using `apispec` and `pyyaml` libraries.
 
The Schema generator gathers all the API information needed directly from your code and infers the schema that 
represents your API based on [OpenAPI] standard. The schema will be also served under `/schema/` route by default, but it 
is absolutety configurable.

## The Schema Generation

Let's take a look at how the API schema is generated with an example that includes all the pieces involved in the 
process.

The API used for this example will consist of a collection of puppies and some methods for handling it.

### Data Schemas

First we define the data schemas that will be used to validate the inputs in our API.

In our case we only need a single schema for defining a `Puppy` with a small set of attributes.

```python
from marshmallow import Schema, fields, validate


class Puppy(Schema):
    id = fields.Integer()
    name = fields.String()
    age = fields.Integer(validate=validate.Range(min=0))
```

### Routes

Now that we have a proper input validation we can use those schemas to define the functions associated to each route in 
our API.

In that case we are going to define a couple of endpoints, a first one for listing a collection and a second for 
creating a new resource in that collection.

Our goal is to describe our API using a schema inferred directly from our codebase so our functions needs to be well 
documented using docstrings, that will be appended to our API schema following [OpenAPI] format.

Regarding to our data schemas previously defined and used as annotations in our functions, it will be automatically 
inspected and will be part of the information of our endpoints.

```python
from . import schemas


def list_puppies(name: str = None) -> schemas.Puppy(many=True):
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
    

def create_puppy(puppy: schemas.Puppy) -> schemas.Puppy:
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
```


### Application

The last step is to define our main application and configure the highest level information of our schema, such 
as the title, version and a description, as well as the path use to serve it.

```python
from flama.applications import Flama

from . import views


app = Flama(
    title="Puppy Register",               # API title
    version="0.1",                        # API version
    description="A register of puppies",  # API description
    schema="/schema/",                    # Path to expose OpenAPI schema
)


app.add_route("/", views.list_puppies, methods=["GET"])
app.add_route("/", views.create_puppy, methods=["POST"])
```

### Schema

And here is the result schema of our example.

```yaml
components:
  schemas:
    APIError:
      properties:
        detail:
          description: Error detail
          title: detail
          type: string
        error:
          description: Exception or error type
          title: type
          type: string
        status_code:
          description: HTTP status code
          format: int32
          title: status_code
          type: integer
      required:
      - detail
      - status_code
      type: object
    Puppy:
      properties:
        age:
          format: int32
          minimum: 0
          type: integer
        id:
          format: int32
          type: integer
        name:
          type: string
      type: object
info:
  description: A register of puppies
  title: Puppy Register
  version: '0.1'
openapi: 3.0.0
paths:
  /:
    get:
      description: List the puppies collection. There is an optional query parameter
        that specifies a name for filtering the collection based on it.
      parameters:
      - in: query
        name: name
        required: false
        schema:
          default: null
          nullable: true
          type: string
      responses:
        '200':
          content:
            application/json:
              schema:
                items:
                  $ref: '#/components/schemas/Puppy'
                type: array
          description: List puppies.
        default:
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/APIError'
          description: Unexpected error.
      summary: List puppies.
      tags:
      - puppy
    post:
      description: Create a new puppy using data validated from request body and add
        it to the collection.
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/Puppy'
      responses:
        '200':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Puppy'
          description: Puppy created successfully.
        default:
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/APIError'
          description: Unexpected error.
      summary: Create a new puppy.
      tags:
      - puppy
```

## Disable Schema

You can disable the schema generation by using `None` value for the `schema` argument.

```python
from flama.applications import Flama

app = Flama(
    title="Puppy Register",               # API title
    version="0.1",                        # API version
    description="A register of puppies",  # API description
    schema=None,                          # Disable api schema generation
)
```

## Swagger UI

Swagger UI is a collection of HTML, Javascript, and CSS assets that dynamically generate beautiful documentation from a 
Swagger-compliant API. It's fully integrated with your application and can be served under an specific path 
simply configuring a single parameter.

```python
from flama.applications import Flama

app = Flama(
    title="Puppy Register",               # API title
    version="0.1",                        # API version
    description="A register of puppies",  # API description
    schema="/schema/",                    # Path to expose OpenAPI schema
    docs="/docs/",                        # Path to expose SwaggerUI application
)
```

![](https://raw.githubusercontent.com/perdy/flama/master/docs/images/swaggerui.gif)

## ReDoc

ReDoc is an OpenAPI/Swagger-generated API Reference Documentation, a well-built application to serve your API docs 
based on your API schema. It's fully integrated with your application and can be served under an specific path 
simply configuring a single parameter.

```python
from flama.applications import Flama

app = Flama(
    title="Puppy Register",               # API title
    version="0.1",                        # API version
    description="A register of puppies",  # API description
    schema="/schema/",                    # Path to expose OpenAPI schema
    redoc="/redoc/",                      # Path to expose ReDoc application
)
```

![](https://raw.githubusercontent.com/perdy/flama/master/docs/images/redoc.gif)

[OpenAPI]: https://github.com/OAI/OpenAPI-Specification
[Swagger UI]: https://swagger.io/tools/swagger-ui/
[ReDoc]: https://rebilly.github.io/ReDoc/
