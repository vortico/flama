import os
import typing
from string import Template

from starlette.responses import HTMLResponse

from flama import pagination, schemas
from flama.modules import Module
from flama.responses import OpenAPIResponse
from flama.schemas.generator import SchemaGenerator
from flama.templates import PATH as TEMPLATES_PATH

if typing.TYPE_CHECKING:
    from flama import Flama

__all__ = ["SchemaModule"]


class SchemaModule(Module):
    name = "schema"

    def __init__(
        self,
        app: "Flama",
        title: str = "",
        version: str = "",
        description: str = "",
        schema: typing.Optional[str] = "/schema/",
        docs: typing.Optional[str] = "/docs/",
        redoc: typing.Optional[str] = None,
        *args,
        **kwargs
    ):
        super().__init__(app, *args, **kwargs)
        # Schema definitions
        self.schemas: typing.Dict[str, typing.Any] = {}

        # Schema
        self.title = title
        self.version = version
        self.description = description

        # Adds schema endpoint
        if schema:
            schema_url = schema

            def schema_view():
                return OpenAPIResponse(self.schema)

            self.app.add_route(path=schema_url, route=schema_view, methods=["GET"], include_in_schema=False)

        # Adds swagger ui endpoint
        if docs:
            docs_url = docs

            def swagger_ui() -> HTMLResponse:
                with open(os.path.join(TEMPLATES_PATH, "swagger_ui.html")) as f:
                    content = Template(f.read()).substitute(title=self.title, schema_url=schema_url)

                return HTMLResponse(content)

            self.app.add_route(path=docs_url, route=swagger_ui, methods=["GET"], include_in_schema=False)

        # Adds redoc endpoint
        if redoc:
            redoc_url = redoc

            def redoc_view() -> HTMLResponse:
                with open(os.path.join(TEMPLATES_PATH, "redoc.html")) as f:
                    content = Template(f.read()).substitute(title=self.title, schema_url=schema_url)

                return HTMLResponse(content)

            self.app.add_route(path=redoc_url, route=redoc_view, methods=["GET"], include_in_schema=False)

    def register_schema(self, name: str, schema):
        self.schemas[name] = schema

    @property
    def schema_generator(self) -> SchemaGenerator:
        self.schemas.update({**schemas.schemas.SCHEMAS, **pagination.paginator.schemas})
        return SchemaGenerator(
            title=self.title, version=self.version, description=self.description, schemas=self.schemas
        )

    @property
    def schema(self) -> typing.Dict[str, typing.Any]:
        return self.schema_generator.get_api_schema(self.app.routes)
