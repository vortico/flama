import inspect
import sys
import typing as t

import typesystem

from flama.injection import Parameter
from flama.schemas._libs.typesystem.fields import MAPPING, MAPPING_TYPES
from flama.schemas.adapter import Adapter
from flama.schemas.exceptions import SchemaGenerationError, SchemaValidationError
from flama.types import JSONSchema

if sys.version_info < (3, 10):  # PORT: Remove when stop supporting 3.9 # pragma: no cover
    from typing_extensions import TypeGuard

    t.TypeGuard = TypeGuard  # type: ignore

__all__ = ["TypesystemAdapter"]

Schema = typesystem.Schema
Field = typesystem.Field


class TypesystemAdapter(Adapter[Schema, Field]):
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

    @t.no_type_check
    def build_schema(
        self,
        name: t.Optional[str] = None,
        schema: t.Optional[t.Union[Schema, t.Type[Schema]]] = None,
        fields: t.Optional[t.Dict[str, Field]] = None,
    ) -> Schema:
        return Schema(
            title=name or self.DEFAULT_SCHEMA_NAME,
            fields={**(self.unique_schema(schema).fields if self.is_schema(schema) else {}), **(fields or {})},
        )

    @t.no_type_check
    def validate(self, schema: Schema, values: t.Dict[str, t.Any]) -> t.Any:
        try:
            return schema.validate(values)
        except typesystem.ValidationError as errors:
            raise SchemaValidationError(errors={k: [v] for k, v in errors.items()})

    @t.no_type_check
    def load(self, schema: Schema, value: t.Dict[str, t.Any]) -> t.Any:
        return schema.validate(value)

    @t.no_type_check
    def dump(self, schema: Schema, value: t.Dict[str, t.Any]) -> t.Any:
        return self._dump(self.validate(schema, value))

    def _dump(self, value: t.Any) -> t.Any:
        if isinstance(value, list):
            return [self._dump(x) for x in value]

        return value

    @t.no_type_check
    def name(self, schema: Schema) -> str:
        if not schema.title:
            raise ValueError(f"Schema '{schema}' needs to define title attribute")

        return schema.title if schema.__module__ == "builtins" else f"{schema.__module__}.{schema.title}"

    @t.no_type_check
    def to_json_schema(self, schema: t.Union[Schema, Field]) -> JSONSchema:
        try:
            json_schema = typesystem.to_json_schema(schema)

            if not isinstance(json_schema, dict):
                raise SchemaGenerationError

            json_schema.pop("components", None)
        except Exception as e:
            raise SchemaGenerationError from e

        return json_schema

    @t.no_type_check
    def unique_schema(self, schema: Schema) -> Schema:
        return schema

    def _get_field_type(
        self, field: Field
    ) -> t.Union[t.Union[Schema, t.Type], t.List[t.Union[Schema, t.Type]], t.Dict[str, t.Union[Schema, t.Type]]]:
        if isinstance(field, typesystem.Reference):
            return field.target

        if isinstance(field, typesystem.Array):
            return (
                [self._get_field_type(x) for x in field.items]
                if isinstance(field.items, (list, tuple, set))
                else self._get_field_type(field.items)
            )

        if isinstance(field, typesystem.Object):
            return {k: self._get_field_type(v) for k, v in field.properties.items()}

        try:
            return MAPPING_TYPES[field.__class__]
        except KeyError:
            return None

    @t.no_type_check
    def schema_fields(
        self, schema: Schema
    ) -> t.Dict[
        str,
        t.Tuple[
            t.Union[t.Union[Schema, t.Type], t.List[t.Union[Schema, t.Type]], t.Dict[str, t.Union[Schema, t.Type]]],
            Field,
        ],
    ]:
        return {name: (self._get_field_type(field), field) for name, field in schema.fields.items()}

    @t.no_type_check
    def is_schema(
        self, obj: t.Any
    ) -> t.TypeGuard[Schema]:  # type: ignore # PORT: Remove this comment when stop supporting 3.9
        return isinstance(obj, Schema) or (inspect.isclass(obj) and issubclass(obj, Schema))

    @t.no_type_check
    def is_field(
        self, obj: t.Any
    ) -> t.TypeGuard[Field]:  # type: ignore # PORT: Remove this comment when stop supporting 3.9
        return isinstance(obj, Field) or (inspect.isclass(obj) and issubclass(obj, Field))
