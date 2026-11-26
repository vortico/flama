import dataclasses
import enum
import inspect
import typing as t
from types import UnionType

from flama import _compat, types
from flama.http.data_structures import UploadFile
from flama.http.responses.response import Response, StreamingResponse
from flama.injection.resolver import Parameter as InjectionParameter
from flama.schemas.libs._libraries import libraries
from flama.types.schemas import SchemaPayload

if t.TYPE_CHECKING:
    from flama.schemas.adapter import Adapter
    from flama.schemas.libs._libraries import Library

__all__ = ["Field", "Schema", "Parameter", "Parameters"]


UNKNOWN = _compat.sentinel("UNKNOWN")


class ParameterLocation(enum.StrEnum):
    query = enum.auto()
    path = enum.auto()
    body = enum.auto()
    response = enum.auto()


@dataclasses.dataclass(frozen=True)
class Field:
    name: str
    type: _compat.TypeForm[t.Any]
    nullable: bool = dataclasses.field(init=False)
    field: t.Any = dataclasses.field(hash=False, init=False, compare=False)
    multiple: bool | None = dataclasses.field(hash=False, compare=False, default=None)
    required: bool = True
    default: t.Any = InjectionParameter.empty
    # Schema library the field is built with, the default one unless given.
    library: "Library | None" = dataclasses.field(hash=False, compare=False, default=None, kw_only=True)

    def __post_init__(self) -> None:
        annotation = types.Annotation(self.type)
        field_type = annotation.element

        object.__setattr__(self, "nullable", annotation.optional or self.default is None)
        object.__setattr__(self, "library", self.library or libraries.default)

        if not Schema.is_schema(field_type) and self.multiple is None:
            object.__setattr__(self, "multiple", annotation.is_multiple)

        object.__setattr__(
            self,
            "field",
            self.adapter.build_field(
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
            parameter.annotation if parameter.annotation is not InjectionParameter.empty else str,
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

    @property
    def adapter(self) -> "Adapter":
        return t.cast("Library", self.library).adapter

    @classmethod
    def is_field(cls, obj: t.Any) -> bool:
        return libraries.of(obj, "field") is not None

    @classmethod
    def is_http_valid_type(cls, type_: t.Any) -> bool:
        """Whether a type can be carried by a query or path parameter.

        An optional or repeated parameter is described by the type it wraps, so both are unwrapped down to the
        type actually travelling on the wire. An enum qualifies wherever a primitive does, being a string
        constrained to the set of its values.

        :param type_: Annotation to check, which a union or a subscription makes something other than a type.
        :return: True if a parameter of this type can be read from a request.
        """
        carried = types.Annotation(type_).element

        # Anything still generic once the list is unwrapped names no single value, so nothing can carry it.
        if t.get_origin(carried) is not None:
            return False

        return carried in types.PARAMETERS_TYPES or (inspect.isclass(carried) and issubclass(carried, enum.Enum))

    @property
    def json_schema(self) -> types.JSONSchema:
        return self.adapter.to_json_schema(self.field)


@dataclasses.dataclass(frozen=True)
class Schema:
    schema: t.Any = dataclasses.field(hash=False, compare=False)
    # Schema library the schema belongs to, none when there is no schema.
    library: "Library | None" = dataclasses.field(hash=False, init=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "library", libraries.of(self.schema, "schema"))

    @classmethod
    def from_type(cls, type_: _compat.TypeForm[t.Any] | SchemaPayload | None) -> "Schema":
        if (metadata := types.get_schema_metadata(type_)) is not None:
            schema = cls(metadata.schema)

            if metadata.partial and schema.library is not None:
                schema = cls(
                    schema.adapter.build_schema(
                        name=schema.adapter.name(schema.schema, prefix="Partial").rsplit(".", 1)[1],
                        schema=schema.schema,
                        partial=True,
                    )
                )
        elif t.get_origin(type_) in (list, tuple, set):
            return cls.from_type(t.get_args(type_)[0])
        else:
            schema = cls(type_)

        if schema.library is None:
            raise ValueError("Wrong schema type")

        return schema

    @classmethod
    def build(
        cls,
        name: str | None = None,
        module: str | None = None,
        schema: t.Any = None,
        fields: list[Field] | None = None,
        *,
        library: "Library | None" = None,
    ) -> "Schema":
        """Build a schema from fields, extending another schema when given.

        :param name: Schema name.
        :param module: Module the schema is named after.
        :param schema: Schema to extend.
        :param fields: Fields of the schema, built with the same library.
        :param library: Schema library to build it with, the one of the schema it extends or else the default one.
        :return: The schema built.
        """
        base = cls(schema) if schema is not None else None
        library = library or (base.library if base is not None else None) or libraries.default

        return cls(
            schema=library.adapter.build_schema(
                name=name,
                module=module,
                schema=base.schema if base is not None else None,
                fields={f.name: f.field for f in (fields or [])},
            ),
        )

    @classmethod
    def is_schema(cls, obj: t.Any) -> bool:
        return libraries.of(obj, "schema") is not None

    @property
    def adapter(self) -> "Adapter":
        """Adapter of the schema's library, or of the default one when there is no schema."""
        return (self.library or libraries.default).adapter

    @property
    def name(self) -> str:
        """The name the schema is published under.

        Flama's built-in schemas, defined in their library's package of schemas, are named in Flama's namespace after
        their library and module, ``core.APIError`` of Pydantic being ``flama.pydantic.core.APIError``, so the
        built-ins of different libraries never share a name. Any other schema is named by its library.
        """
        if self.library is not None:
            unique = self.unique_schema
            package, _, module = unique.__module__.rpartition(".")
            if package == self.library.schemas.__name__:
                return f"flama.{self.library.name}.{module}.{unique.__qualname__}"

        return self.adapter.name(self.schema)

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
                self.adapter.to_json_schema(self.schema),
                {Schema(x).name.rsplit(".", 1)[1]: names[id(Schema(x).unique_schema)] for x in self.nested_schemas()},
                root,
            ),
        )

    @property
    def unique_schema(self) -> t.Any:
        return self.adapter.unique_schema(self.schema)

    @property
    def fields(self) -> dict[str, tuple[t.Any, t.Any]]:
        return self.adapter.schema_fields(self.unique_schema)

    def nested_schemas(self, schema: t.Any = UNKNOWN) -> list[t.Any]:
        if schema is UNKNOWN:
            return self.nested_schemas(self)

        if isinstance(schema, Schema):
            return [x for field_type, _ in schema.fields.values() for x in self.nested_schemas(field_type)]

        if (library := libraries.of(schema, "schema")) is not None:
            return [library.adapter.unique_schema(schema)]

        if t.get_origin(schema) in (t.Union, UnionType, list, tuple, set, frozenset, dict):
            return [x for field in t.get_args(schema) for x in self.nested_schemas(field)]

        if isinstance(schema, list | tuple | set):
            return [x for field in schema for x in self.nested_schemas(field)]

        if isinstance(schema, dict):
            return [x for field in schema.values() for x in self.nested_schemas(field)]

        return []

    @t.overload
    def validate(self, values: None, *, partial: bool = False) -> dict[str, t.Any]: ...

    @t.overload
    def validate(self, values: dict[str, t.Any], *, partial: bool = False) -> dict[str, t.Any]: ...

    @t.overload
    def validate(self, values: list[dict[str, t.Any]], *, partial: bool = False) -> list[dict[str, t.Any]]: ...

    def validate(self, values: dict[str, t.Any] | list[dict[str, t.Any]] | None, *, partial=False):
        if isinstance(values, list | tuple):
            return [self.adapter.validate(self.schema, value, partial=partial) for value in values]

        return self.adapter.validate(self.schema, values or {}, partial=partial)

    @t.overload
    def load(self, values: dict[str, t.Any]) -> t.Any: ...

    @t.overload
    def load(self, values: list[dict[str, t.Any]]) -> list[t.Any]: ...

    def load(self, values):
        if isinstance(values, list | tuple):
            return [self.adapter.load(self.schema, value) for value in values]

        return self.adapter.load(self.schema, values)

    @t.overload
    def dump(self, values: dict[str, t.Any]) -> dict[str, t.Any]: ...

    @t.overload
    def dump(self, values: list[dict[str, t.Any]]) -> list[dict[str, t.Any]]: ...

    def dump(self, values):
        if isinstance(values, list | tuple):
            return [self.adapter.dump(self.schema, value) for value in values]

        return self.adapter.dump(self.schema, values)


