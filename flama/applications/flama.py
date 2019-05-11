import typing

from flama.applications.base import BaseApp
from flama.applications.schema import SchemaMixin

__all__ = ["Flama"]


class Flama(BaseApp, SchemaMixin):
    def __init__(
        self,
        title: typing.Optional[str] = "",
        version: typing.Optional[str] = "",
        description: typing.Optional[str] = "",
        schema: typing.Optional[str] = "/schema/",
        docs: typing.Optional[str] = "/docs/",
        redoc: typing.Optional[str] = None,
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)

        # Add schema and docs routes
        self.add_schema_routes(
            title=title, version=version, description=description, schema_url=schema, docs_url=docs, redoc_url=redoc
        )
