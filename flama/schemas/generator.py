import enum
import inspect
import itertools
import json
import logging
import os
import typing
from collections import defaultdict
from string import Template

from starlette import routing
from starlette import schemas as starlette_schemas
from starlette.responses import HTMLResponse

from flama.schemas import Field, Schema, openapi, schemas, to_json_schema
from flama.templates import PATH as TEMPLATES_PATH

logger = logging.getLogger(__name__)

__all__ = ["OpenAPIResponse", "SchemaGenerator", "SchemaMixin"]


class FieldLocation(enum.Enum):
    query = enum.auto()
    path = enum.auto()
    body = enum.auto()


class Field(typing.NamedTuple):
    name: str
    location: FieldLocation
    schema: typing.Union[Field, Schema]
    required: bool = False


class EndpointInfo(typing.NamedTuple):
    path: str
    method: str
    func: typing.Callable
    query_fields: typing.Dict[str, Field]
    path_fields: typing.Dict[str, Field]
    body_field: Field
    output_field: typing.Any


class OpenAPIResponse(starlette_schemas.OpenAPIResponse):
    def render(self, content: typing.Any) -> bytes:
        assert isinstance(content, dict), "The schema passed to OpenAPIResponse should be a dictionary."

        return json.dumps(content).encode("utf-8")


class SchemaRegistry(typing.Set[Schema]):
    @staticmethod
    def _schema_class(element: Schema):
        return element if inspect.isclass(element) else element.__class__

    def __contains__(self, item):
        return super().__contains__(self._schema_class(item))

    def add(self, element: Schema) -> None:
        """
        Register a new Schema to this registry.

        :param element: Schema object or class.
        """
        super().add(self._schema_class(element))

    def get_name(self, element: Schema) -> str:
        """
        Generate a name for given schema.

        :param element: Schema object or class.
        :return: Schema name.
        """
        if element not in self:
            raise ValueError("Unregistered schema")

        return self._schema_class(element).__name__

    def get_ref(self, element: Schema) -> typing.Union[openapi.Schema, openapi.Reference]:
        """
        Generate a reference for given schema.

        :param element: Schema object or class.
        :return: Schema reference.
        """
        if element not in self:
            raise ValueError("Unregistered schema")

        reference = openapi.Reference(ref=f"#/components/schemas/{self.get_name(element)}")
        schema = to_json_schema(element)
        if schema.get("type") == "array" and schema.get("items"):
            schema["items"] = reference
            return openapi.Schema(schema)

        return reference


