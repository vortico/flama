import typing
from pathlib import Path

from starlette.responses import HTMLResponse

from flama import pagination, schemas
from flama.modules import Module
from flama.responses import HTMLTemplateResponse, OpenAPIResponse
from flama.schemas.generator import SchemaGenerator

if typing.TYPE_CHECKING:
    from flama import Flama

__all__ = ["SchemaModule"]

TEMPLATES_PATH = Path(__file__).parents[1] / "templates"


class SchemaModule(Module):
    name = "schema"

    def __init__(
        self,
        app: "Flama",
        title: str,
        version: str,
        description: str,
        schema: typing.Optional[str] = None,
        docs: typing.Optional[str] = None,
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

            self.app.add_route(schema_url, schema_view, methods=["GET"], include_in_schema=False)

        # Adds docs endpoint
        if docs:
            docs_url = docs

            def docs_view() -> HTMLResponse:
                return HTMLTemplateResponse(
                    "schemas/docs.html", {"title": self.title, "schema_url": schema_url, "docs_url": docs_url}
                )

            self.app.add_route(docs_url, docs_view, methods=["GET"], include_in_schema=False)

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

    def set_schema_library(self, library: str):
        schemas._module.setup(library)
