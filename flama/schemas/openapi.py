import dataclasses
import typing as t

import flama.types

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

Schema = t.NewType("Schema", flama.types.JSONSchema)


@dataclasses.dataclass(frozen=True)
class Reference:
    ref: str


@dataclasses.dataclass(frozen=True)
class Contact:
    name: t.Optional[str] = None
    url: t.Optional[str] = None
    email: t.Optional[str] = None


@dataclasses.dataclass(frozen=True)
class License:
    name: str
    url: t.Optional[str] = None


@dataclasses.dataclass(frozen=True)
class ExternalDocs:
    url: str
    description: t.Optional[str] = None


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


@dataclasses.dataclass(frozen=True)
class Info:
    title: str
    version: str
    description: t.Optional[str] = None
    termsOfService: t.Optional[str] = None
    contact: t.Optional[Contact] = None
    license: t.Optional[License] = None


@dataclasses.dataclass(frozen=True)
class ServerVariable:
    enum: list[str]
    default: str
    description: t.Optional[str] = None


@dataclasses.dataclass(frozen=True)
class Server:
    url: str
    variables: dict[str, ServerVariable]
    description: t.Optional[str] = None


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
        title: str,
        version: str,
        description: t.Optional[str] = None,
        terms_of_service: t.Optional[str] = None,
        contact: t.Optional[Contact] = None,
        license: t.Optional[License] = None,
    ):
        self.spec = OpenAPI(
            openapi=self.OPENAPI_VERSION,
            info=Info(
                title=title,
                version=version,
                description=description,
                termsOfService=terms_of_service,
                contact=contact,
                license=license,
            ),
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
