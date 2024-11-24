import inspect
import itertools
import typing as t
import warnings

import typesystem

from flama import compat
from flama.injection import Parameter
from flama.schemas._libs.typesystem.fields import MAPPING, MAPPING_TYPES
from flama.schemas.adapter import Adapter
from flama.schemas.exceptions import SchemaGenerationError, SchemaValidationError
from flama.types import JSONSchema

__all__ = ["TypesystemAdapter"]

Schema = typesystem.Schema
Field = typesystem.Field


class TypesystemAdapter(Adapter[Schema, Field]):
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
        if required is False and default is not Parameter.empty:
            kwargs["default"] = default

        kwargs.update({"allow_null": nullable, "title": name})

        if multiple:
            return typesystem.Array(
                (
                    typesystem.Reference(to=type_.title, definitions=typesystem.Definitions({type_.title: type_}))
                    if self.is_schema(type_)
                    else MAPPING[type_]()
                ),
                **kwargs,
            )

        return MAPPING[type_](**kwargs)

    def build_schema(  # type: ignore[return-value]
        self,
        *,
        name: t.Optional[str] = None,
        schema: t.Optional[t.Union[Schema, type[Schema]]] = None,
        fields: t.Optional[dict[str, Field]] = None,
        partial: bool = False,
    ) -> Schema:
        fields_ = {**(self.unique_schema(schema).fields if self.is_schema(schema) else {}), **(fields or {})}

        if partial:
            for field in fields_:
                fields_[field].default = None
                fields_[field].allow_null = True

        return Schema(title=name or self.DEFAULT_SCHEMA_NAME, fields=fields_)

    def validate(self, schema: Schema, values: dict[str, t.Any], *, partial: bool = False) -> t.Any:
        try:
            if partial:
                warnings.warn("Typesystem does not support partial validation")
                return schema.serialize(values)
            return schema.validate(values)
        except typesystem.ValidationError as errors:
            raise SchemaValidationError(errors={k: [v] for k, v in errors.items()})

    def load(self, schema: Schema, value: dict[str, t.Any]) -> t.Any:
        return schema.validate(value)

    def dump(self, schema: Schema, value: dict[str, t.Any]) -> t.Any:
        return self._dump(self.validate(schema, value))

    def _dump(self, value: t.Any) -> t.Any:
        if isinstance(value, list):
            return [self._dump(x) for x in value]

        return value

    def name(self, schema: Schema, *, prefix: t.Optional[str] = None) -> str:
        if not schema.title:
            raise ValueError(f"Schema '{schema}' needs to define title attribute")

        schema_name = f"{prefix or ''}{schema.title}"
        return schema_name if schema.__module__ == "builtins" else f"{schema.__module__}.{schema_name}"

    def to_json_schema(self, schema: t.Union[Schema, Field]) -> JSONSchema:
        try:
            json_schema = typesystem.to_json_schema(schema)

            if not isinstance(json_schema, dict):
                raise SchemaGenerationError

            for property in itertools.chain(json_schema.get("properties", {}).values(), [json_schema]):
                if isinstance(property.get("type"), list):
                    property["anyOf"] = [{"type": x} for x in property["type"]]
                    del property["type"]

            json_schema.pop("components", None)
        except Exception as e:
            raise SchemaGenerationError from e

        return json_schema

    def unique_schema(self, schema: Schema) -> Schema:
        return schema

    def _get_field_type(self, field: Field) -> t.Any:
        if isinstance(field, typesystem.Reference):
            return field.target

        if isinstance(field, typesystem.Array):
            return (
                [self._get_field_type(x) for x in field.items]
                if isinstance(field.items, (list, tuple, set))
                else self._get_field_type(field.items)
            )

        if isinstance(field, typesystem.Object):
            object_fields = {k: self._get_field_type(v) for k, v in field.properties.items()}
            if isinstance(field.additional_properties, (typesystem.Field, typesystem.Reference)):
                object_fields[""] = self._get_field_type(field.additional_properties)
            return object_fields

        try:
            return MAPPING_TYPES[field.__class__]
        except KeyError:
            return None

    def schema_fields(
        self, schema: Schema
    ) -> dict[
        str,
        tuple[
            t.Union[t.Union[Schema, type], list[t.Union[Schema, type]], dict[str, t.Union[Schema, type]]],
            Field,
        ],
    ]:
        return {name: (self._get_field_type(field), field) for name, field in schema.fields.items()}

    def is_schema(self, obj: t.Any) -> compat.TypeGuard[Schema]:  # PORT: Replace compat when stop supporting 3.9
        return isinstance(obj, Schema) or (inspect.isclass(obj) and issubclass(obj, Schema))

    def is_field(self, obj: t.Any) -> compat.TypeGuard[Field]:  # PORT: Replace compat when stop supporting 3.9
        return isinstance(obj, Field) or (inspect.isclass(obj) and issubclass(obj, Field))
