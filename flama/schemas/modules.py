import typing as t
from pathlib import Path
from types import ModuleType

from flama import http, pagination, schemas
from flama.modules import Module
from flama.schemas.generator import SchemaGenerator

__all__ = ["SchemaModule"]

TEMPLATES_PATH = Path(__file__).parents[1] / "templates"


class SchemaModule(Module):
    name = "schema"

    def __init__(
        self,
        title: str,
        version: str,
        description: str,
        schema: t.Optional[str] = None,
        docs: t.Optional[str] = None,
    ):
        super().__init__()
        # Schema definitions
        self.schemas: t.Dict[str, t.Any] = {}

        # Schema
        self.title = title
        self.version = version
        self.description = description
        self.schema_path = schema
        self.docs_path = docs

    def register_schema(self, name: str, schema: t.Any) -> None:
        """Register a new schema.

        :param name: Schema name.
        :param schema: Schema.
        """
        self.schemas[name] = schema

    @property
    def schema_generator(self) -> SchemaGenerator:
        """Build an API Schema Generator.

        :return: API Schema Generator.
        """
        self.schemas.update({**schemas.schemas.SCHEMAS, **pagination.paginator.schemas})
        return SchemaGenerator(
            title=self.title, version=self.version, description=self.description, schemas=self.schemas
        )

    @property
    def schema(self) -> t.Dict[str, t.Any]:
        """Generate the API schema.

        :return: API schema.
        """
        return self.schema_generator.get_api_schema(self.app.routes)

    @property
    def schema_library(self) -> ModuleType:
        """Global schema library.

        :return: Schema library module.
        """
        return schemas._module.lib

    @schema_library.setter
    def schema_library(self, library: str) -> None:
        """Globally set the schema library.

        :param library: Schema library to be used.
        """
        schemas._module.setup(library)

    def add_routes(self) -> None:
        """Add schema and docs routes."""
        if self.schema_path:
            self.app.add_route(self.schema_path, self.schema_view, methods=["GET"], include_in_schema=False)
        if self.docs_path:
            assert self.schema_path, "Schema path must be defined to use docs view"
            self.app.add_route(self.docs_path, self.docs_view, methods=["GET"], include_in_schema=False)

    def schema_view(self) -> http.OpenAPIResponse:
        return http.OpenAPIResponse(self.schema)

    def docs_view(self) -> http.HTMLResponse:
        return http._ReactTemplateResponse(
            "schemas/docs.html", {"title": self.title, "schema_url": self.schema_path, "docs_url": self.docs_path}
        )
