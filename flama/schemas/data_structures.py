import dataclasses
import enum
import inspect
import typing as t
from types import UnionType

from flama import compat, schemas, types
from flama.http.data_structures import UploadFile
from flama.http.responses.response import Response, StreamingResponse
from flama.injection.resolver import Parameter as InjectionParameter

__all__ = ["Field", "Schema", "Parameter", "Parameters"]


UNKNOWN = t.TypeVar("UNKNOWN")


class ParameterLocation(compat.StrEnum):  # PORT: Replace compat when stop supporting 3.10
    query = enum.auto()
    path = enum.auto()
    body = enum.auto()
    response = enum.auto()


@dataclasses.dataclass(frozen=True)
class Field:
    name: str
    type: type
    nullable: bool = dataclasses.field(init=False)
    field: t.Any = dataclasses.field(hash=False, init=False, compare=False)
    multiple: bool | None = dataclasses.field(hash=False, compare=False, default=None)
    required: bool = True
    default: t.Any = InjectionParameter.empty

    def __post_init__(self) -> None:
        annotation = types.Annotation(self.type)
        field_type = annotation.element(list)

        object.__setattr__(self, "nullable", annotation.optional or self.default is None)

        if not Schema.is_schema(field_type) and self.multiple is None:
            object.__setattr__(self, "multiple", annotation.is_multiple(list))

        object.__setattr__(
            self,
            "field",
            schemas.adapter.build_field(
                self.name,
                field_type,
                nullable=self.nullable,
                required=self.required,
                default=self.default,
                multiple=bool(self.multiple),
            ),
        )

    @classmethod
    def from_parameter(cls, parameter: InjectionParameter) -> "Field":
        return cls(
            parameter.name,
            parameter.annotation,
            required=parameter.default is InjectionParameter.empty,
            default=parameter.default
            if parameter.default is not InjectionParameter.empty
            else InjectionParameter.empty,
        )

    @classmethod
    def from_handler(cls, func: t.Callable, *, exclude: t.Container[t.Any] = ()) -> list["Field"]:
        return [
            cls.from_parameter(
                InjectionParameter(
                    name=p.name,
                    annotation=p.annotation if p.annotation is not inspect.Parameter.empty else str,
                    default=p.default if p.default is not inspect.Parameter.empty else InjectionParameter.empty,
                )
            )
            for p in inspect.signature(func).parameters.values()
            if p.annotation not in exclude
        ]

    @classmethod
    def is_field(cls, obj: t.Any) -> bool:
        return schemas.adapter.is_field(obj)

    @classmethod
    def is_http_valid_type(cls, type_: t.Any) -> bool:
        """Whether a type can be carried by a query or path parameter.

        An optional or repeated parameter is described by the type it wraps, so both are unwrapped down to the
        type actually travelling on the wire. An enum qualifies wherever a primitive does, being a string
        constrained to the set of its values.

        :param type_: Annotation to check, which a union or a subscription makes something other than a type.
        :return: True if a parameter of this type can be read from a request.
        """
        carried = types.Annotation(type_).element(list)

        # Anything still generic once the list is unwrapped names no single value, so nothing can carry it.
        if t.get_origin(carried) is not None:
            return False

        return carried in types.PARAMETERS_TYPES or (inspect.isclass(carried) and issubclass(carried, enum.Enum))

    @property
    def json_schema(self) -> types.JSONSchema:
        return schemas.adapter.to_json_schema(self.field)


