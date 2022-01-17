import os
import typing
from string import Template

from starlette.responses import HTMLResponse

from flama import pagination, schemas
from flama.responses import OpenAPIResponse
from flama.schemas.generator import SchemaGenerator
from flama.schemas.types import Schemas
from flama.templates import PATH as TEMPLATES_PATH

__all__ = ["AppSchemaMixin", "AppDocsMixin", "AppRedocMixin"]


class AppSchemaMixin:
    """
    Mixin for adding schema generation and endpoint to Flama application.
    """

    def add_schema_routes(
        self,
        title: str = "",
        version: str = "",
        description: str = "",
        schema: typing.Optional[str] = "/schema/",
    ):
        # Definitions
        self.schemas = Schemas({})

        # Schema
        self.title = title
        self.version = version
        self.description = description
        self.schema_url = schema
        if self.schema_url:

            def schema():
                return OpenAPIResponse(self.schema)

            self.add_route(path=self.schema_url, route=schema, methods=["GET"], include_in_schema=False)

    @property
    def schema_generator(self):
        self.schemas.update({**schemas.schemas.SCHEMAS, **pagination.SCHEMAS})
        return SchemaGenerator(
            title=self.title, version=self.version, description=self.description, schemas=self.schemas
        )

    @property
    def schema(self):
        return self.schema_generator.get_api_schema(self.routes)


class AppDocsMixin:
    """
    Mixin for adding Swagger UI based docs endpoint to Flama application.
    """

    def add_docs_route(self, docs: typing.Optional[str] = "/docs/"):
        self.docs_url = docs
        if self.docs_url:

            def swagger_ui() -> HTMLResponse:
                with open(os.path.join(TEMPLATES_PATH, "swagger_ui.html")) as f:
                    content = Template(f.read()).substitute(title=self.title, schema_url=self.schema_url)

                return HTMLResponse(content)

            self.add_route(path=self.docs_url, route=swagger_ui, methods=["GET"], include_in_schema=False)


class AppRedocMixin:
    """
    Mixin for adding Redoc based docs endpoint to Flama application.
    """

    def add_redoc_route(self, redoc: typing.Optional[str] = None):
        self.redoc_url = redoc
        if self.redoc_url:

            def redoc() -> HTMLResponse:
                with open(os.path.join(TEMPLATES_PATH, "redoc.html")) as f:
                    content = Template(f.read()).substitute(title=self.title, schema_url=self.schema_url)

                return HTMLResponse(content)

            self.add_route(path=self.redoc_url, route=redoc, methods=["GET"], include_in_schema=False)
