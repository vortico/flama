# Applications

Flama provides an application class that acts as an interface to interact with all functionality and configure some 
high level parameters.

```python
from flama import Flama


def home():
    """
    tags:
        - hello-world
    summary:
        Hello world.
    description:
        Basic hello world endpoint.
    responses:
        200:
            description: Hello world.
    """
    return {"hello": "world"}


app = Flama(
    components=[],                          # List of components used by this application
    debug=False,                            # Debug
    title="Puppy Register",                 # API title
    version="0.1",                          # API version
    description="A register of puppies",    # API description
    schema="/schema/",                      # Path to expose OpenAPI schema
    docs="/docs/",                          # Path to expose SwaggerUI application
    redoc="/redoc/",                        # Path to expose ReDoc application
)

app.add_route("/", home, methods=["GET"])
```

Flama application exposes the same interface than [Starlette application](https://www.starlette.io/applications/) but 
including own functionality.

### Adding Resources to the application

You can use any of the following to add handled resources and its respective routes to the application:

 * `app.add_resource(path, resource)` - Add a REST resource. The resource must be a Resource class.
 * `@app.resource(path)` - Add a REST resource, decorator style.
 
### Dependency Injector

The dependency injector is automatically created during application creation process.

 * `app.injector` - Dependency injector. 

### API Schema

The schema is generated automatically gathering all routes from the application.

 * `app.schema` - API schema.
 
!!! note
    The API schema can only be generated if `apispec` is installed as a requirement.