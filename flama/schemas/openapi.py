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

Schema = t.NewType("Schema", types.JSONSchema)


@dataclasses.dataclass(frozen=True)
class Reference:
    ref: str


@dataclasses.dataclass(frozen=True)
class Contact:
    name: t.Optional[str] = None
    url: t.Optional[str] = None
    email: t.Optional[str] = None

    @classmethod
    def from_spec(cls, spec: types.OpenAPISpecInfoContact, /) -> "Contact":
        return cls(**spec)


@dataclasses.dataclass(frozen=True)
class License:
    name: str
    identifier: t.Optional[str] = None
    url: t.Optional[str] = None

    @classmethod
    def from_spec(cls, spec: types.OpenAPISpecInfoLicense, /) -> "License":
        return cls(**spec)


@dataclasses.dataclass(frozen=True)
class ExternalDocs:
    url: str
    description: t.Optional[str] = None

    @classmethod
    def from_spec(cls, spec: types.OpenAPISpecExternalDocs, /) -> "ExternalDocs":
        return cls(**spec)


@dataclasses.dataclass(frozen=True)
class Example:
    summary: t.Optional[str] = None
    description: t.Optional[str] = None
    value: t.Optional[t.Any] = None
    externalValue: t.Optional[str] = None


@dataclasses.dataclass(frozen=True)
class Tag:
    name: str
    description: t.Optional[str] = None
    externalDocs: t.Optional[ExternalDocs] = None

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
    summary: t.Optional[str] = None
    description: t.Optional[str] = None
    termsOfService: t.Optional[str] = None
    contact: t.Optional[Contact] = None
    license: t.Optional[License] = None

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
    enum: t.Optional[list[str]] = None
    description: t.Optional[str] = None

    @classmethod
    def from_spec(cls, spec: types.OpenAPISpecServerVariable, /) -> "ServerVariable":
        return cls(**spec)


@dataclasses.dataclass(frozen=True)
class Server:
    url: str
    description: t.Optional[str] = None
    variables: t.Optional[dict[str, ServerVariable]] = None

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
    operationRef: t.Optional[str] = None
    operationId: t.Optional[str] = None
    parameters: t.Optional[dict[str, t.Any]] = None
    requestBody: t.Optional[t.Any] = None
    description: t.Optional[str] = None
    server: t.Optional[Server] = None


Security = t.NewType("Security", dict[str, list[str]])
Callback = t.NewType("Callback", dict[str, "Path"])


@dataclasses.dataclass(frozen=True)
class Header:
    description: t.Optional[str] = None
    required: t.Optional[bool] = None
    deprecated: t.Optional[bool] = None
    allowEmptyValue: t.Optional[bool] = None
    style: t.Optional[str] = None
    explode: t.Optional[bool] = None
    allowReserved: t.Optional[bool] = None
    schema: t.Optional[t.Union[Schema, Reference]] = None
    example: t.Optional[t.Any] = None
    examples: t.Optional[dict[str, t.Union[Example, Reference]]] = None


@dataclasses.dataclass(frozen=True)
class Parameter:
    name: str
    in_: str
    description: t.Optional[str] = None
    required: t.Optional[bool] = None
    deprecated: t.Optional[bool] = None
    allowEmptyValue: t.Optional[bool] = None
    style: t.Optional[str] = None
    explode: t.Optional[bool] = None
    allowReserved: t.Optional[bool] = None
    schema: t.Optional[t.Union[Schema, Reference]] = None
    example: t.Optional[t.Any] = None
    examples: t.Optional[dict[str, t.Union[Example, Reference]]] = None


@dataclasses.dataclass(frozen=True)
class Encoding:
    contentType: t.Optional[str] = None
    headers: t.Optional[dict[str, t.Union[Header, Reference]]] = None
    style: t.Optional[str] = None
    explode: t.Optional[bool] = None
    allowReserved: t.Optional[bool] = None


@dataclasses.dataclass(frozen=True)
class MediaType:
    schema: t.Optional[t.Union[Schema, Reference]] = None
    example: t.Optional[t.Any] = None
    examples: t.Optional[dict[str, t.Union[t.Any, Reference]]] = None
    encoding: t.Optional[dict[str, Encoding]] = None


@dataclasses.dataclass(frozen=True)
class RequestBody:
    content: dict[str, MediaType]
    description: t.Optional[str] = None
    required: t.Optional[bool] = None


@dataclasses.dataclass(frozen=True)
class Response:
    description: str
    headers: t.Optional[dict[str, t.Union[Header, Reference]]] = None
    content: t.Optional[dict[str, MediaType]] = None
    links: t.Optional[dict[str, t.Union[Link, Reference]]] = None


