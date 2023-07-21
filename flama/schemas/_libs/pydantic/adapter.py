import inspect
import sys
import typing as t

import pydantic
from pydantic.fields import FieldInfo
from pydantic.json_schema import model_json_schema

from flama.injection import Parameter
from flama.schemas.adapter import Adapter
from flama.schemas.exceptions import SchemaGenerationError, SchemaValidationError
from flama.types import JSONSchema

if sys.version_info < (3, 10):  # PORT: Remove when stop supporting 3.9 # pragma: no cover
    from typing_extensions import TypeGuard

    t.TypeGuard = TypeGuard

__all__ = ["PydanticAdapter"]

Schema = pydantic.BaseModel
Field = FieldInfo


class PydanticAdapter(Adapter[Schema, Field]):
    def build_field(
        self,
        name: str,
        type_: t.Type,
        nullable: bool = False,
        required: bool = True,
        default: t.Any = None,
        multiple: bool = False,
        **kwargs,
    ) -> Field:
        if not required:
            kwargs["default"] = None if default is Parameter.empty else default

        annotation: t.Any = type_

        if multiple:
            annotation = t.List[annotation]

        if nullable:
            annotation = t.Optional[annotation]

        if default is Parameter.empty:
            field = FieldInfo.from_annotation(annotation)
        else:
            field = FieldInfo.from_annotated_attribute(annotation, default)

        return field

    def build_schema(
        self,
        *,
        name: t.Optional[str] = None,
        schema: t.Optional[t.Union[Schema, t.Type[Schema]]] = None,
        fields: t.Optional[t.Dict[str, Field]] = None,
    ) -> t.Type[Schema]:
        return pydantic.create_model(  # type: ignore
            name or self.DEFAULT_SCHEMA_NAME,
            **{
                **(
                    {
                        name: (field_info.annotation, field_info)
                        for name, field_info in self.unique_schema(schema).model_fields.items()
                    }
                    if schema
                    else {}
                ),
                **({name: (field.annotation, field) for name, field in fields.items()} if fields else {}),
            },
        )

    def validate(self, schema: t.Union[Schema, t.Type[Schema]], values: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
        schema_cls = self.unique_schema(schema)

        try:
            return schema_cls(**values).model_dump()
        except pydantic.ValidationError as errors:
            raise SchemaValidationError(errors={str(error["loc"][0]): error for error in errors.errors()})

    def load(self, schema: t.Union[Schema, t.Type[Schema]], value: t.Dict[str, t.Any]) -> Schema:
        schema_cls = self.unique_schema(schema)

        return schema_cls(**value)

    def dump(self, schema: t.Union[Schema, t.Type[Schema]], value: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
        schema_cls = self.unique_schema(schema)

        return self.validate(schema_cls, value)

    def to_json_schema(self, schema: t.Union[Schema, t.Type[Schema], Field]) -> JSONSchema:
        try:
            if self.is_schema(schema):
                json_schema = model_json_schema(schema, ref_template="#/components/schemas/{model}")
                if "$defs" in json_schema:
                    del json_schema["$defs"]
            elif self.is_field(schema):
                json_schema = model_json_schema(
                    self.build_schema(fields={"x": schema}), ref_template="#/components/schemas/{model}"
                )["properties"]["x"]
                if not schema.title:  # Pydantic is introducing a default title, so we drop it
                    del json_schema["title"]
                if "anyOf" in json_schema:  # Just simplifying type definition from anyOf to a list of types
                    json_schema["type"] = [x["type"] for x in json_schema["anyOf"]]
                    del json_schema["anyOf"]
            else:
                raise TypeError("Not a valid schema class or field")

            return json_schema
        except Exception as e:
            raise SchemaGenerationError from e

    def unique_schema(self, schema: t.Union[Schema, t.Type[Schema]]) -> t.Type[Schema]:
        return schema.__class__ if isinstance(schema, Schema) else schema

    def is_schema(self, obj: t.Any) -> t.TypeGuard[t.Type[Schema]]:
        return inspect.isclass(obj) and issubclass(obj, Schema)

    def is_field(self, obj: t.Any) -> t.TypeGuard[Field]:
        return isinstance(obj, Field)
