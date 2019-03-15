import inspect
import itertools
import os
import typing
from collections import defaultdict
from string import Template

import marshmallow
from starlette import routing, schemas
from starlette.responses import HTMLResponse

from starlette_api.types import EndpointInfo
from starlette_api.utils import dict_safe_add

try:
    import apispec
except Exception:  # pragma: no cover
    apispec = None  # type: ignore

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None  # type: ignore

__all__ = ["OpenAPIResponse", "SchemaGenerator", "SchemaMixin"]


class OpenAPIResponse(schemas.OpenAPIResponse):
    def render(self, content: typing.Any) -> bytes:
        assert yaml is not None, "`pyyaml` must be installed to use OpenAPIResponse."
        assert apispec is not None, "`apispec` must be installed to use OpenAPIResponse."
        assert isinstance(content, dict), "The schema passed to OpenAPIResponse should be a dictionary."

        from apispec.core import YAMLDumper

        return yaml.dump(content, default_flow_style=False, Dumper=YAMLDumper).encode("utf-8")


class SchemaGenerator(schemas.BaseSchemaGenerator):
    def __init__(self, title: str, version: str, description: str, openapi_version="3.0.0"):
        assert apispec is not None, "`apispec` must be installed to use SchemaGenerator."

        from apispec.ext.marshmallow import MarshmallowPlugin

        self.spec = apispec.APISpec(
            title=title,
            version=version,
            openapi_version=openapi_version,
            info={"description": description},
            plugins=[MarshmallowPlugin()],
        )
        self.openapi = self.spec.plugins[0].openapi

    def get_endpoints(
        self, routes: typing.List[routing.BaseRoute], base_path: str = ""
    ) -> typing.Dict[str, typing.Sequence[EndpointInfo]]:
        """
        Given the routes, yields the following information:

        - path
            eg: /users/
        - http_method
            one of 'get', 'post', 'put', 'patch', 'delete', 'options'
        - func
            method ready to extract the docstring
        """
        endpoints_info: typing.Dict[str, typing.Sequence[EndpointInfo]] = defaultdict(list)

        for route in routes:
            if isinstance(route, routing.Route) and route.include_in_schema:
                _, path, _ = routing.compile_path(base_path + route.path)

                if inspect.isfunction(route.endpoint) or inspect.ismethod(route.endpoint):
                    for method in route.methods or ["GET"]:
                        if method == "HEAD":
                            continue

                        endpoints_info[path].append(
                            EndpointInfo(
                                path=path,
                                method=method.lower(),
                                func=route.endpoint,
                                query_fields=route.query_fields.get(method),
                                path_fields=route.path_fields.get(method),
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
                                query_fields=route.query_fields.get(method.upper()),
                                path_fields=route.path_fields.get(method.upper()),
                                body_field=route.body_field.get(method.upper()),
                                output_field=route.output_field.get(method.upper()),
                            )
                        )
            elif isinstance(route, routing.Mount):
                endpoints_info.update(self.get_endpoints(route.routes, base_path=route.path))

        return endpoints_info

    def get_endpoint_parameters_schema(self, endpoint: EndpointInfo, schema: typing.Dict) -> typing.List[typing.Dict]:
        schema["parameters"] = [
            self.openapi.field2parameter(field.schema, name=field.name, default_in=field.location.name)
            for field in itertools.chain(endpoint.query_fields.values(), endpoint.path_fields.values())
        ]

    def get_endpoint_body_schema(self, endpoint: EndpointInfo, schema: typing.Dict):
        component_schema = (
            endpoint.body_field.schema
            if inspect.isclass(endpoint.body_field.schema)
            else endpoint.body_field.schema.__class__
        )

        self.spec.definition(name=component_schema.__name__, schema=component_schema)

        dict_safe_add(
            schema,
            self.openapi.schema2jsonschema(endpoint.body_field.schema),
            "requestBody",
            "content",
            "application/json",
            "schema",
        )

    def get_endpoint_response_schema(self, endpoint: EndpointInfo, schema: typing.Dict):
        component_schema = (
            endpoint.output_field if inspect.isclass(endpoint.output_field) else endpoint.output_field.__class__
        )

        self.spec.definition(name=component_schema.__name__, schema=component_schema)

        dict_safe_add(
            schema,
            self.openapi.resolve_schema_dict(endpoint.output_field),
            "responses",
            200,
            "content",
            "application/json",
            "schema",
        )

    def get_endpoint_schema(self, endpoint: EndpointInfo) -> typing.Dict[str, typing.Any]:
        schema = self.parse_docstring(endpoint.func)

        # Query and Path parameters
        self.get_endpoint_parameters_schema(endpoint, schema)

        # Body
        if endpoint.body_field:
            self.get_endpoint_body_schema(endpoint, schema)

        # Response
        if endpoint.output_field and (
            (inspect.isclass(endpoint.output_field) and issubclass(endpoint.output_field, marshmallow.Schema))
            or isinstance(endpoint.output_field, marshmallow.Schema)
        ):
            self.get_endpoint_response_schema(endpoint, schema)

        return schema

    def get_schema(self, routes: typing.List[routing.BaseRoute]) -> typing.Dict[str, typing.Any]:
        endpoints_info = self.get_endpoints(routes)

        for path, endpoints in endpoints_info.items():
            self.spec.add_path(path=path, operations={e.method: self.get_endpoint_schema(e) for e in endpoints})

        return self.spec.to_dict()


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
        return self.schema_generator.get_schema(self.routes)

    def add_schema_route(self):
        def schema():
            return OpenAPIResponse(self.schema)

        self.add_route(path=self.schema_url, route=schema, methods=["GET"], include_in_schema=False)

    def add_docs_route(self):
        def swagger_ui() -> HTMLResponse:
            with open(os.path.join(os.path.dirname(__file__), "templates/swagger_ui.html")) as f:
                content = Template(f.read()).substitute(title=self.title, schema_url=self.schema_url)

            return HTMLResponse(content)

        self.add_route(path=self.docs_url, route=swagger_ui, methods=["GET"], include_in_schema=False)

    def add_redoc_route(self):
        def redoc() -> HTMLResponse:
            with open(os.path.join(os.path.dirname(__file__), "templates/redoc.html")) as f:
                content = Template(f.read()).substitute(title=self.title, schema_url=self.schema_url)

            return HTMLResponse(content)

        self.add_route(path=self.redoc_url, route=redoc, methods=["GET"], include_in_schema=False)
