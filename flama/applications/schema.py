import os
import typing
from string import Template

from flama.applications.base import BaseApp
from flama.responses import HTMLResponse
from flama.schemas import OpenAPIResponse, SchemaGenerator
from flama.types import asgi

__all__ = ["SchemaMixin"]


def schema(app: asgi.App):
    return OpenAPIResponse(app.schema)


def swagger_ui(app: asgi.App) -> HTMLResponse:
    with open(os.path.join(BaseApp.TEMPLATES_DIR, "swagger_ui.html")) as f:
        content = Template(f.read()).substitute(title=app._schema_title, schema_url=app._schema_url)

    return HTMLResponse(content)


def redoc(app: asgi.App) -> HTMLResponse:
    with open(os.path.join(BaseApp.TEMPLATES_DIR, "redoc.html")) as f:
        content = Template(f.read()).substitute(title=app._schema_title, schema_url=app._schema_url)

    return HTMLResponse(content)


class SchemaMixin:
    def add_schema_routes(
        self,
        title: str = "",
        version: str = "",
        description: str = "",
        schema_url: typing.Optional[str] = "/schema/",
        docs_url: typing.Optional[str] = "/docs/",
        redoc_url: typing.Optional[str] = None,
    ):
        self._schema_url = schema_url

        if self._schema_url:
            # Metadata
            self._schema_title = title
            self._schema_version = version
            self._schema_description = description

            # Schema
            self.add_route(path=schema_url, route=schema, methods=["GET"], include_in_schema=False)

            # Docs (Swagger UI)
            if docs_url:
                self.add_route(path=docs_url, route=swagger_ui, methods=["GET"], include_in_schema=False)

            # Redoc
            if redoc_url:
                self.add_route(path=redoc_url, route=redoc, methods=["GET"], include_in_schema=False)

    @property
    def schema_generator(self):
        if not hasattr(self, "_schema_generator"):
            assert getattr(self, "_schema_url", None), "Schema generation is disabled"

            self._schema_generator = SchemaGenerator(
                title=self._schema_title, version=self._schema_version, description=self._schema_description
            )

        return self._schema_generator

    @property
    def schema(self):
        return self.schema_generator.get_schema(self.routes)
