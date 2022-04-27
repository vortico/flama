import dataclasses
import typing

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

Schema = typing.NewType("Schema", typing.Dict[str, typing.Any])


@dataclasses.dataclass(frozen=True)
class Reference:
    ref: str


@dataclasses.dataclass(frozen=True)
class Contact:
    name: typing.Optional[str] = None
    url: typing.Optional[str] = None
    email: typing.Optional[str] = None


@dataclasses.dataclass(frozen=True)
class License:
    name: str
    url: typing.Optional[str] = None


@dataclasses.dataclass(frozen=True)
class ExternalDocs:
    url: str
    description: typing.Optional[str] = None


@dataclasses.dataclass(frozen=True)
class Example:
    summary: typing.Optional[str] = None
    description: typing.Optional[str] = None
    value: typing.Optional[typing.Any] = None
    externalValue: typing.Optional[str] = None


@dataclasses.dataclass(frozen=True)
class Tag:
    name: str
    description: typing.Optional[str] = None
    externalDocs: typing.Optional[ExternalDocs] = None


@dataclasses.dataclass(frozen=True)
class Info:
    title: str
    version: str
    description: typing.Optional[str] = None
    termsOfService: typing.Optional[str] = None
    contact: typing.Optional[Contact] = None
    license: typing.Optional[License] = None


@dataclasses.dataclass(frozen=True)
class ServerVariable:
    enum: typing.List[str]
    default: str
    description: typing.Optional[str] = None


@dataclasses.dataclass(frozen=True)
class Server:
    url: str
    variables: typing.Dict[str, ServerVariable]
    description: typing.Optional[str] = None


@dataclasses.dataclass(frozen=True)
class Link:
    operationRef: typing.Optional[str] = None
    operationId: typing.Optional[str] = None
    parameters: typing.Optional[typing.Dict[str, typing.Any]] = None
    requestBody: typing.Optional[typing.Any] = None
    description: typing.Optional[str] = None
    server: typing.Optional[Server] = None


Security = typing.NewType("Security", typing.Dict[str, typing.List[str]])
Callback = typing.NewType("Callback", typing.Dict[str, "Path"])


@dataclasses.dataclass(frozen=True)
class Header:
    description: typing.Optional[str] = None
    required: typing.Optional[bool] = None
    deprecated: typing.Optional[bool] = None
    allowEmptyValue: typing.Optional[bool] = None
    style: typing.Optional[str] = None
    explode: typing.Optional[bool] = None
    allowReserved: typing.Optional[bool] = None
    schema: typing.Optional[typing.Union[Schema, Reference]] = None
    example: typing.Optional[typing.Any] = None
    examples: typing.Optional[typing.Dict[str, typing.Union[Example, Reference]]] = None


@dataclasses.dataclass(frozen=True)
class Parameter:
    name: str
    in_: str
    description: typing.Optional[str] = None
    required: typing.Optional[bool] = None
    deprecated: typing.Optional[bool] = None
    allowEmptyValue: typing.Optional[bool] = None
    style: typing.Optional[str] = None
    explode: typing.Optional[bool] = None
    allowReserved: typing.Optional[bool] = None
    schema: typing.Optional[typing.Union[Schema, Reference]] = None
    example: typing.Optional[typing.Any] = None
    examples: typing.Optional[typing.Dict[str, typing.Union[Example, Reference]]] = None


@dataclasses.dataclass(frozen=True)
class Encoding:
    contentType: typing.Optional[str] = None
    headers: typing.Optional[typing.Dict[str, typing.Union[Header, Reference]]] = None
    style: typing.Optional[str] = None
    explode: typing.Optional[bool] = None
    allowReserved: typing.Optional[bool] = None


@dataclasses.dataclass(frozen=True)
class MediaType:
    schema: typing.Optional[typing.Union[Schema, Reference]] = None
    example: typing.Optional[typing.Any] = None
    examples: typing.Optional[typing.Dict[str, typing.Union[typing.Any, Reference]]] = None
    encoding: typing.Optional[typing.Dict[str, Encoding]] = None


@dataclasses.dataclass(frozen=True)
class RequestBody:
    content: typing.Dict[str, MediaType]
    description: typing.Optional[str] = None
    required: typing.Optional[bool] = None


@dataclasses.dataclass(frozen=True)
class Response:
    description: str
    headers: typing.Optional[typing.Dict[str, typing.Union[Header, Reference]]] = None
    content: typing.Optional[typing.Dict[str, MediaType]] = None
    links: typing.Optional[typing.Dict[str, typing.Union[Link, Reference]]] = None


Responses = typing.NewType("Responses", typing.Dict[str, Response])