@dataclasses.dataclass(frozen=True)
class Schema:
    schema: t.Any = dataclasses.field(hash=False, compare=False)

    @classmethod
    def from_type(cls, type_: type | None) -> "Schema":
        if types.is_schema(type_):
            schema = types.get_schema_metadata(type_).schema

            if types.is_schema_partial(type_):
                schema = schemas.adapter.build_schema(
                    name=schemas.adapter.name(schema, prefix="Partial").rsplit(".", 1)[1], schema=schema, partial=True
                )
        elif t.get_origin(type_) in (list, tuple, set):
            return cls.from_type(t.get_args(type_)[0])
        else:
            schema = type_

        if not schemas.adapter.is_schema(schema):
            raise ValueError("Wrong schema type")

        return cls(schema=schema)

    @classmethod
    def build(
        cls,
        name: str | None = None,
        module: str | None = None,
        schema: t.Any = None,
        fields: list[Field] | None = None,
    ) -> "Schema":
        return cls(
            schema=schemas.adapter.build_schema(
                name=name, module=module, schema=schema, fields={f.name: f.field for f in (fields or [])}
            ),
        )

    @classmethod
    def is_schema(cls, obj: t.Any) -> bool:
        return schemas.adapter.is_schema(obj)

    @property
    def name(self) -> str:
        return schemas.adapter.name(self.schema)

    def _fix_ref(self, value: str, refs: dict[str, str], root: str | None = None) -> str:
        try:
            prefix, name = value.rsplit("/", 1)
            return f"{root or prefix}/{refs[name]}"
        except KeyError:
            return value

    def _map_refs(self, schema: types.JSONField, transform: t.Callable[[str], str]) -> types.JSONField:
        """Walk a JSON Schema applying ``transform`` to every ``$ref`` value."""
        if isinstance(schema, dict):
            return {
                k: transform(t.cast(str, v)) if k == "$ref" else self._map_refs(v, transform) for k, v in schema.items()
            }

        if isinstance(schema, list | tuple | set):
            return [self._map_refs(x, transform) for x in schema]

        return schema

    def _replace_json_schema_refs(
        self, schema: types.JSONField, refs: dict[str, str], root: str | None = None
    ) -> types.JSONField:
        return self._map_refs(schema, lambda value: self._fix_ref(value, refs, root))

    def json_schema(self, names: dict[int, str], *, root: str | None = None) -> types.JSONSchema:
        return t.cast(
            types.JSONSchema,
            self._replace_json_schema_refs(
                schemas.adapter.to_json_schema(self.schema),
                {Schema(x).name.rsplit(".", 1)[1]: names[id(Schema(x).unique_schema)] for x in self.nested_schemas()},
                root,
            ),
        )

    @property
    def unique_schema(self) -> t.Any:
        return schemas.adapter.unique_schema(self.schema)

    @property
    def fields(self) -> dict[str, tuple[t.Any, t.Any]]:
        return schemas.adapter.schema_fields(self.unique_schema)

    def nested_schemas(self, schema: t.Any = UNKNOWN) -> list[t.Any]:
        if schema == UNKNOWN:
            return self.nested_schemas(self)

        if schemas.adapter.is_schema(schema):
            return [schemas.adapter.unique_schema(schema)]

        if t.get_origin(schema) in (t.Union, UnionType):
            return [x for field in t.get_args(schema) for x in self.nested_schemas(field)]

        if isinstance(schema, list | tuple | set):
            return [x for field in schema for x in self.nested_schemas(field)]

        if isinstance(schema, dict):
            return [x for field in schema.values() for x in self.nested_schemas(field)]

        if isinstance(schema, Schema):
            return [x for field_type, _ in schema.fields.values() for x in self.nested_schemas(field_type)]

        return []

    @t.overload
    def validate(self, values: None, *, partial: bool = False) -> dict[str, t.Any]: ...

    @t.overload
    def validate(self, values: dict[str, t.Any], *, partial: bool = False) -> dict[str, t.Any]: ...

    @t.overload
    def validate(self, values: list[dict[str, t.Any]], *, partial: bool = False) -> list[dict[str, t.Any]]: ...

    def validate(self, values: dict[str, t.Any] | list[dict[str, t.Any]] | None, *, partial=False):
        if isinstance(values, list | tuple):
            return [schemas.adapter.validate(self.schema, value, partial=partial) for value in values]

        return schemas.adapter.validate(self.schema, values or {}, partial=partial)

    @t.overload
    def load(self, values: dict[str, t.Any]) -> t.Any: ...

    @t.overload
    def load(self, values: list[dict[str, t.Any]]) -> list[t.Any]: ...

    def load(self, values):
        if isinstance(values, list | tuple):
            return [schemas.adapter.load(self.schema, value) for value in values]

        return schemas.adapter.load(self.schema, values)

    @t.overload
    def dump(self, values: dict[str, t.Any]) -> dict[str, t.Any]: ...

    @t.overload
    def dump(self, values: list[dict[str, t.Any]]) -> list[dict[str, t.Any]]: ...

    def dump(self, values):
        if isinstance(values, list | tuple):
            return [schemas.adapter.dump(self.schema, value) for value in values]

        return schemas.adapter.dump(self.schema, values)


