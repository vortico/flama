import dataclasses
import inspect
import itertools
import logging
import typing as t
from collections import defaultdict

import yaml

from flama import routing, schemas, types
from flama.schemas import Schema, openapi
from flama.schemas.data_structures import Parameter
from flama.url import RegexPath

logger = logging.getLogger(__name__)

__all__ = ["SchemaRegistry", "SchemaGenerator"]


@dataclasses.dataclass(frozen=True)
class EndpointInfo:
    path: str
    method: str
    func: t.Callable = dataclasses.field(repr=False)
    query_parameters: dict[str, Parameter] = dataclasses.field(repr=False)
    path_parameters: dict[str, Parameter] = dataclasses.field(repr=False)
    body_parameter: t.Optional[Parameter] = dataclasses.field(repr=False)
    response_parameter: Parameter = dataclasses.field(repr=False)


@dataclasses.dataclass(frozen=True)
class SchemaInfo:
    name: str
    schema: t.Any

    @property
    def ref(self) -> str:
        return f"#/components/schemas/{self.name}"

    def json_schema(self, names: dict[int, str]) -> types.JSONSchema:
        return Schema(self.schema).json_schema(names)


class SchemaRegistry(dict[int, SchemaInfo]):
    def __init__(self, schemas: t.Optional[dict[str, schemas.Schema]] = None):
        super().__init__()

        for name, schema in (schemas or {}).items():
            self.register(schema, name)

    def __contains__(self, item: t.Any) -> bool:
        return super().__contains__(id(schemas.Schema(item).unique_schema))

    def __getitem__(self, item: t.Any) -> SchemaInfo:
        """Lookup method that allows using Schema classes or instances.

        :param item: Schema to look for.
        :return: Registered schema.
        """
        return super().__getitem__(id(schemas.Schema(item).unique_schema))

    @property
    def names(self) -> dict[int, str]:
        """Returns a dictionary mapping schema ids to their names.

        :return: Schema names.
        """
        return {k: v.name for k, v in self.items()}

    @t.no_type_check
    def _get_schema_references_from_schema(self, schema: t.Union[openapi.Schema, openapi.Reference]) -> list[str]:
        if isinstance(schema, openapi.Reference):
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
                    for ref in self._get_schema_references_from_schema(openapi.Schema(x))
                ]

        props = schema.get("properties", {})
        if isinstance(props, dict):
            result += [
                ref
                for x in props.values()
                if x and isinstance(x, dict)
                for ref in self._get_schema_references_from_schema(openapi.Schema(x))
            ]

        return result

    def _get_schema_references_from_path(self, path: openapi.Path) -> list[str]:
        return [y for x in path.operations.values() for y in self._get_schema_references_from_operation(x)]

    def _get_schema_references_from_operation(self, operation: openapi.Operation) -> list[str]:
        return [
            *self._get_schema_references_from_operation_parameters(operation.parameters),
            *self._get_schema_references_from_operation_request_body(operation.requestBody),
            *self._get_schema_references_from_operation_callbacks(operation.callbacks),
            *self._get_schema_references_from_operation_responses(operation.responses),
        ]

    def _get_schema_references_from_operation_responses(self, responses: openapi.Responses) -> list[str]:
        refs = []

        for response in [x for x in responses.values() if x.content]:
            for media_type in [
                x
                for x in response.content.values()  # type: ignore[union-attr]
                if isinstance(x, openapi.MediaType) and x.schema
            ]:
                refs += self._get_schema_references_from_schema(media_type.schema)  # type: ignore[arg-type]

        return refs

    def _get_schema_references_from_operation_callbacks(
        self, callbacks: t.Optional[dict[str, t.Union[openapi.Callback, openapi.Reference]]]
    ) -> list[str]:
        refs = []

        if callbacks:
            for callback in callbacks.values():
                if isinstance(callback, openapi.Reference):
                    refs.append(callback.ref)
                else:
                    for callback_path in callback.values():
                        refs += self._get_schema_references_from_path(callback_path)

        return refs

    def _get_schema_references_from_operation_request_body(
        self, request_body: t.Optional[t.Union[openapi.RequestBody, openapi.Reference]]
    ) -> list[str]:
        refs = []

        if request_body:
            if isinstance(request_body, openapi.Reference):
                refs.append(request_body.ref)
            else:
                for media_type in [x for x in request_body.content.values() if isinstance(x, openapi.MediaType)]:
                    refs += self._get_schema_references_from_schema(media_type.schema)  # type: ignore[arg-type]

        return refs

    def _get_schema_references_from_operation_parameters(
        self, parameters: t.Optional[list[t.Union[openapi.Parameter, openapi.Reference]]]
    ) -> list[str]:
        refs = []

        if parameters:
            for param in parameters:
                if isinstance(param, openapi.Reference):
                    refs.append(param.ref)
                else:
                    refs += self._get_schema_references_from_schema(param.schema)  # type: ignore[arg-type]

        return refs

    def used(self, spec: openapi.OpenAPISpec) -> dict[int, SchemaInfo]:
        """
        Generate a dict containing used schemas.

        :param spec: API Schema.
        :return: Used schemas.
        """
        refs_from_spec = {
            x.split("/")[-1] for path in spec.spec.paths.values() for x in self._get_schema_references_from_path(path)
        }
        used_schemas = {k: v for k, v in self.items() if v.name in refs_from_spec}
        refs_from_schemas = {
            x.split("/")[-1]
            for schema in used_schemas.values()
            for x in self._get_schema_references_from_schema(openapi.Schema(schema.json_schema(self.names)))
        }
        used_schemas.update({k: v for k, v in self.items() if v.name in refs_from_schemas})

        for child_schema in [y for x in used_schemas.values() for y in schemas.Schema(x.schema).nested_schemas()]:
            schema = schemas.Schema(child_schema)
            instance = schema.unique_schema

            if instance not in used_schemas:
                used_schemas[id(instance)] = self[instance]

        return used_schemas

    def register(self, schema: schemas.Schema, name: t.Optional[str] = None) -> int:
        """
        Register a new Schema to this registry.

        :param schema: Schema object or class.
        :param name: Schema name.
        :return: Schema ID.
        """
        if schema in self:
            raise ValueError("Schema is already registered.")

        s = schemas.Schema(schema)

        try:
            schema_name = name or s.name
        except ValueError as e:  # pragma: no cover
            raise ValueError("Cannot infer schema name.") from e

        schema_instance = s.unique_schema
        schema_id = id(schema_instance)
        self[schema_id] = SchemaInfo(name=schema_name, schema=schema_instance)

        for child_schema in [schemas.Schema(x) for x in s.nested_schemas() if x not in self]:
            self.register(schema=child_schema.schema, name=child_schema.name)

        return schema_id

    def get_openapi_ref(
        self, element: schemas.Schema, multiple: t.Optional[bool] = None
    ) -> t.Union[openapi.Schema, openapi.Reference]:
        """
        Builds the reference for a single schema or the array schema containing the reference.

        :param element: Schema to use as reference.
        :param multiple: True for building a schema containing an array of references instead of a single reference.
        :return: Reference or array schema.
        """
        reference = self[element].ref

        if multiple is True:
            return openapi.Schema({"items": {"$ref": reference}, "type": "array"})
        else:
            return openapi.Reference(ref=reference)