@dataclasses.dataclass(frozen=True)
class Parameter:
    name: str
    location: ParameterLocation
    type: t.Any
    required: bool = True
    default: t.Any = InjectionParameter.empty
    nullable: bool = dataclasses.field(init=False)
    multiple: bool = dataclasses.field(init=False)
    # At most one of these is set: a parameter is described by a schema or by a single field, or not at all when
    # it is a response that no schema describes.
    schema: "Schema | None" = dataclasses.field(hash=False, init=False, compare=False)
    field: "Field | None" = dataclasses.field(hash=False, init=False, compare=False)
    response: "type[Response] | None" = dataclasses.field(hash=False, init=False, compare=False)

    def __post_init__(self) -> None:
        annotation = types.Annotation(self.type)

        object.__setattr__(self, "nullable", annotation.optional or self.default is None)

        origin = t.get_origin(self.type) or self.type
        response = origin if inspect.isclass(origin) and issubclass(origin, Response) else None
        # An output of any value, or a response of one of several kinds, carries a payload that is not described.
        undescribed = self.location == ParameterLocation.response and (
            self.type is t.Any
            or (
                t.get_origin(self.type) in (t.Union, UnionType)
                and all(
                    inspect.isclass(x := t.get_origin(m) or m) and issubclass(x, Response)
                    for m in t.get_args(self.type)
                )
            )
        )

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
                if self.type in (None, InjectionParameter.empty) or undescribed:
                    schema = Schema(schema=None)
                    field = None
                else:
                    schema = None
                    # A route returns nothing a schema does not describe, so a response is never a single field.
                    field = (
                        Field(self.name, self.type, required=self.required, default=self.default)
                        if self.location != ParameterLocation.response
                        else None
                    )

        # The payload is a response's type argument, and its schema metadata says nothing about how many there are.
        payload = types.Annotation(
            t.get_args(self.type)[0] if response is not None and t.get_args(self.type) else self.type
        )
        if t.get_origin(payload.type) is t.Annotated:
            payload = types.Annotation(t.get_args(payload.type)[0])

        object.__setattr__(self, "schema", schema)
        object.__setattr__(self, "field", field)
        object.__setattr__(self, "response", response)
        object.__setattr__(self, "multiple", payload.is_multiple)

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
