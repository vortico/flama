import copy
import inspect
import typing as t

import pydantic
from pydantic.fields import FieldInfo
from pydantic.json_schema import model_json_schema

from flama.injection import Parameter
from flama.schemas._libs.pydantic.fields import MAPPING
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

        annotation: t.Any = MAPPING.get(type_, type_)

        if multiple:
            annotation = list[annotation]

        if nullable:
            annotation = annotation | None

        if default is Parameter.empty:
            field = FieldInfo.from_annotation(annotation)  # ty: ignore[invalid-argument-type]
        else:
            field = FieldInfo.from_annotated_attribute(annotation, default)  # ty: ignore[invalid-argument-type]

        return field

    def build_schema(
        self,
        *,
        name: str | None = None,
        module: str | None = None,
        schema: Schema | type[Schema] | None = None,
        fields: dict[str, Field] | None = None,
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
                optional = copy.copy(field)
                optional.default = None
                fields_[name] = ((t.Any if annotation is None else annotation) | None, optional)

        return pydantic.create_model(  # ty: ignore[no-matching-overload]
            name or self.DEFAULT_SCHEMA_NAME,
            __module__=module,
            **fields_,
        )

    def validate(
        self, schema: Schema | type[Schema], values: dict[str, t.Any], *, partial: bool = False
    ) -> dict[str, t.Any]:
        schema_cls = self.unique_schema(schema)

        try:
            return schema_cls(**values).model_dump(exclude_unset=partial)
        except pydantic.ValidationError as errors:
            raise SchemaValidationError(
                errors={
                    ".".join(str(x) for x in error.get("loc", [])): {
                        **error,
                        "input": self._json_safe(error.get("input")),
                    }
                    for error in errors.errors(include_url=False)
                }
            )

    def _json_safe(self, value: t.Any) -> t.Any:
        """Recursively replace values that JSON cannot represent with their repr.

        Validation errors echo the offending value back, and for a missing field that value is the whole
        object being validated, so it may hold anything the caller passed in.

        :param value: Value to make representable.
        :return: An equivalent value that the JSON encoder accepts.
        """
        if isinstance(value, dict):
            return {k: self._json_safe(v) for k, v in value.items()}

        if isinstance(value, list | tuple | set):
            return [self._json_safe(v) for v in value]

        if isinstance(value, str | int | float | bool | None):
            return value

        return repr(value)

    def load(self, schema: Schema | type[Schema], value: dict[str, t.Any]) -> Schema:
        schema_cls = self.unique_schema(schema)

        return schema_cls(**value)

    def dump(self, schema: Schema | type[Schema], value: dict[str, t.Any]) -> dict[str, t.Any]:
        schema_cls = self.unique_schema(schema)

        return self.validate(schema_cls, value)

    def name(self, schema: Schema | type[Schema], *, prefix: str | None = None) -> str:
        schema_cls = self.unique_schema(schema)

        schema_name = f"{prefix or ''}{schema_cls.__qualname__}"
        return schema_name if schema_cls.__module__ == "builtins" else f"{schema_cls.__module__}.{schema_name}"

    def to_json_schema(self, schema: type[Schema] | Field) -> JSONSchema:
        try:
            if self.is_schema(schema):
                json_schema = model_json_schema(schema, ref_template="#/components/schemas/{model}")
                definitions = json_schema.pop("$defs", {})
            elif self.is_field(schema):
                document = model_json_schema(
                    self.build_schema(fields={"x": schema}), ref_template="#/components/schemas/{model}"
                )
                definitions = document.pop("$defs", {})
                json_schema = document["properties"]["x"]
                if not schema.title:  # Pydantic is introducing a default title, so we drop it
                    json_schema.pop("title", None)
            else:
                raise TypeError("Not a valid schema class or field")

            # A nested schema is published as a component of its own, so dropping its definition here leaves a
            # reference that still resolves. A value set is not a schema and nothing publishes it, so it is
            # inlined instead of dropped.
            return t.cast(
                JSONSchema,
                self._inline_definitions(json_schema, {k: v for k, v in definitions.items() if "enum" in v}),
            )
        except Exception as e:
            raise SchemaGenerationError from e

    def unique_schema(self, schema: Schema | type[Schema]) -> type[Schema]:
        return schema.__class__ if isinstance(schema, Schema) else schema

    def _inline_definitions(self, schema: t.Any, definitions: dict[str, t.Any]) -> t.Any:
        """Replace every reference to one of ``definitions`` with the definition itself.

        Keys already present next to the reference win over the definition, so a sibling such as a default is
        not lost when the reference it accompanies is expanded.

        :param schema: JSON Schema to walk.
        :param definitions: Definitions to inline, keyed by the name their references carry.
        :return: JSON Schema holding no reference to any of the given definitions.
        """
        if not definitions:
            return schema

        if isinstance(schema, dict):
            if (ref := schema.get("$ref")) and (definition := definitions.get(ref.rsplit("/", 1)[1])):
                return {**definition, **{k: v for k, v in schema.items() if k != "$ref"}}

            return {k: self._inline_definitions(v, definitions) for k, v in schema.items()}

        if isinstance(schema, list):
            return [self._inline_definitions(x, definitions) for x in schema]

        return schema

    def _get_field_type(self, field: Field) -> t.Any:
        if not self.is_field(field):
            return field

        if t.get_origin(field.annotation) == list:
            return self._get_field_type(t.get_args(field.annotation)[0])

        if t.get_origin(field.annotation) == dict:
            return self._get_field_type(t.get_args(field.annotation)[1])

        return field.annotation

    def schema_fields(self, schema: type[Schema]) -> dict[str, tuple[type | list[type] | dict[str, type], Field]]:
        return {name: (self._get_field_type(field), field) for name, field in schema.model_fields.items()}

    def is_schema(self, obj: t.Any) -> t.TypeGuard[type[Schema]]:
        if t.get_origin(obj):
            obj = t.get_origin(obj)

        return inspect.isclass(obj) and issubclass(obj, Schema)

    def is_field(self, obj: t.Any) -> t.TypeGuard[Field]:
        return isinstance(obj, Field)
