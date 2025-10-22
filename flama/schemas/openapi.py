import dataclasses
import typing as t

from flama import types

__all__ = [
    "Schema",
    "Reference",
    "Contact",
    "License",
    "ExternalDocs",
    "Example",
    "Tag",
    "Info",
    "ServerVariable",
    "Server",
    "Link",
    "Security",
    "Callback",
    "Header",
    "Parameter",
    "Encoding",
    "MediaType",
    "RequestBody",
    "Response",
    "Responses",
    "Operation",
    "Path",
    "Paths",
    "Components",
    "OpenAPI",
    "OpenAPISpec",
]

empty = types.Empty()


class Schema(types.JSONSchema): ...


@dataclasses.dataclass(frozen=True)
class Reference:
    ref: str


@dataclasses.dataclass(frozen=True)
class Contact:
    name: str | None = None
    url: str | None = None
    email: str | None = None

    @classmethod
    def from_spec(cls, spec: types.OpenAPISpecInfoContact, /) -> "Contact":
        return cls(**spec)


@dataclasses.dataclass(frozen=True)
class License:
    name: str
    identifier: str | None = None
    url: str | None = None

    @classmethod
    def from_spec(cls, spec: types.OpenAPISpecInfoLicense, /) -> "License":
        return cls(**spec)


@dataclasses.dataclass(frozen=True)
class ExternalDocs:
    url: str
    description: str | None = None

    @classmethod
    def from_spec(cls, spec: types.OpenAPISpecExternalDocs, /) -> "ExternalDocs":
        return cls(**spec)


@dataclasses.dataclass(frozen=True)
class Example:
    summary: str | None = None
    description: str | None = None
    value: t.Any | None = None
    externalValue: str | None = None


@dataclasses.dataclass(frozen=True)
class Tag:
    name: str
    description: str | None = None
    externalDocs: ExternalDocs | None = None

    @classmethod
    def from_spec(cls, spec: types.OpenAPISpecTag, /) -> "Tag":
        return cls(
            name=spec["name"],
            description=spec.get("description"),
            externalDocs=(
                ExternalDocs.from_spec(t.cast(types.OpenAPISpecExternalDocs, spec.get("externalDocs")))
                if "externalDocs" in spec
                else None
            ),
        )


@dataclasses.dataclass(frozen=True)
class Info:
    title: str
    version: str
    summary: str | None = None
    description: str | None = None
    termsOfService: str | None = None
    contact: Contact | None = None
    license: License | None = None

    @classmethod
    def from_spec(cls, spec: types.OpenAPISpecInfo) -> "Info":
        return cls(
            title=spec["title"],
            version=spec["version"],
            summary=spec.get("summary"),
            description=spec.get("description"),
            termsOfService=spec.get("termsOfService"),
            contact=(
                Contact.from_spec(t.cast(types.OpenAPISpecInfoContact, spec["contact"])) if "contact" in spec else None
            ),
            license=(
                License.from_spec(t.cast(types.OpenAPISpecInfoLicense, spec["license"])) if "license" in spec else None
            ),
        )


@dataclasses.dataclass(frozen=True)
class ServerVariable:
    default: str
    enum: list[str] | None = None
    description: str | None = None

    @classmethod
    def from_spec(cls, spec: types.OpenAPISpecServerVariable, /) -> "ServerVariable":
        return cls(**spec)


@dataclasses.dataclass(frozen=True)
class Server:
    url: str
    description: str | None = None
    variables: dict[str, ServerVariable] | None = None

    @classmethod
    def from_spec(cls, spec: types.OpenAPISpecServer, /) -> "Server":
        return cls(
            url=spec["url"],
            description=spec.get("description"),
            variables=(
                {
                    name: ServerVariable.from_spec(t.cast(types.OpenAPISpecServerVariable, variable))
                    for name, variable in spec["variables"].items()
                }
                if "variables" in spec and spec["variables"]
                else None
            ),
        )


@dataclasses.dataclass(frozen=True)
class Link:
    operationRef: str | None = None
    operationId: str | None = None
    parameters: dict[str, t.Any] | None = None
    requestBody: t.Any | None = None
    description: str | None = None
    server: Server | None = None


class Security(dict[str, list[str]]): ...


class Callback(dict[str, "Path"]): ...


@dataclasses.dataclass(frozen=True)
class Header:
    description: str | None = None
    required: bool | None = None
    deprecated: bool | None = None
    allowEmptyValue: bool | None = None
    style: str | None = None
    explode: bool | None = None
    allowReserved: bool | None = None
    schema: Schema | Reference | None = None
    example: t.Any | None = None
    examples: dict[str, Example | Reference] | None = None


@dataclasses.dataclass(frozen=True)
class Parameter:
    name: str
    in_: str
    description: str | None = None
    required: bool | None = None
    deprecated: bool | None = None
    allowEmptyValue: bool | None = None
    style: str | None = None
    explode: bool | None = None
    allowReserved: bool | None = None
    schema: Schema | Reference | None = None
    example: t.Any | None = None
    examples: dict[str, Example | Reference] | None = None


@dataclasses.dataclass(frozen=True)
class Encoding:
    contentType: str | None = None
    headers: dict[str, Header | Reference] | None = None
    style: str | None = None
    explode: bool | None = None
    allowReserved: bool | None = None


@dataclasses.dataclass(frozen=True)
class MediaType:
    schema: Schema | Reference | None = None
    example: t.Any | None = None
    examples: dict[str, t.Any | Reference] | None = None
    encoding: dict[str, Encoding] | None = None