class SchemaGenerator:
    def __init__(
        self,
        title: str,
        version: str,
        description: t.Optional[str] = None,
        terms_of_service: t.Optional[str] = None,
        contact_name: t.Optional[str] = None,
        contact_url: t.Optional[str] = None,
        contact_email: t.Optional[str] = None,
        license_name: t.Optional[str] = None,
        license_url: t.Optional[str] = None,
        schemas: t.Optional[dict] = None,
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
        self.schemas = SchemaRegistry(schemas=schemas)

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
            path = RegexPath(base_path + route.path.path).template

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
    ) -> t.Optional[list[openapi.Parameter]]:
        if not endpoint.query_parameters and not endpoint.path_parameters:
            return None

        return [
            openapi.Parameter(
                schema=openapi.Schema(field.field.json_schema),
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

    def _build_endpoint_body(
        self, endpoint: EndpointInfo, metadata: dict[str, t.Any]
    ) -> t.Optional[openapi.RequestBody]:
        content = {k: v for k, v in metadata.get("requestBody", {}).get("content", {}).items()}

        if endpoint.body_parameter:
            if endpoint.body_parameter.schema.schema not in self.schemas:
                self.schemas.register(schema=endpoint.body_parameter.schema.schema)

            content["application/json"] = openapi.MediaType(
                schema=self.schemas.get_openapi_ref(
                    endpoint.body_parameter.schema.schema, multiple=endpoint.body_parameter.multiple
                ),
            )

        if not content:
            return None

        return openapi.RequestBody(
            content=content,
            **{x: metadata.get("requestBody", {}).get(x) for x in ("description", "required")},
        )

    def _build_endpoint_responses(self, endpoint: EndpointInfo, metadata: dict[str, t.Any]) -> openapi.Responses:
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
                "application/json": {"schema": self.schemas.get_openapi_ref(schemas.schemas.APIError, multiple=False)}
            },
        }

        return openapi.Responses(
            {
                str(code): openapi.Response(
                    description=response["description"],
                    headers=response.get("headers"),
                    content={
                        mime: openapi.MediaType(
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
            schema = yaml.safe_load(func.__doc__.split("---")[-1])  # type: ignore[union-attr]
        except AttributeError:
            schema = None

        if not isinstance(schema, dict):
            raise ValueError

        return schema

    def get_operation_schema(self, endpoint: EndpointInfo) -> openapi.Operation:
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

        return openapi.Operation(
            responses=responses,
            parameters=parameters,  # type: ignore[arg-type]
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
                self.spec.add_path(path, openapi.Path(**operations))  # type: ignore[arg-type]

        for schema in self.schemas.used(self.spec).values():
            self.spec.add_schema(schema.name, openapi.Schema(schema.json_schema(self.schemas.names)))

        api_schema: dict[str, t.Any] = self.spec.asdict()

        return api_schema