class SchemaGenerator(starlette_schemas.BaseSchemaGenerator):
    def __init__(
        self,
        title: str,
        version: str,
        description: str = None,
        terms_of_service: str = None,
        contact_name: str = None,
        contact_url: str = None,
        contact_email: str = None,
        license_name: str = None,
        license_url: str = None,
    ):
        contact = (
            openapi.Contact(name=contact_name, url=contact_url, email=contact_email)
            if contact_name or contact_url or contact_email
            else None
        )

        license = openapi.License(name=license_name, url=license_url) if license_name else None

        self.spec = openapi.OpenAPISpec(
            title=title,
            version=version,
            description=description,
            terms_of_service=terms_of_service,
            contact=contact,
            license=license,
        )

        # Builtin definitions
        self.schemas = SchemaRegistry()

    def get_endpoints(
        self, routes: typing.List[routing.BaseRoute], base_path: str = ""
    ) -> typing.Dict[str, typing.List[EndpointInfo]]:
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
        endpoints_info: typing.Dict[str, typing.List[EndpointInfo]] = defaultdict(list)

        for route in routes:
            _, path, _ = routing.compile_path(base_path + route.path)

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
                                query_fields=route.query_fields.get(method, {}),
                                path_fields=route.path_fields.get(method, {}),
                                body_field=route.body_field.get(method),
                                output_field=route.output_field.get(method),
                            )
                        )
                else:
                    for method in ["get", "post", "put", "patch", "delete", "options"]:
                        if not hasattr(route.endpoint, method):
                            continue

                        func = getattr(route.endpoint, method)
                        endpoints_info[path].append(
                            EndpointInfo(
                                path=path,
                                method=method.lower(),
                                func=func,
                                query_fields=route.query_fields.get(method.upper(), {}),
                                path_fields=route.path_fields.get(method.upper(), {}),
                                body_field=route.body_field.get(method.upper()),
                                output_field=route.output_field.get(method.upper()),
                            )
                        )
            elif isinstance(route, routing.Mount):
                endpoints_info.update(self.get_endpoints(route.routes, base_path=path))

        return endpoints_info

    def _build_endpoint_parameters(
        self, endpoint: EndpointInfo, metadata: typing.Dict[str, typing.Any]
    ) -> typing.Optional[typing.List[openapi.Parameter]]:
        if not endpoint.query_fields and not endpoint.path_fields:
            return None

        return [
            openapi.Parameter(
                schema=to_json_schema(field.schema),
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
            for field in itertools.chain(endpoint.query_fields.values(), endpoint.path_fields.values())
        ]

    def _build_endpoint_body(
        self, endpoint: EndpointInfo, metadata: typing.Dict[str, typing.Any]
    ) -> typing.Optional[openapi.RequestBody]:
        if not endpoint.body_field:
            return None

        self.schemas.add(endpoint.body_field.schema)
        schema_ref = self.schemas.get_ref(endpoint.body_field.schema)

        return openapi.RequestBody(
            content={"application/json": openapi.MediaType(schema=schema_ref)},
            **{
                x: metadata.get("requestBody", {}).get("content", {}).get("application/json", {}).get(x)
                for x in ("description", "required")
            },
        )

    def _build_endpoint_response(
        self, endpoint: EndpointInfo, metadata: typing.Dict[str, typing.Any]
    ) -> typing.Tuple[typing.Optional[openapi.Response], typing.Optional[str]]:
        try:
            response_code, main_response = list(metadata.get("responses", {}).items())[0]
        except IndexError:
            response_code, main_response = "200", {}
            logger.warning(
                'OpenAPI description not provided in docstring for main response in endpoint "%s"', endpoint.path
            )

        if endpoint.output_field and (
            (inspect.isclass(endpoint.output_field) and issubclass(endpoint.output_field, Schema))
            or isinstance(endpoint.output_field, Schema)
        ):
            self.schemas.add(endpoint.output_field)
            schema_ref = self.schemas.get_ref(endpoint.output_field)
            content = {"application/json": openapi.MediaType(schema=schema_ref)}
        else:
            content = None

        return (
            openapi.Response(
                description=main_response.get("description", "Description not provided."), content=content,
            ),
            str(response_code),
        )

    def _build_endpoint_default_response(self, metadata: typing.Dict[str, typing.Any]) -> openapi.Response:
        self.schemas.add(schemas.APIError)
        schema_ref = self.schemas.get_ref(schemas.APIError)

        return openapi.Response(
            description=metadata.get("responses", {}).get("default", {}).get("description", "Unexpected error."),
            content={"application/json": openapi.MediaType(schema=schema_ref)},
        )

    def get_operation_schema(self, endpoint: EndpointInfo) -> openapi.Operation:
        docstring_info = self.parse_docstring(endpoint.func)

        # Query and Path parameters
        parameters = self._build_endpoint_parameters(endpoint, docstring_info)

        # Body
        request_body = self._build_endpoint_body(endpoint, docstring_info)

        responses = {}

        # Response
        response, response_code = self._build_endpoint_response(endpoint, docstring_info)
        if response:
            responses[response_code] = response

        # Default response
        responses["default"] = self._build_endpoint_default_response(docstring_info)

        return openapi.Operation(
            responses=openapi.Responses(responses),
            parameters=parameters,
            requestBody=request_body,
            **{
                x: docstring_info.get(x)
                for x in ("tags", "summary", "description", "externalDocs", "operationId", "deprecated")
            },
        )

    def get_api_schema(self, routes: typing.List[routing.BaseRoute]) -> typing.Dict[str, typing.Any]:
        endpoints_info = self.get_endpoints(routes)

        for path, endpoints in endpoints_info.items():
            self.spec.add_path(path, openapi.Path(**{e.method: self.get_operation_schema(e) for e in endpoints}))

        for name, schema in [(self.schemas.get_name(x), x) for x in self.schemas]:
            self.spec.add_schema(name, openapi.Schema(to_json_schema(schema)))

        return self.spec.asdict()


class SchemaMixin:
    def add_schema_docs_routes(
        self,
        title: str = "",
        version: str = "",
        description: str = "",
        schema: typing.Optional[str] = "/schema/",
        docs: typing.Optional[str] = "/docs/",
        redoc: typing.Optional[str] = None,
    ):
        # Schema
        self.title = title
        self.version = version
        self.description = description
        self.schema_url = schema
        if self.schema_url:
            self.add_schema_route()

        # Docs (Swagger UI)
        self.docs_url = docs
        if self.docs_url:
            self.add_docs_route()

        # Redoc
        self.redoc_url = redoc
        if self.redoc_url:
            self.add_redoc_route()

    @property
    def schema_generator(self):
        if not hasattr(self, "_schema_generator"):
            self._schema_generator = SchemaGenerator(
                title=self.title, version=self.version, description=self.description
            )

        return self._schema_generator

    @property
    def schema(self):
        return self.schema_generator.get_api_schema(self.routes)

    def add_schema_route(self):
        def schema():
            return OpenAPIResponse(self.schema)

        self.add_route(path=self.schema_url, route=schema, methods=["GET"], include_in_schema=False)

    def add_docs_route(self):
        def swagger_ui() -> HTMLResponse:
            with open(os.path.join(TEMPLATES_PATH, "swagger_ui.html")) as f:
                content = Template(f.read()).substitute(title=self.title, schema_url=self.schema_url)

            return HTMLResponse(content)

        self.add_route(path=self.docs_url, route=swagger_ui, methods=["GET"], include_in_schema=False)

    def add_redoc_route(self):
        def redoc() -> HTMLResponse:
            with open(os.path.join(TEMPLATES_PATH, "redoc.html")) as f:
                content = Template(f.read()).substitute(title=self.title, schema_url=self.schema_url)

            return HTMLResponse(content)

        self.add_route(path=self.redoc_url, route=redoc, methods=["GET"], include_in_schema=False)
