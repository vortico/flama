import dataclasses
import inspect
import itertools
import logging
import typing as t
from collections import defaultdict

import yaml

from flama import routing, schemas, types, url
from flama.schemas import data_structures as ds
from flama.schemas.registry import SchemaInfo, SchemaRegistry

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
    "OpenAPISchemaRegistry",
    "SchemaGenerator",
]

empty = types.Empty()
logger = logging.getLogger(__name__)


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
                {name: ServerVariable.from_spec(variable) for name, variable in spec["variables"].items()}
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
                [Server.from_spec(server) for server in spec["servers"]]
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


class OpenAPISchemaRegistry(SchemaRegistry):
    """Schema registry that resolves references against an OpenAPI ``#/components/schemas`` section."""

    def _get_schema_references_from_schema(self, schema: "Schema | Reference") -> list[str]:
        if isinstance(schema, Reference):
            return [schema.ref]

        result = []

        if "$ref" in schema:
            result.append(schema["$ref"])

        if schema.get("type", "") == "array":
            items = schema.get("items", {})
            if isinstance(items, dict) and "$ref" in items:
                result.append(items["$ref"])

        for composer in ("allOf", "anyOf", "oneOf"):
            composer_schemas = schema.get(composer, [])
            if isinstance(composer_schemas, list):
                result += [
                    ref
                    for x in composer_schemas
                    if x and isinstance(x, dict)
                    for ref in self._get_schema_references_from_schema(Schema(x))
                ]

        props = schema.get("properties", {})
        if isinstance(props, dict):
            result += [
                ref
                for x in props.values()
                if x and isinstance(x, dict)
                for ref in self._get_schema_references_from_schema(Schema(x))
            ]

        return result

    def _get_schema_references_from_path(self, path: "Path") -> list[str]:
        return [y for x in path.operations.values() for y in self._get_schema_references_from_operation(x)]

    def _get_schema_references_from_operation(self, operation: "Operation") -> list[str]:
        return [
            *self._get_schema_references_from_operation_parameters(operation.parameters),
            *self._get_schema_references_from_operation_request_body(operation.requestBody),
            *self._get_schema_references_from_operation_callbacks(operation.callbacks),
            *self._get_schema_references_from_operation_responses(operation.responses),
        ]

    def _get_schema_references_from_operation_responses(self, responses: "Responses") -> list[str]:
        refs = []

        for response in responses.values():
            content = response.content
            if not content:
                continue
            for media_type in content.values():
                if not isinstance(media_type, MediaType):
                    continue
                schema = media_type.schema
                if schema is None:
                    continue
                refs += self._get_schema_references_from_schema(schema)

        return refs

    def _get_schema_references_from_operation_callbacks(
        self, callbacks: "dict[str, Callback | Reference] | None"
    ) -> list[str]:
        refs = []

        if callbacks:
            for callback in callbacks.values():
                if isinstance(callback, Reference):
                    refs.append(callback.ref)
                else:
                    for callback_path in callback.values():
                        refs += self._get_schema_references_from_path(callback_path)

        return refs

    def _get_schema_references_from_operation_request_body(
        self, request_body: "RequestBody | Reference | None"
    ) -> list[str]:
        refs = []

        if request_body:
            if isinstance(request_body, Reference):
                refs.append(request_body.ref)
            else:
                for media_type in request_body.content.values():
                    if not isinstance(media_type, MediaType):
                        continue
                    schema = media_type.schema
                    if schema is None:
                        continue
                    refs += self._get_schema_references_from_schema(schema)

        return refs

    def _get_schema_references_from_operation_parameters(
        self, parameters: "list[Parameter | Reference] | None"
    ) -> list[str]:
        refs = []

        if parameters:
            for param in parameters:
                if isinstance(param, Reference):
                    refs.append(param.ref)
                elif param.schema is not None:
                    refs += self._get_schema_references_from_schema(param.schema)

        return refs

    def used(self, spec: "OpenAPISpec") -> dict[int, SchemaInfo]:
        """Generate a dict containing used schemas.

        :param spec: API Schema.
        :return: Used schemas.
        """
        # Get schemas from references in path
        refs = {
            x.split("/")[-1] for path in spec.spec.paths.values() for x in self._get_schema_references_from_path(path)
        }
        used_schemas = {id_: schema for id_, schema in self.items() if schema.name in refs}

        # Get schemas from references in schema
        partial_schemas = set(used_schemas.values())
        refs = set([])
        while partial_schemas:
            schema = partial_schemas.pop()
            refs_from_schema = {
                ref.split("/")[-1]
                for ref in self._get_schema_references_from_schema(Schema(schema.json_schema(self.names)))
            }
            partial_schemas |= {schema for schema in self.values() if schema.name in refs_from_schema}
            refs |= refs_from_schema
        used_schemas |= {id_: schema for id_, schema in self.items() if schema.name in refs}

        # Get schemas from schema children
        partial_schemas = set(used_schemas.values())
        while partial_schemas:
            for schema in (
                ds.Schema(s).unique_schema for s in ds.Schema(partial_schemas.pop().schema).nested_schemas()
            ):
                partial_schemas.add(self[schema])
                used_schemas[id(schema)] = self[schema]

        return used_schemas

    def get_openapi_ref(self, element: "ds.Schema", multiple: bool | None = None) -> "Schema | Reference":
        """Builds the reference for a single schema or the array schema containing the reference.

        :param element: Schema to use as reference.
        :param multiple: True for building a schema containing an array of references instead of a single reference.
        :return: Reference or array schema.
        """
        reference = f"#/components/schemas/{self[element].name}"

        if multiple is True:
            return Schema({"items": {"$ref": reference}, "type": "array"})
        else:
            return Reference(ref=reference)


