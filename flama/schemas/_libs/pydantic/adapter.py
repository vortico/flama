import inspect
import typing as t

import pydantic
from pydantic.fields import FieldInfo
from pydantic.json_schema import model_json_schema

from flama import compat
from flama.injection import Parameter
from flama.schemas.adapter import Adapter
from flama.schemas.exceptions import SchemaGenerationError, SchemaValidationError
from flama.types import JSONSchema

__all__ = ["PydanticAdapter"]

Schema = pydantic.BaseModel
Field = FieldInfo


class PydanticAdapter(Adapter[Schema, Field]):
    def build_field(
        self,
        name: str,
        type_: type,
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
            annotation = list[annotation]

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
        schema: t.Optional[t.Union[Schema, type[Schema]]] = None,
        fields: t.Optional[dict[str, type[Field]]] = None,
        partial: bool = False,
    ) -> type[Schema]:
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
        self, schema: t.Union[Schema, type[Schema]], values: dict[str, t.Any], *, partial: bool = False
    ) -> dict[str, t.Any]:
        schema_cls = self.unique_schema(schema)

        try:
            return schema_cls(**values).model_dump(exclude_unset=partial)
        except pydantic.ValidationError as errors:
            raise SchemaValidationError(
                errors={
                    ".".join(str(x) for x in error.get("loc", [])): error for error in errors.errors(include_url=False)
                }
            )

    def load(self, schema: t.Union[Schema, type[Schema]], value: dict[str, t.Any]) -> Schema:
        schema_cls = self.unique_schema(schema)

        return schema_cls(**value)

    def dump(self, schema: t.Union[Schema, type[Schema]], value: dict[str, t.Any]) -> dict[str, t.Any]:
        schema_cls = self.unique_schema(schema)

        return self.validate(schema_cls, value)

    def name(self, schema: t.Union[Schema, type[Schema]], *, prefix: t.Optional[str] = None) -> str:
        s = self.unique_schema(schema)
        schema_name = f"{prefix or ''}{s.__qualname__}"
        return schema_name if s.__module__ == "builtins" else f"{s.__module__}.{schema_name}"

    def to_json_schema(self, schema: t.Union[type[Schema], type[Field]]) -> JSONSchema:
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

    def unique_schema(self, schema: t.Union[Schema, type[Schema]]) -> type[Schema]:
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
        self, schema: type[Schema]
    ) -> dict[str, tuple[t.Union[type, list[type], dict[str, type]], Field]]:
        return {name: (self._get_field_type(field), field) for name, field in schema.model_fields.items()}

    def is_schema(self, obj: t.Any) -> compat.TypeGuard[type[Schema]]:  # PORT: Replace compat when stop supporting 3.9
        if t.get_origin(obj):
            obj = t.get_origin(obj)

        return inspect.isclass(obj) and issubclass(obj, Schema)

    def is_field(self, obj: t.Any) -> compat.TypeGuard[type[Field]]:  # PORT: Replace compat when stop supporting 3.9
        return isinstance(obj, Field)
