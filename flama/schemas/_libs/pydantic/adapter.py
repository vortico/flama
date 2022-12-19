import inspect
import sys
import typing as t

import pydantic
from pydantic.fields import ModelField
from pydantic.schema import field_schema, model_schema

from flama.injection import Parameter
from flama.schemas.adapter import Adapter
from flama.schemas.exceptions import SchemaGenerationError, SchemaValidationError
from flama.schemas.types import JSONSchema

if sys.version_info < (3, 10):  # PORT: Remove when stop supporting 3.9 # pragma: no cover
    from typing_extensions import TypeGuard

    t.TypeGuard = TypeGuard

__all__ = ["PydanticAdapter"]

Schema = pydantic.BaseModel
Field = ModelField


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

        return ModelField.infer(
            name=name,
            annotation=annotation,
            value=pydantic.Field(**kwargs),
            class_validators=None,
            config=pydantic.BaseConfig,
        )

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
                        name: (field.annotation, field.field_info)
                        for name, field in self.unique_schema(schema).__fields__.items()
                    }
                    if schema
                    else {}
                ),
                **({name: (field.annotation, field.field_info) for name, field in fields.items()} if fields else {}),
            },
        )

    def validate(self, schema: t.Union[Schema, t.Type[Schema]], values: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
        schema_cls = self.unique_schema(schema)

        try:
            return schema_cls(**values).dict()
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
                json_schema = model_schema(schema, ref_prefix="#/components/schemas/")
            elif self.is_field(schema):
                json_schema = field_schema(schema, ref_prefix="#/components/schemas/", model_name_map={})[0]
                if schema.allow_none:
                    types = [json_schema["type"]] if isinstance(json_schema["type"], str) else json_schema["type"]
                    json_schema["type"] = list(dict.fromkeys(types + ["null"]))
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
