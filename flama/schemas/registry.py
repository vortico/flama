import dataclasses
import typing as t

from flama import exceptions, types
from flama.schemas.data_structures import Schema

__all__ = ["SchemaInfo", "SchemaRegistry"]


@dataclasses.dataclass(frozen=True)
class SchemaInfo:
    name: str
    schema: t.Any

    def json_schema(self, names: dict[int, str], *, root: str | None = None) -> types.JSONSchema:
        return Schema(self.schema).json_schema(names, root=root)


class SchemaRegistry(dict[int, SchemaInfo]):
    def __init__(self, schemas: dict[str, Schema] | None = None):
        super().__init__()

        for name, schema in (schemas or {}).items():
            self.register(schema, name)

    def __contains__(self, item: t.Any) -> bool:
        return super().__contains__(id(Schema(item).unique_schema))

    def __getitem__(self, item: t.Any) -> SchemaInfo:
        """Lookup method that allows using Schema classes or instances.

        :param item: Schema to look for.
        :return: Registered schema.
        """
        return super().__getitem__(id(Schema(item).unique_schema))

    @property
    def names(self) -> dict[int, str]:
        """Returns a dictionary mapping schema ids to their names.

        :return: Schema names.
        """
        return {k: v.name for k, v in self.items()}

    def register(self, schema: Schema, name: str | None = None) -> int:
        """Register a new Schema to this registry.

        :param schema: Schema object or class.
        :param name: Schema name.
        :return: Schema ID.
        """
        if schema in self:
            raise exceptions.ApplicationError(f"Schema '{schema}' is already registered.")

        s = Schema(schema)

        try:
            schema_name = name or s.name
        except ValueError as e:  # pragma: no cover
            raise exceptions.ApplicationError("Cannot infer schema name.") from e

        schema_instance = s.unique_schema
        schema_id = id(schema_instance)
        self[schema_id] = SchemaInfo(name=schema_name, schema=schema_instance)

        for child_schema in (Schema(x) for x in s.nested_schemas() if x not in self):
            self.register(schema=child_schema.schema, name=child_schema.name)

        return schema_id

    @classmethod
    def bundle(cls, schema: t.Any, *, multiple: bool = False) -> types.JSONSchema:
        """Render ``schema`` as a self-contained JSON Schema 2020-12 document.

        Every descendant schema is inlined under ``$defs`` and all references are rewritten to local ``#/$defs``
        pointers, so the document needs no external dereferencing. When ``multiple`` is set the schema is wrapped in an
        array, keeping ``$defs`` at the document root so the local pointers still resolve.

        :param schema: Schema object or class to bundle.
        :param multiple: Whether to wrap the bundled schema in an array.
        :return: JSON Schema whose ``$ref`` pointers all resolve within the document.
        """
        registry = cls()
        root_id = registry.register(schema)
        names = registry.names

        document = t.cast("dict[str, t.Any]", registry[schema].json_schema(names, root="#/$defs"))
        defs = {info.name: info.json_schema(names, root="#/$defs") for id_, info in registry.items() if id_ != root_id}

        if multiple:
            document = {"type": "array", "items": document}

        if defs:
            document["$defs"] = defs

        return t.cast(types.JSONSchema, document)