@dataclasses.dataclass(frozen=True)
class RequestBody:
    content: dict[str, MediaType]
    description: str | None = None
    required: bool | None = None


@dataclasses.dataclass(frozen=True)
class Response:
    description: str
    headers: dict[str, Header | Reference] | None = None
    content: dict[str, MediaType] | None = None
    links: dict[str, Link | Reference] | None = None


class Responses(dict[str, Response]): ...


@dataclasses.dataclass(frozen=True)
class Operation:
    responses: Responses
    tags: list[str] | None = None
    summary: str | None = None
    description: str | None = None
    externalDocs: ExternalDocs | None = None
    operationId: str | None = None
    parameters: list[Parameter | Reference] | None = None
    requestBody: RequestBody | Reference | None = None
    callbacks: dict[str, Callback | Reference] | None = None
    deprecated: bool | None = None
    security: list[Security] | None = None
    servers: list[Server] | None = None


@dataclasses.dataclass(frozen=True)
class Path:
    ref: str | None = None
    summary: str | None = None
    description: str | None = None
    get: Operation | None = None
    put: Operation | None = None
    post: Operation | None = None
    delete: Operation | None = None
    options: Operation | None = None
    head: Operation | None = None
    patch: Operation | None = None
    trace: Operation | None = None
    servers: list[Server] | None = None
    parameters: list[Parameter | Reference] | None = None

    @property
    def operations(self) -> dict[str, Operation]:
        return {
            x: getattr(self, x)
            for x in ("get", "put", "post", "delete", "options", "head", "patch", "trace")
            if getattr(self, x) is not None
        }


class Paths(dict[str, Path]): ...


@dataclasses.dataclass(frozen=True)
class Components:
    schemas: dict[str, Schema | Reference]
    responses: dict[str, Response | Reference]
    parameters: dict[str, Parameter | Reference]
    examples: dict[str, Example | Reference]
    requestBodies: dict[str, RequestBody | Reference]
    headers: dict[str, Header | Reference]
    securitySchemes: dict[str, Security | Reference]
    links: dict[str, Link | Reference]
    callbacks: dict[str, Callback | Reference]


@dataclasses.dataclass(frozen=True)
class OpenAPI:
    openapi: str
    info: Info
    paths: Paths
    components: Components
    servers: list[Server] | None = None
    security: list[Security] | None = None
    tags: list[Tag] | None = None
    externalDocs: ExternalDocs | None = None


class OpenAPISpec:
    OPENAPI_VERSION = "3.1.0"

    def __init__(
        self,
        info: Info,
        *,
        servers: list[Server] | None = None,
        security: list[Security] | None = None,
        tags: list[Tag] | None = None,
        externalDocs: ExternalDocs | None = None,
    ):
        self.spec = OpenAPI(
            openapi=self.OPENAPI_VERSION,
            info=info,
            paths=Paths({}),
            components=Components(
                schemas={},
                responses={},
                parameters={},
                examples={},
                requestBodies={},
                headers={},
                securitySchemes={},
                links={},
                callbacks={},
            ),
            servers=servers,
            security=security,
            tags=tags,
            externalDocs=externalDocs,
        )

    @classmethod
    def from_spec(cls, spec: types.OpenAPISpec, /) -> "OpenAPISpec":
        return cls(
            info=Info.from_spec(spec["info"]),
            servers=(
                [Server.from_spec(t.cast(types.OpenAPISpecServer, server)) for server in spec["servers"]]
                if "servers" in spec and spec["servers"]
                else None
            ),
            security=(
                [Security(security) for security in spec["security"]]
                if "security" in spec and spec["security"]
                else None
            ),
            tags=[Tag.from_spec(tag) for tag in spec["tags"]] if "tags" in spec and spec["tags"] else None,
            externalDocs=(
                ExternalDocs.from_spec(t.cast(types.OpenAPISpecExternalDocs, spec.get("externalDocs")))
                if "externalDocs" in spec
                else None
            ),
        )

    def add_path(self, path: str, item: Path):
        self.spec.paths[path] = item

    def add_schema(self, name: str, item: Schema | Reference):
        self.spec.components.schemas[name] = item

    def add_response(self, name: str, item: Response | Reference):
        self.spec.components.responses[name] = item

    def add_parameter(self, name: str, item: Parameter | Reference):
        self.spec.components.parameters[name] = item

    def add_example(self, name: str, item: Example | Reference):
        self.spec.components.examples[name] = item

    def add_request_body(self, name: str, item: RequestBody | Reference):
        self.spec.components.requestBodies[name] = item

    def add_header(self, name: str, item: Header | Reference):
        self.spec.components.headers[name] = item

    def add_security(self, name: str, item: Security | Reference):
        self.spec.components.securitySchemes[name] = item

    def add_link(self, name: str, item: Link | Reference):
        self.spec.components.links[name] = item

    def add_callback(self, name: str, item: Callback | Reference):
        self.spec.components.callbacks[name] = item

    def to_dict(self, obj: t.Any = empty) -> t.Any:
        if obj is empty:
            return self.to_dict(dataclasses.asdict(self.spec))

        if isinstance(obj, list):
            return [self.to_dict(i) for i in obj]

        if isinstance(obj, dict):
            return {{"ref": "$ref", "in_": "in"}.get(k, k): self.to_dict(v) for k, v in obj.items() if v is not None}

        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return self.to_dict(dataclasses.asdict(obj))

        return obj