@dataclasses.dataclass(frozen=True)
class EndpointInfo:
    path: str
    method: str
    func: t.Callable = dataclasses.field(repr=False)
    query_parameters: dict[str, ds.Parameter] = dataclasses.field(repr=False)
    path_parameters: dict[str, ds.Parameter] = dataclasses.field(repr=False)
    body_parameter: ds.Parameter | None = dataclasses.field(repr=False)
    response_parameter: ds.Parameter = dataclasses.field(repr=False)


class SchemaGenerator:
    def __init__(self, spec: types.OpenAPISpec, schemas: dict[str, ds.Schema] | None = None):
        self.spec = OpenAPISpec.from_spec(spec)

        # Builtin definitions
        self.schemas = OpenAPISchemaRegistry(schemas=schemas)

    def get_endpoints(  # type: ignore[override]
        self, routes: list[routing.BaseRoute], base_path: str = ""
    ) -> dict[str, list[EndpointInfo]]:
        """
        Given the routes, yields the following information:

        - path
            eg: /users/
        - http_method
            one of 'get', 'post', 'put', 'patch', 'delete', 'options'
        - func
            method ready to extract the docstring

        :param routes: A list of routes.
        :param base_path: The base endpoints path.
        :return: Data structure that contains metadata from every route.
        """
        endpoints_info: dict[str, list[EndpointInfo]] = defaultdict(list)

        for route in routes:
            path = str(url.Path(base_path) / route.path)

            if isinstance(route, routing.Route) and route.include_in_schema:
                if inspect.isfunction(route.endpoint) or inspect.ismethod(route.endpoint):
                    for method in route.methods or ["GET"]:
                        if method == "HEAD":
                            continue

                        endpoints_info[path].append(
                            EndpointInfo(
                                path=path,
                                method=method.lower(),
                                func=route.endpoint,
                                query_parameters=route.parameters.query.get(method, {}),
                                path_parameters=route.parameters.path.get(method, {}),
                                body_parameter=route.parameters.body.get(method),
                                response_parameter=route.parameters.response[method],
                            )
                        )
                else:
                    for method in [x.lower() for x in route.methods]:
                        if not hasattr(route.endpoint, method):
                            continue

                        func = getattr(route.endpoint, method)
                        endpoints_info[path].append(
                            EndpointInfo(
                                path=path,
                                method=method.lower(),
                                func=func,
                                query_parameters=route.parameters.query.get(method.upper(), {}),
                                path_parameters=route.parameters.path.get(method.upper(), {}),
                                body_parameter=route.parameters.body.get(method.upper()),
                                response_parameter=route.parameters.response[method.upper()],
                            )
                        )
            elif isinstance(route, routing.Mount):
                endpoints_info.update(self.get_endpoints(route.routes, base_path=path))

        return endpoints_info

    def _build_endpoint_parameters(
        self, endpoint: EndpointInfo, metadata: dict[str, t.Any]
    ) -> list[Parameter | Reference] | None:
        if not endpoint.query_parameters and not endpoint.path_parameters:
            return None

        return [
            Parameter(
                schema=Schema(field.field.json_schema),
                name=field.name,
                in_=field.location.name,
                required=field.required,
                **{
                    x: y.get(x)
                    for y in [x for x in metadata.get("parameters", []) if x.get("name") == field.name]
                    if y
                    for x in (
                        "description",
                        "deprecated",
                        "allowEmptyValue",
                        "style",
                        "explode",
                        "allowReserved",
                        "example",
                    )
                },
            )
            for field in itertools.chain(endpoint.query_parameters.values(), endpoint.path_parameters.values())
        ]

    def _build_endpoint_body(self, endpoint: EndpointInfo, metadata: dict[str, t.Any]) -> RequestBody | None:
        content = {k: v for k, v in metadata.get("requestBody", {}).get("content", {}).items()}

        if endpoint.body_parameter:
            if endpoint.body_parameter.schema.schema not in self.schemas:
                self.schemas.register(schema=endpoint.body_parameter.schema.schema)

            content["application/json"] = MediaType(
                schema=self.schemas.get_openapi_ref(
                    endpoint.body_parameter.schema.schema, multiple=endpoint.body_parameter.multiple
                ),
            )

        if not content:
            return None

        return RequestBody(
            content=content,
            **{x: metadata.get("requestBody", {}).get(x) for x in ("description", "required")},
        )

    def _build_endpoint_responses(self, endpoint: EndpointInfo, metadata: dict[str, t.Any]) -> Responses:
        responses = metadata.get("responses", {})
        try:
            main_response_code = next(iter(responses.keys()))
            assert 100 <= int(main_response_code) < 600
        except (ValueError, AssertionError, StopIteration):
            main_response_code = 200
            responses[main_response_code] = {
                "description": "Description not provided.",
            }
            logger.warning(
                'OpenAPI description not provided in docstring for main response in endpoint "%s", adding a standard '
                '"%s" response',
                main_response_code,
                endpoint.path,
            )

        if endpoint.response_parameter.schema.schema:
            if endpoint.response_parameter.schema.schema not in self.schemas:
                self.schemas.register(schema=endpoint.response_parameter.schema.schema)

            responses[main_response_code]["content"] = {
                **responses[main_response_code].get("content", {}),
                "application/json": {
                    "schema": self.schemas.get_openapi_ref(
                        endpoint.response_parameter.schema.schema, multiple=endpoint.response_parameter.multiple
                    )
                },
            }

        responses["default"] = {
            "description": "Unexpected error.",
            **responses.get("default", {}),
            "content": {
                "application/json": {
                    "schema": self.schemas.get_openapi_ref(schemas.schemas.core.APIError, multiple=False)
                }
            },
        }

        return Responses(
            {
                str(code): Response(
                    description=response["description"],
                    headers=response.get("headers"),
                    content={
                        mime: MediaType(
                            schema=media_type.get("schema"),
                            example=media_type.get("example"),
                            examples=media_type.get("examples"),
                            encoding=media_type.get("encoding"),
                        )
                        for mime, media_type in response.get("content", {}).items()
                    },
                    links=response.get("links"),
                )
                for code, response in responses.items()
            }
        )

    def _parse_docstring(self, func: t.Callable) -> dict[t.Any, t.Any]:
        """Given a function, parse the docstring as YAML and return a dictionary of info.

        :param func: Function to analyze docstring.
        :return: Schema extracted.
        """
        try:
            # It's possible to define a standard docstring along with the schema definition, for doing so the schema
            # should start with a line with three dashes "---" as it's the usual notation for starting a yaml file.
            schema = yaml.safe_load((func.__doc__ or "").split("---")[-1])
        except AttributeError:
            schema = None

        if not isinstance(schema, dict):
            raise ValueError

        return schema

    def get_operation_schema(self, endpoint: EndpointInfo) -> Operation:
        try:
            docstring_info = self._parse_docstring(endpoint.func)
        except ValueError:
            docstring_info = {}

        # Query and Path parameters
        parameters = self._build_endpoint_parameters(endpoint, docstring_info)

        # Body
        request_body = self._build_endpoint_body(endpoint, docstring_info)

        # Response
        responses = self._build_endpoint_responses(endpoint, docstring_info)

        return Operation(
            responses=responses,
            parameters=parameters,
            requestBody=request_body,
            **{
                x: docstring_info.get(x)
                for x in ("tags", "summary", "description", "externalDocs", "operationId", "deprecated")
            },
        )

    def get_api_schema(self, routes: list[routing.BaseRoute]) -> dict[str, t.Any]:
        endpoints_info = self.get_endpoints(routes)

        for path, endpoints in endpoints_info.items():
            operations = {}
            for endpoint in endpoints:
                try:
                    operations[endpoint.method] = self.get_operation_schema(endpoint)
                except Exception:
                    logger.error("Cannot generate schema for endpoint %s", endpoint)

            if operations:
                self.spec.add_path(path, Path(**operations))  # type: ignore[arg-type]

        for schema in self.schemas.used(self.spec).values():
            self.spec.add_schema(schema.name, Schema(schema.json_schema(self.schemas.names)))

        api_schema: dict[str, t.Any] = self.spec.to_dict()

        return api_schema