@dataclasses.dataclass(frozen=True)
class Operation:
    responses: Responses
    tags: typing.Optional[typing.List[str]] = None
    summary: typing.Optional[str] = None
    description: typing.Optional[str] = None
    externalDocs: typing.Optional[ExternalDocs] = None
    operationId: typing.Optional[str] = None
    parameters: typing.Optional[typing.List[typing.Union[Parameter, Reference]]] = None
    requestBody: typing.Optional[typing.Union[RequestBody, Reference]] = None
    callbacks: typing.Optional[typing.Dict[str, typing.Union[Callback, Reference]]] = None
    deprecated: typing.Optional[bool] = None
    security: typing.Optional[typing.List[Security]] = None
    servers: typing.Optional[typing.List[Server]] = None


@dataclasses.dataclass(frozen=True)
class Path:
    ref: typing.Optional[str] = None
    summary: typing.Optional[str] = None
    description: typing.Optional[str] = None
    get: typing.Optional[Operation] = None
    put: typing.Optional[Operation] = None
    post: typing.Optional[Operation] = None
    delete: typing.Optional[Operation] = None
    options: typing.Optional[Operation] = None
    head: typing.Optional[Operation] = None
    patch: typing.Optional[Operation] = None
    trace: typing.Optional[Operation] = None
    servers: typing.Optional[typing.List[Server]] = None
    parameters: typing.Optional[typing.List[typing.Union[Parameter, Reference]]] = None

    @property
    def operations(self) -> typing.Dict[str, Operation]:
        return {
            x: getattr(self, x)
            for x in ("get", "put", "post", "delete", "options", "head", "patch", "trace")
            if getattr(self, x) is not None
        }


Paths = typing.NewType("Paths", typing.Dict[str, Path])


@dataclasses.dataclass(frozen=True)
class Components:
    schemas: typing.Dict[str, typing.Union[Schema, Reference]]
    responses: typing.Dict[str, typing.Union[Response, Reference]]
    parameters: typing.Dict[str, typing.Union[Parameter, Reference]]
    examples: typing.Dict[str, typing.Union[Example, Reference]]
    requestBodies: typing.Dict[str, typing.Union[RequestBody, Reference]]
    headers: typing.Dict[str, typing.Union[Header, Reference]]
    securitySchemes: typing.Dict[str, typing.Union[Security, Reference]]
    links: typing.Dict[str, typing.Union[Link, Reference]]
    callbacks: typing.Dict[str, typing.Union[Callback, Reference]]


@dataclasses.dataclass(frozen=True)
class OpenAPI:
    openapi: str
    info: Info
    paths: Paths
    components: Components
    servers: typing.Optional[typing.List[Server]] = None
    security: typing.Optional[typing.List[Security]] = None
    tags: typing.Optional[typing.List[Tag]] = None
    externalDocs: typing.Optional[ExternalDocs] = None


class OpenAPISpec:
    OPENAPI_VERSION = "3.0.3"

    def __init__(
        self,
        title: str,
        version: str,
        description: str = None,
        terms_of_service: str = None,
        contact: Contact = None,
        license: License = None,
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

    def add_schema(self, name: str, item: typing.Union[Schema, Reference]):
        self.spec.components.schemas[name] = item

    def add_response(self, name: str, item: typing.Union[Response, Reference]):
        self.spec.components.responses[name] = item

    def add_parameter(self, name: str, item: typing.Union[Parameter, Reference]):
        self.spec.components.parameters[name] = item

    def add_example(self, name: str, item: typing.Union[Example, Reference]):
        self.spec.components.examples[name] = item

    def add_request_body(self, name: str, item: typing.Union[RequestBody, Reference]):
        self.spec.components.requestBodies[name] = item

    def add_header(self, name: str, item: typing.Union[Header, Reference]):
        self.spec.components.headers[name] = item

    def add_security(self, name: str, item: typing.Union[Security, Reference]):
        self.spec.components.securitySchemes[name] = item

    def add_link(self, name: str, item: typing.Union[Link, Reference]):
        self.spec.components.links[name] = item

    def add_callback(self, name: str, item: typing.Union[Callback, Reference]):
        self.spec.components.callbacks[name] = item

    def asdict(self, obj: typing.Any = None) -> typing.Any:
        if obj is None:
            return self.asdict(dataclasses.asdict(self.spec))

        if isinstance(obj, list):
            return [self.asdict(i) for i in obj]

        if isinstance(obj, dict):
            return {{"ref": "$ref", "in_": "in"}.get(k, k): self.asdict(v) for k, v in obj.items() if v is not None}

        if dataclasses.is_dataclass(obj):
            return self.asdict(dataclasses.asdict(obj))

        return obj
