import typing


def _fix_key_names(x):
    try:
        return {"ref": "$ref", "in_": "in"}[x]
    except KeyError:
        return x


def _object_asdict(x=None):
    if isinstance(x, list):
        return [_object_asdict(i) for i in x]

    if isinstance(x, dict):
        return {_fix_key_names(k): _object_asdict(v) for k, v in x.items() if v is not None}

    try:
        return {_fix_key_names(k): _object_asdict(v) for k, v in x._asdict().items() if v is not None}
    except AttributeError:
        return x


Schema = typing.NewType("Schema", typing.Dict[str, typing.Any])


class Reference(typing.NamedTuple):
    ref: str


class Contact(typing.NamedTuple):
    name: str = None
    url: str = None
    email: str = None


class License(typing.NamedTuple):
    name: str
    url: str = None


class ExternalDocs(typing.NamedTuple):
    url: str
    description: str = None


class Example(typing.NamedTuple):
    summary: str = None
    description: str = None
    value: typing.Any = None
    externalValue: str = None


class Tag(typing.NamedTuple):
    name: str
    description: str = None
    externalDocs: ExternalDocs = None


class Info(typing.NamedTuple):
    title: str
    version: str
    description: str = None
    termsOfService: str = None
    contact: Contact = None
    license: License = None


class ServerVariable(typing.NamedTuple):
    enum: typing.List[str]
    default: str
    description: str = None


class Server(typing.NamedTuple):
    url: str
    variables: typing.Dict[str, ServerVariable]
    description: str = None


class Link(typing.NamedTuple):
    operationRef: str = None
    operationId: str = None
    parameters: typing.Dict[str, typing.Any] = None
    requestBody: typing.Any = None
    description: str = None
    server: Server = None


Security = typing.NewType("Security", typing.Dict[str, typing.List[str]])
Callback = typing.NewType("Callback", typing.Dict[str, "Path"])


class Header(typing.NamedTuple):
    description: str = None
    required: bool = None
    deprecated: bool = None
    allowEmptyValue: bool = None
    style: str = None
    explode: bool = None
    allowReserved: bool = None
    schema: typing.Union[Schema, Reference] = None
    example: typing.Any = None
    examples: typing.Dict[str, typing.Union[Example, Reference]] = None


class Parameter(typing.NamedTuple):
    name: str
    in_: str
    description: str = None
    required: bool = None
    deprecated: bool = None
    allowEmptyValue: bool = None
    style: str = None
    explode: bool = None
    allowReserved: bool = None
    schema: typing.Union[Schema, Reference] = None
    example: typing.Any = None
    examples: typing.Dict[str, typing.Union[Example, Reference]] = None


class Encoding(typing.NamedTuple):
    contentType: str = None
    headers: typing.Dict[str, typing.Union[Header, Reference]] = None
    style: str = None
    explode: bool = None
    allowReserved: bool = None


class MediaType(typing.NamedTuple):
    schema: typing.Union[Schema, Reference] = None
    example: typing.Any = None
    examples: typing.Dict[str, typing.Union[typing.Any, Reference]] = None
    encoding: typing.Dict[str, Encoding] = None


class RequestBody(typing.NamedTuple):
    content: typing.Dict[str, MediaType]
    description: str = None
    required: bool = None


class Response(typing.NamedTuple):
    description: str
    headers: typing.Dict[str, typing.Union[Header, Reference]] = None
    content: typing.Dict[str, MediaType] = None
    links: typing.Dict[str, typing.Union[Link, Reference]] = None


Responses = typing.NewType("Responses", typing.Dict[str, Response])


class Operation(typing.NamedTuple):
    responses: Responses
    tags: typing.List[str] = None
    summary: str = None
    description: str = None
    externalDocs: ExternalDocs = None
    operationId: str = None
    parameters: typing.List[typing.Union[Parameter, Reference]] = None
    requestBody: typing.Union[RequestBody, Reference] = None
    callbacks: typing.Dict[str, typing.Union[Callback, Reference]] = None
    deprecated: bool = None
    security: typing.List[Security] = None
    servers: typing.List[Server] = None


class Path(typing.NamedTuple):
    ref: str = None
    summary: str = None
    description: str = None
    get: Operation = None
    put: Operation = None
    post: Operation = None
    delete: Operation = None
    options: Operation = None
    head: Operation = None
    patch: Operation = None
    trace: Operation = None
    servers: typing.List[Server] = None
    parameters: typing.List[typing.Union[Parameter, Reference]] = None

    @property
    def operations(self) -> typing.Dict[str, Operation]:
        return {
            x: getattr(self, x)
            for x in ("get", "put", "post", "delete", "options", "head", "patch", "trace")
            if getattr(self, x) is not None
        }


Paths = typing.NewType("Paths", typing.Dict[str, Path])


class Components(typing.NamedTuple):
    schemas: typing.Dict[str, typing.Union[Schema, Reference]]
    responses: typing.Dict[str, typing.Union[Response, Reference]]
    parameters: typing.Dict[str, typing.Union[Parameter, Reference]]
    examples: typing.Dict[str, typing.Union[Example, Reference]]
    requestBodies: typing.Dict[str, typing.Union[RequestBody, Reference]]
    headers: typing.Dict[str, typing.Union[Header, Reference]]
    securitySchemes: typing.Dict[str, typing.Union[Security, Reference]]
    links: typing.Dict[str, typing.Union[Link, Reference]]
    callbacks: typing.Dict[str, typing.Union[Callback, Reference]]


class OpenAPI(typing.NamedTuple):
    openapi: str
    info: Info
    paths: Paths
    components: Components
    servers: typing.List[Server] = None
    security: typing.List[Security] = None
    tags: typing.List[Tag] = None
    externalDocs: ExternalDocs = None


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

    def asdict(self):
        return _object_asdict(self.spec)