Responses = t.NewType("Responses", dict[str, Response])


@dataclasses.dataclass(frozen=True)
class Operation:
    responses: Responses
    tags: t.Optional[list[str]] = None
    summary: t.Optional[str] = None
    description: t.Optional[str] = None
    externalDocs: t.Optional[ExternalDocs] = None
    operationId: t.Optional[str] = None
    parameters: t.Optional[list[t.Union[Parameter, Reference]]] = None
    requestBody: t.Optional[t.Union[RequestBody, Reference]] = None
    callbacks: t.Optional[dict[str, t.Union[Callback, Reference]]] = None
    deprecated: t.Optional[bool] = None
    security: t.Optional[list[Security]] = None
    servers: t.Optional[list[Server]] = None


@dataclasses.dataclass(frozen=True)
class Path:
    ref: t.Optional[str] = None
    summary: t.Optional[str] = None
    description: t.Optional[str] = None
    get: t.Optional[Operation] = None
    put: t.Optional[Operation] = None
    post: t.Optional[Operation] = None
    delete: t.Optional[Operation] = None
    options: t.Optional[Operation] = None
    head: t.Optional[Operation] = None
    patch: t.Optional[Operation] = None
    trace: t.Optional[Operation] = None
    servers: t.Optional[list[Server]] = None
    parameters: t.Optional[list[t.Union[Parameter, Reference]]] = None

    @property
    def operations(self) -> dict[str, Operation]:
        return {
            x: getattr(self, x)
            for x in ("get", "put", "post", "delete", "options", "head", "patch", "trace")
            if getattr(self, x) is not None
        }


Paths = t.NewType("Paths", dict[str, Path])


@dataclasses.dataclass(frozen=True)
class Components:
    schemas: dict[str, t.Union[Schema, Reference]]
    responses: dict[str, t.Union[Response, Reference]]
    parameters: dict[str, t.Union[Parameter, Reference]]
    examples: dict[str, t.Union[Example, Reference]]
    requestBodies: dict[str, t.Union[RequestBody, Reference]]
    headers: dict[str, t.Union[Header, Reference]]
    securitySchemes: dict[str, t.Union[Security, Reference]]
    links: dict[str, t.Union[Link, Reference]]
    callbacks: dict[str, t.Union[Callback, Reference]]


@dataclasses.dataclass(frozen=True)
class OpenAPI:
    openapi: str
    info: Info
    paths: Paths
    components: Components
    servers: t.Optional[list[Server]] = None
    security: t.Optional[list[Security]] = None
    tags: t.Optional[list[Tag]] = None
    externalDocs: t.Optional[ExternalDocs] = None


class OpenAPISpec:
    OPENAPI_VERSION = "3.1.0"

    def __init__(
        self,
        info: Info,
        *,
        servers: t.Optional[list[Server]] = None,
        security: t.Optional[list[Security]] = None,
        tags: t.Optional[list[Tag]] = None,
        externalDocs: t.Optional[ExternalDocs] = None,
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

    def add_schema(self, name: str, item: t.Union[Schema, Reference]):
        self.spec.components.schemas[name] = item

    def add_response(self, name: str, item: t.Union[Response, Reference]):
        self.spec.components.responses[name] = item

    def add_parameter(self, name: str, item: t.Union[Parameter, Reference]):
        self.spec.components.parameters[name] = item

    def add_example(self, name: str, item: t.Union[Example, Reference]):
        self.spec.components.examples[name] = item

    def add_request_body(self, name: str, item: t.Union[RequestBody, Reference]):
        self.spec.components.requestBodies[name] = item

    def add_header(self, name: str, item: t.Union[Header, Reference]):
        self.spec.components.headers[name] = item

    def add_security(self, name: str, item: t.Union[Security, Reference]):
        self.spec.components.securitySchemes[name] = item

    def add_link(self, name: str, item: t.Union[Link, Reference]):
        self.spec.components.links[name] = item

    def add_callback(self, name: str, item: t.Union[Callback, Reference]):
        self.spec.components.callbacks[name] = item

    def to_dict(self, obj=None) -> t.Any:
        if obj is None:
            return self.to_dict(dataclasses.asdict(self.spec))

        if isinstance(obj, list):
            return [self.to_dict(i) for i in obj]

        if isinstance(obj, dict):
            return {{"ref": "$ref", "in_": "in"}.get(k, k): self.to_dict(v) for k, v in obj.items() if v is not None}

        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return self.to_dict(dataclasses.asdict(obj))

        return obj