@dataclasses.dataclass(frozen=True)
class Parameter:
    name: str
    location: ParameterLocation
    type: t.Any
    required: bool = True
    default: t.Any = InjectionParameter.empty
    nullable: bool = dataclasses.field(init=False)
    multiple: bool = dataclasses.field(init=False)
    # Exactly one of these is set: a parameter is described either by a schema or by a single field.
    schema: "Schema | None" = dataclasses.field(hash=False, init=False, compare=False)
    field: "Field | None" = dataclasses.field(hash=False, init=False, compare=False)
    response: "type[Response] | None" = dataclasses.field(hash=False, init=False, compare=False)

    def __post_init__(self) -> None:
        annotation = types.Annotation(self.type)

        object.__setattr__(self, "nullable", annotation.optional or self.default is None)

        origin = t.get_origin(self.type) or self.type
        response = origin if inspect.isclass(origin) and issubclass(origin, Response) else None

        if response is not None:
            # A response class carries its own media type, and a type argument, when given, the schema
            # of its payload.
            args = t.get_args(self.type)
            try:
                schema = Schema.from_type(args[0]) if args else Schema(schema=None)
            except ValueError:
                schema = Schema(schema=None)
            field = None
        else:
            try:
                schema = Schema.from_type(self.type)
                field = None
            except ValueError:
                if self.type in (None, InjectionParameter.empty):
                    schema = Schema(schema=None)
                    field = None
                else:
                    schema = None
                    field = Field(self.name, self.type, required=self.required, default=self.default)

        object.__setattr__(self, "schema", schema)
        object.__setattr__(self, "field", field)
        object.__setattr__(self, "response", response)
        object.__setattr__(self, "multiple", annotation.is_multiple(list, tuple, set, frozenset))

    @property
    def media_type(self) -> str | None:
        """Media type of the payload carried by this parameter.

        A response class declares its own, and may declare none, as a redirect does. A request body is
        multipart as soon as any of its fields is a file upload, since a binary payload cannot be
        represented in JSON. Only direct fields are inspected, because multipart is a flat format and a
        file nested inside another schema is not expressible on the wire.

        :return: The media type to advertise, or ``None`` when there is no payload to describe.
        """
        if self.response is not None:
            return self.response.media_type

        if self.schema is None or self.schema.schema is None:
            candidates = [self.type]
        else:
            candidates = [field_type for field_type, _ in self.schema.fields.values()]

        return "multipart/form-data" if any(self._is_file(x) for x in candidates) else "application/json"

    @property
    def streaming(self) -> bool:
        """Whether the payload is a sequence of frames rather than a single document.

        :return: True when each frame is to be described independently.
        """
        return self.response is not None and issubclass(self.response, StreamingResponse)

    def _is_file(self, annotation: t.Any) -> bool:
        """Whether an annotation is a file upload, or a container or union holding one.

        :param annotation: Annotation to inspect.
        :return: True when a file upload can appear under this annotation.
        """
        return annotation is UploadFile or any(self._is_file(arg) for arg in t.get_args(annotation))

    @classmethod
    def build(cls, type_: str, parameter: InjectionParameter):
        return {
            "path": cls._build_path_parameter,
            "query": cls._build_query_parameter,
            "body": cls._build_body_parameter,
            "response": cls._build_response_parameter,
        }[type_](parameter)

    @classmethod
    def _build_path_parameter(cls, parameter: InjectionParameter) -> "Parameter":
        return cls(
            name=parameter.name,
            location=ParameterLocation.path,
            type=parameter.annotation if parameter.annotation is not parameter.empty else str,
        )

    @classmethod
    def _build_query_parameter(cls, parameter: InjectionParameter) -> "Parameter":
        return cls(
            name=parameter.name,
            location=ParameterLocation.query,
            type=parameter.annotation if parameter.annotation is not parameter.empty else str,
            required=parameter.default is InjectionParameter.empty,
            default=parameter.default,
        )

    @classmethod
    def _build_body_parameter(cls, parameter: InjectionParameter) -> "Parameter":
        return cls(name=parameter.name, location=ParameterLocation.body, type=parameter.annotation)

    @classmethod
    def _build_response_parameter(cls, parameter: InjectionParameter) -> "Parameter":
        return cls(name=parameter.name, location=ParameterLocation.response, type=parameter.annotation)


Parameters = dict[str, Parameter]
