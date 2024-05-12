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

    t.TypeGuard = TypeGuard  # type: ignore

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
        fields: t.Optional[t.Dict[str, t.Type[Field]]] = None,
        partial: bool = False,
    ) -> t.Type[Schema]:
        fields_ = {
            **{
                name: (field.annotation, field)
                for name, field in (self.unique_schema(schema).model_fields.items() if self.is_schema(schema) else {})
            },
            **{name: (field.annotation, field) for name, field in (fields.items() if fields else {})},
        }

        if partial:
            for name, (annotation, field) in fields_.items():
                field.default = None
                fields_[name] = (t.Optional[annotation], field)

        return pydantic.create_model(name or self.DEFAULT_SCHEMA_NAME, **fields_)

    def validate(
        self, schema: t.Union[Schema, t.Type[Schema]], values: t.Dict[str, t.Any], *, partial: bool = False
    ) -> t.Dict[str, t.Any]:
        schema_cls = self.unique_schema(schema)

        try:
            return schema_cls(**values).model_dump(exclude_unset=partial)
        except pydantic.ValidationError as errors:
            raise SchemaValidationError(errors={str(error["loc"][0]): error for error in errors.errors()})

    def load(self, schema: t.Union[Schema, t.Type[Schema]], value: t.Dict[str, t.Any]) -> Schema:
        schema_cls = self.unique_schema(schema)

        return schema_cls(**value)

    def dump(self, schema: t.Union[Schema, t.Type[Schema]], value: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
        schema_cls = self.unique_schema(schema)

        return self.validate(schema_cls, value)

    def name(self, schema: t.Union[Schema, t.Type[Schema]], *, prefix: t.Optional[str] = None) -> str:
        s = self.unique_schema(schema)
        schema_name = f"{prefix or ''}{s.__qualname__}"
        return schema_name if s.__module__ == "builtins" else f"{s.__module__}.{schema_name}"

    def to_json_schema(self, schema: t.Union[t.Type[Schema], t.Type[Field]]) -> JSONSchema:
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
            else:
                raise TypeError("Not a valid schema class or field")

            return json_schema
        except Exception as e:
            raise SchemaGenerationError from e

    def unique_schema(self, schema: t.Union[Schema, t.Type[Schema]]) -> t.Type[Schema]:
        return schema.__class__ if isinstance(schema, Schema) else schema

    def _get_field_type(self, field: Field) -> t.Any:
        if not self.is_field(field):
            return field

        if t.get_origin(field.annotation) == list:
            return self._get_field_type(t.get_args(field.annotation)[0])

        if t.get_origin(field.annotation) == dict:
            return self._get_field_type(t.get_args(field.annotation)[1])

        return field.annotation

    def schema_fields(
        self, schema: t.Type[Schema]
    ) -> t.Dict[str, t.Tuple[t.Union[t.Type, t.List[t.Type], t.Dict[str, t.Type]], Field]]:
        return {name: (self._get_field_type(field), field) for name, field in schema.model_fields.items()}

    def is_schema(
        self, obj: t.Any
    ) -> t.TypeGuard[t.Type[Schema]]:  # type: ignore # PORT: Remove this comment when stop supporting 3.9
        return inspect.isclass(obj) and issubclass(obj, Schema)

    def is_field(
        self, obj: t.Any
    ) -> t.TypeGuard[t.Type[Field]]:  # type: ignore # PORT: Remove this comment when stop supporting 3.9
        return isinstance(obj, Field)
