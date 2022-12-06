import inspect
import sys
import typing as t

import pydantic
from pydantic.fields import ModelField
from pydantic.schema import field_schema, model_schema

from flama.injection import Parameter
from flama.schemas.adapter import Adapter
from flama.schemas.exceptions import SchemaGenerationError, SchemaValidationError

if sys.version_info >= (3, 10):  # PORT: Remove when stop supporting 3.9 # pragma: no cover
    from typing import TypeGuard
else:  # pragma: no cover
    from typing_extensions import TypeGuard

__all__ = ["PydanticAdapter"]

Schema = pydantic.BaseModel
Field = ModelField


class PydanticAdapter(Adapter[Schema, Field]):
    def build_field(
        self,
        name: str,
        type: t.Type,
        nullable: bool = False,
        required: bool = True,
        default: t.Any = None,
        **kwargs: t.Any
    ) -> Field:
        if not required:
            kwargs["default"] = None if default is Parameter.empty else default

        return ModelField.infer(
            name=name,
            annotation=t.Optional[type] if nullable else type,
            value=pydantic.Field(**kwargs),
            class_validators=None,
            config=pydantic.BaseConfig,
        )

    def build_schema(
        self,
        name: str = "Schema",
        schema: t.Optional[t.Union[Schema, t.Type[Schema]]] = None,
        pagination: t.Optional[t.Union[Schema, t.Type[Schema]]] = None,
        paginated_schema_name: t.Optional[str] = None,
        fields: t.Optional[t.Dict[str, Field]] = None,
    ) -> t.Type[Schema]:
        model_fields = {k: (v.type_, v.field_info) for k, v in (fields or {}).items()}

        if schema:
            model_fields.update({k: (v.type_, v.field_info) for k, v in self.unique_schema(schema).__fields__.items()})

        if pagination and schema:
            schema_cls = self.unique_schema(schema)
            model_fields = {
                **{k: (v.type_, v.field_info) for k, v in pagination.__fields__.items() if k != "data"},
                **{"data": (t.List[schema_cls], pydantic.Field(...))},
            }
            name = paginated_schema_name

        return pydantic.create_model(name, **model_fields)

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

    def to_json_schema(self, schema: t.Union[Schema, t.Type[Schema], Field]) -> t.Dict[str, t.Any]:
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

    def is_schema(self, obj: t.Any) -> TypeGuard[t.Type[Schema]]:
        return inspect.isclass(obj) and issubclass(obj, Schema)

    def is_field(self, obj: t.Any) -> TypeGuard[Field]:
        return isinstance(obj, Field)
