import inspect
import itertools
import os
import typing
from collections import defaultdict
from string import Template

import marshmallow
from starlette import routing, schemas
from starlette.responses import HTMLResponse

from flama.responses import APIError
from flama.types import EndpointInfo
from flama.utils import dict_safe_add

try:
    import apispec
except Exception:  # pragma: no cover
    apispec = None  # type: ignore

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None  # type: ignore

__all__ = ["OpenAPIResponse", "SchemaGenerator", "SchemaMixin"]


if yaml is not None and apispec is not None:
    from apispec.core import YAMLDumper as BaseYAMLDumper

    class YAMLDumper(BaseYAMLDumper):
        def ignore_aliases(self, data):
            return True


class OpenAPIResponse(schemas.OpenAPIResponse):
    def render(self, content: typing.Any) -> bytes:
        assert yaml is not None, "`pyyaml` must be installed to use OpenAPIResponse."
        assert apispec is not None, "`apispec` must be installed to use OpenAPIResponse."
        assert isinstance(content, dict), "The schema passed to OpenAPIResponse should be a dictionary."

        return yaml.dump(content, default_flow_style=False, Dumper=YAMLDumper).encode("utf-8")


class SchemaRegistry(dict):
    def __init__(self, spec: apispec.APISpec, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.spec = spec
        self.openapi = self.spec.plugins[0].openapi

    def __getitem__(self, item):
        try:
            schema = super().__getitem__(item)
        except KeyError:
            component_schema = item if inspect.isclass(item) else item.__class__

            self.spec.definition(name=component_schema.__name__, schema=component_schema)

            schema = self.openapi.resolve_schema_dict(item)
            super().__setitem__(item, schema)

        return schema


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

        # Builtin definitions
        self.schemas = SchemaRegistry(self.spec)

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
                endpoints_info.update(self.get_endpoints(route.routes, base_path=route.path))

        return endpoints_info

    def _add_endpoint_parameters(self, endpoint: EndpointInfo, schema: typing.Dict):
        schema["parameters"] = [
            self.openapi.field2parameter(field.schema, name=field.name, default_in=field.location.name)
            for field in itertools.chain(endpoint.query_fields.values(), endpoint.path_fields.values())
        ]

    def _add_endpoint_body(self, endpoint: EndpointInfo, schema: typing.Dict):
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

    def _add_endpoint_response(self, endpoint: EndpointInfo, schema: typing.Dict):
        response_codes = list(schema.get("responses", {}).keys())
        main_response = response_codes[0] if response_codes else 200

        dict_safe_add(
            schema,
            self.schemas[endpoint.output_field],
            "responses",
            main_response,
            "content",
            "application/json",
            "schema",
        )

    def _add_endpoint_default_response(self, schema: typing.Dict):
        dict_safe_add(schema, self.schemas[APIError], "responses", "default", "content", "application/json", "schema")

        # Default description
        schema["responses"]["default"]["description"] = schema["responses"]["default"].get(
            "description", "Unexpected error."
        )

    def get_endpoint_schema(self, endpoint: EndpointInfo) -> typing.Dict[str, typing.Any]:
        schema = self.parse_docstring(endpoint.func)

        # Query and Path parameters
        if endpoint.query_fields or endpoint.path_fields:
            self._add_endpoint_parameters(endpoint, schema)

        # Body
        if endpoint.body_field:
            self._add_endpoint_body(endpoint, schema)

        # Response
        if endpoint.output_field and (
            (inspect.isclass(endpoint.output_field) and issubclass(endpoint.output_field, marshmallow.Schema))
            or isinstance(endpoint.output_field, marshmallow.Schema)
        ):
            self._add_endpoint_response(endpoint, schema)

        # Default response
        self._add_endpoint_default_response(schema)

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
