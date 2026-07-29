import dataclasses
import enum
import json
import re
import threading
import typing as t
from collections import namedtuple
from unittest.mock import patch

import marshmallow
import pydantic
import pytest
import typesystem
import typesystem.fields

from flama import Flama, types
from flama.endpoints import HTTPEndpoint
from flama.http.responses.html import HTMLResponse
from flama.http.responses.json import JSONResponse
from flama.http.responses.ndjson import NDJSONResponse
from flama.http.responses.sse import ServerSentEventResponse
from flama.schemas import data_structures as ds
from flama.schemas import openapi
from flama.schemas.openapi import (
    Callback,
    Contact,
    Encoding,
    Example,
    ExternalDocs,
    Header,
    Info,
    License,
    Link,
    MediaType,
    OpenAPISchemaRegistry,
    OpenAPISpec,
    Operation,
    Parameter,
    Path,
    RequestBody,
    Response,
    Responses,
    Schema,
    Security,
    Server,
    ServerVariable,
    Tag,
)
from tests._utils import assert_recursive_contains


class _RecursiveNode(pydantic.BaseModel):
    """A self-referencing model used to assert OpenAPI generation does not loop on recursive schemas."""

    id: int
    children: list["_RecursiveNode"] = []


class _Status(enum.Enum):
    """An enum whose member names differ from their values, so resolving by either is distinguishable."""

    AVAILABLE = "available"
    ADOPTED = "adopted"


class _EnumNode(pydantic.BaseModel):
    """A model carrying an enum, which pydantic emits as a definition of its own rather than in place."""

    status: _Status


class TestCaseOpenAPISpec:
    @pytest.fixture(scope="function")
    def spec(self):
        return OpenAPISpec(
            info=Info(
                title="Title",
                version="1.0.0",
                description="Description",
                termsOfService="TOS",
                contact=Contact(name="Contact name", url="https://contact.com", email="contact@contact.com"),
                license=License(name="License name", url="https://license.com"),
            )
        )

    @pytest.fixture(scope="function")
    def schema(self):
        return Schema(
            {
                "title": "Person",
                "type": "object",
                "properties": {
                    "firstName": {"type": "string", "description": "The person's first name."},
                    "lastName": {"type": "string", "description": "The person's last name."},
                    "age": {
                        "description": "Age in years which must be equal to or greater than zero.",
                        "type": "integer",
                        "minimum": 0,
                    },
                },
            }
        )

    @pytest.fixture(scope="function")
    def example(self, fake):
        return Example(summary=fake.sentence(), description=fake.text(), value={})

    @pytest.fixture(scope="function")
    def header(self, fake, schema, example):
        return Header(
            description=fake.text(),
            required=fake.pybool(),
            deprecated=fake.pybool(),
            allowEmptyValue=fake.pybool(),
            style=fake.sentence(),
            explode=fake.pybool(),
            allowReserved=fake.pybool(),
            schema=schema,
            example=example,
        )

    @pytest.fixture(scope="function")
    def server_variable(self, fake):
        return ServerVariable(enum=fake.pylist(value_types=[str]), default=fake.word(), description=fake.sentence())

    @pytest.fixture(scope="function")
    def server(self, fake, server_variable):
        return Server(url=fake.url(), name=fake.word(), variables={"var": server_variable}, description=fake.sentence())

    @pytest.fixture(scope="function")
    def link(self, fake, server):
        return Link(
            operationId=fake.word(),
            parameters=fake.pydict(value_types=[str]),
            requestBody={},
            description=fake.sentence(),
            server=server,
        )

    @pytest.fixture(scope="function")
    def encoding(self, fake, header):
        return Encoding(
            contentType="",
            headers={"header": header},
            style=fake.word(),
            explode=fake.pybool(),
            allowReserved=fake.pybool(),
        )

    @pytest.fixture(scope="function")
    def media_type(self, fake, schema, example, encoding):
        return MediaType(schema=schema, example=example, encoding={"enc": encoding})

    @pytest.fixture(scope="function")
    def response(self, header, media_type, link):
        return Response(
            description="Foo",
            headers={"header": header},
            content={"content": media_type},
            links={"link": link},
        )

    @pytest.fixture(scope="function")
    def parameter(self, fake, schema, example):
        return Parameter(
            name=fake.word(),
            in_="query",
            description=fake.sentence(),
            required=fake.pybool(),
            deprecated=fake.pybool(),
            allowEmptyValue=fake.pybool(),
            style=fake.word(),
            explode=fake.pybool(),
            allowReserved=fake.pybool(),
            schema=schema,
            example=example,
        )

    @pytest.fixture(scope="function")
    def request_body(self, fake, media_type):
        return RequestBody(content=media_type, description=fake.sentence(), required=fake.pybool())

    @pytest.fixture(scope="function")
    def security(self, fake):
        return Security({fake.word(): fake.pylist(value_types=[str])})

    @pytest.fixture(scope="function")
    def external_docs(self, fake):
        return ExternalDocs(url=fake.url(), description=fake.sentence())

    @pytest.fixture(scope="function")
    def operation(self, fake, response, external_docs, parameter, request_body, security, server):
        return Operation(
            responses=Responses({str(fake.random_number(digits=3)): response}),
            tags=fake.pylist(value_types=[str]),
            summary=fake.sentence(),
            description=fake.text(),
            externalDocs=external_docs,
            operationId=fake.word(),
            parameters=[parameter],
            requestBody=request_body,
            deprecated=fake.pybool(),
            security=[security],
            servers=[server],
        )

    @pytest.fixture(scope="function")
    def path(self, fake, operation, server, parameter):
        return Path(
            summary=fake.sentence(),
            description=fake.text(),
            get=operation,
            put=operation,
            post=operation,
            delete=operation,
            options=operation,
            head=operation,
            patch=operation,
            trace=operation,
            query=operation,
            servers=[server],
            parameters=[parameter],
        )

    @pytest.fixture(scope="function")
    def callback(self, fake, path):
        return Callback({fake.word(): path})

    @pytest.mark.parametrize(
        ["spec", "result"],
        [
            pytest.param(
                {"info": {"title": "Title", "version": "1.0.0"}},
                {
                    "openapi": "3.2.0",
                    "info": {"title": "Title", "version": "1.0.0"},
                    "components": {
                        "callbacks": {},
                        "examples": {},
                        "headers": {},
                        "links": {},
                        "parameters": {},
                        "requestBodies": {},
                        "responses": {},
                        "schemas": {},
                        "securitySchemes": {},
                    },
                    "paths": {},
                },
                id="simple",
            ),
            pytest.param(
                {
                    "info": {
                        "title": "Example API",
                        "summary": "This is an example API specification",
                        "description": "A detailed description of the Example API, including usage and endpoints.",
                        "termsOfService": "https://example.com/terms",
                        "contact": {
                            "name": "API Support",
                            "url": "https://example.com/contact",
                            "email": "support@example.com",
                        },
                        "license": {
                            "name": "MIT",
                            "identifier": "MIT",
                            "url": "https://opensource.org/licenses/MIT",
                        },
                        "version": "1.0.0",
                    },
                    "servers": [
                        {
                            "url": "https://api.example.com/v1",
                            "description": "Production server",
                            "variables": {
                                "version": {
                                    "default": "v1",
                                    "enum": ["v1", "v2"],
                                    "description": "API version",
                                }
                            },
                        },
                        {
                            "url": "https://staging-api.example.com",
                            "description": "Staging server",
                        },
                    ],
                    "security": [
                        {
                            "OAuth2": ["read", "write"],
                            "ApiKeyAuth": [],
                        }
                    ],
                    "tags": [
                        {
                            "name": "users",
                            "description": "Operations related to users",
                            "externalDocs": {
                                "url": "https://docs.example.com/users",
                                "description": "User API documentation",
                            },
                        },
                        {
                            "name": "orders",
                            "description": "Operations related to orders",
                        },
                    ],
                    "externalDocs": {
                        "url": "https://docs.example.com",
                        "description": "Full API documentation",
                    },
                },
                {
                    "components": {
                        "callbacks": {},
                        "examples": {},
                        "headers": {},
                        "links": {},
                        "parameters": {},
                        "requestBodies": {},
                        "responses": {},
                        "schemas": {},
                        "securitySchemes": {},
                    },
                    "externalDocs": {
                        "description": "Full API documentation",
                        "url": "https://docs.example.com",
                    },
                    "info": {
                        "contact": {
                            "email": "support@example.com",
                            "name": "API Support",
                            "url": "https://example.com/contact",
                        },
                        "description": "A detailed description of the Example API, including usage and endpoints.",
                        "license": {
                            "identifier": "MIT",
                            "name": "MIT",
                            "url": "https://opensource.org/licenses/MIT",
                        },
                        "summary": "This is an example API specification",
                        "termsOfService": "https://example.com/terms",
                        "title": "Example API",
                        "version": "1.0.0",
                    },
                    "openapi": "3.2.0",
                    "paths": {},
                    "security": [
                        {
                            "ApiKeyAuth": [],
                            "OAuth2": [
                                "read",
                                "write",
                            ],
                        },
                    ],
                    "servers": [
                        {
                            "description": "Production server",
                            "url": "https://api.example.com/v1",
                            "variables": {
                                "version": {
                                    "default": "v1",
                                    "description": "API version",
                                    "enum": [
                                        "v1",
                                        "v2",
                                    ],
                                },
                            },
                        },
                        {
                            "description": "Staging server",
                            "url": "https://staging-api.example.com",
                        },
                    ],
                    "tags": [
                        {
                            "description": "Operations related to users",
                            "externalDocs": {
                                "description": "User API documentation",
                                "url": "https://docs.example.com/users",
                            },
                            "name": "users",
                        },
                        {
                            "description": "Operations related to orders",
                            "name": "orders",
                        },
                    ],
                },
                id="full",
            ),
        ],
    )
    def test_from_spec_to_dict(self, spec, result):
        assert OpenAPISpec.from_spec(spec).to_dict() == result
        assert OpenAPISpec(info=Info(title="Title", version="1.0.0"))
        assert OpenAPISpec(
            info=Info(
                title="Title",
                version="1.0.0",
                description="Description",
                termsOfService="TOS",
                contact=Contact(name="Contact name", url="Contact url", email="Contact email"),
                license=License(name="License name", url="License url"),
            ),
        )

    def test_path_operations(self, path):
        assert set(path.operations) == {"get", "put", "post", "delete", "options", "head", "patch", "trace", "query"}

    @pytest.mark.parametrize(
        ["spec", "expected"],
        [
            pytest.param(
                {"name": "users", "summary": "User management", "parent": "api", "kind": "nav"},
                {"name": "users", "summary": "User management", "parent": "api", "kind": "nav"},
                id="all_fields",
            ),
            pytest.param({"name": "users"}, {"name": "users"}, id="name_only"),
        ],
    )
    def test_tag_from_spec(self, spec, expected):
        tag = Tag.from_spec(spec)

        assert {k: v for k, v in dataclasses.asdict(tag).items() if v is not None} == expected

    @pytest.mark.parametrize(
        ["spec", "expected"],
        [
            pytest.param(
                {"url": "https://example.com", "name": "production"},
                {"url": "https://example.com", "name": "production"},
                id="named",
            ),
            pytest.param({"url": "https://example.com"}, {"url": "https://example.com"}, id="url_only"),
        ],
    )
    def test_server_from_spec(self, spec, expected):
        server = Server.from_spec(spec)

        assert {k: v for k, v in dataclasses.asdict(server).items() if v is not None} == expected

    def test_add_path(self, spec, path):
        path_name = "foo"
        expected_result = spec.to_dict()
        expected_result["paths"] = {"foo": spec.to_dict(dataclasses.asdict(path))}

        spec.add_path(path_name, path)

        assert spec.to_dict() == expected_result

    def test_add_schema(self, spec, schema):
        schema_name = "foo"
        expected_result = spec.to_dict()
        expected_result["components"]["schemas"] = {schema_name: schema}

        spec.add_schema(schema_name, schema)

        assert spec.to_dict() == expected_result

    def test_add_response(self, spec, response):
        response_name = "foo"
        expected_result = spec.to_dict()
        expected_result["components"]["responses"] = {response_name: spec.to_dict(dataclasses.asdict(response))}

        spec.add_response(response_name, response)

        assert spec.to_dict() == expected_result

    def test_add_parameter(self, spec, parameter):
        parameter_name = "foo"
        expected_result = spec.to_dict()
        expected_result["components"]["parameters"] = {parameter_name: spec.to_dict(dataclasses.asdict(parameter))}

        spec.add_parameter(parameter_name, parameter)

        assert spec.to_dict() == expected_result

    def test_add_example(self, spec, example):
        example_name = "foo"
        expected_result = spec.to_dict()
        expected_result["components"]["examples"] = {example_name: spec.to_dict(dataclasses.asdict(example))}

        spec.add_example(example_name, example)

        assert spec.to_dict() == expected_result

    def test_add_request_body(self, spec, request_body):
        request_body_name = "foo"
        expected_result = spec.to_dict()
        expected_result["components"]["requestBodies"] = {
            request_body_name: spec.to_dict(dataclasses.asdict(request_body))
        }

        spec.add_request_body(request_body_name, request_body)

        assert spec.to_dict() == expected_result

    def test_add_header(self, spec, header):
        header_name = "foo"
        expected_result = spec.to_dict()
        expected_result["components"]["headers"] = {header_name: spec.to_dict(dataclasses.asdict(header))}

        spec.add_header(header_name, header)

        assert spec.to_dict() == expected_result

    def test_add_security(self, spec, security):
        security_name = "foo"
        expected_result = spec.to_dict()
        expected_result["components"]["securitySchemes"] = {security_name: spec.to_dict(security)}

        spec.add_security(security_name, security)

        assert spec.to_dict() == expected_result

    def test_add_link(self, spec, link):
        link_name = "foo"
        expected_result = spec.to_dict()
        expected_result["components"]["links"] = {link_name: spec.to_dict(dataclasses.asdict(link))}

        spec.add_link(link_name, link)

        assert spec.to_dict() == expected_result

    def test_add_callback(self, spec, callback):
        callback_name = "foo"
        expected_result = spec.to_dict()
        expected_result["components"]["callbacks"] = {callback_name: spec.to_dict(callback)}

        spec.add_callback(callback_name, callback)

        assert spec.to_dict() == expected_result


def _fix_ref(value, refs):
    try:
        prefix, name = value.rsplit("/", 1)
        return f"{prefix}/{refs[name]}"
    except KeyError:
        return value


def _replace_refs(schema, refs):
    if isinstance(schema, dict):
        return {k: _fix_ref(v, refs) if k == "$ref" else _replace_refs(v, refs) for k, v in schema.items()}

    if isinstance(schema, list | tuple | set):
        return [_replace_refs(x, refs) for x in schema]

    return schema


class TestCaseOpenAPISchemaRegistry:
    @pytest.fixture(scope="function")
    def registry(self, app):
        return OpenAPISchemaRegistry()

    @pytest.fixture(scope="function")
    def spec(self, openapi_spec):
        return openapi.OpenAPISpec.from_spec(openapi_spec)

    @pytest.mark.parametrize(
        ["operation", "register_schemas", "output"],
        [
            pytest.param(
                openapi.Operation(
                    responses=openapi.Responses(
                        {
                            "200": openapi.Response(
                                description="Foo",
                                content={
                                    "application/json": openapi.MediaType(
                                        schema=openapi.Reference(ref="#!/components/schemas/Foo")
                                    )
                                },
                            )
                        }
                    )
                ),
                ["Foo"],
                ["Foo"],
                id="response_reference",
            ),
            pytest.param(
                openapi.Operation(
                    responses=openapi.Responses(
                        {
                            "200": openapi.Response(
                                description="Bar",
                                content={
                                    "application/json": openapi.MediaType(
                                        schema=openapi.Reference(ref="#!/components/schemas/Bar")
                                    )
                                },
                            )
                        }
                    )
                ),
                ["Bar"],
                ["Foo", "Bar"],
                id="response_reference_nested",
            ),
            pytest.param(
                openapi.Operation(
                    responses=openapi.Responses(
                        {
                            "200": openapi.Response(
                                description="Bar",
                                content={
                                    "application/json": openapi.MediaType(
                                        schema=openapi.Reference(ref="#!/components/schemas/BarMultiple")
                                    )
                                },
                            )
                        }
                    )
                ),
                ["BarMultiple"],
                ["Foo", "BarMultiple"],
                id="response_reference_nested_multiple",
            ),
            pytest.param(
                openapi.Operation(
                    responses=openapi.Responses(
                        {
                            "200": openapi.Response(
                                description="Bar",
                                content={
                                    "application/json": openapi.MediaType(
                                        schema=openapi.Reference(ref="#!/components/schemas/BarList")
                                    )
                                },
                            )
                        }
                    )
                ),
                ["BarList"],
                ["Foo", "BarList"],
                id="response_reference_nested_list",
            ),
            pytest.param(
                openapi.Operation(
                    responses=openapi.Responses(
                        {
                            "200": openapi.Response(
                                description="Bar",
                                content={
                                    "application/json": openapi.MediaType(
                                        schema=openapi.Reference(ref="#!/components/schemas/BarDict")
                                    )
                                },
                            )
                        }
                    )
                ),
                ["BarDict"],
                ["Foo", "BarDict"],
                id="response_reference_nested_dict",
            ),
            pytest.param(
                openapi.Operation(
                    responses=openapi.Responses(
                        {
                            "200": openapi.Response(
                                description="Bar",
                                content={
                                    "application/json": openapi.MediaType(
                                        schema=openapi.Reference(ref="#!/components/schemas/FooBarNested")
                                    )
                                },
                            )
                        }
                    )
                ),
                ["FooBarNested"],
                ["Foo", "Bar", "FooBarNested"],
                id="response_reference_nested_nested",
            ),
            pytest.param(
                openapi.Operation(
                    responses=openapi.Responses(
                        {
                            "200": openapi.Response(
                                description="Foo",
                                content={
                                    "application/json": openapi.MediaType(
                                        schema=openapi.Schema(
                                            {
                                                "type": "object",
                                                "properties": {"foo": {"$ref": "#!/components/schemas/Foo"}},
                                            }
                                        ),
                                    )
                                },
                            )
                        }
                    )
                ),
                ["Foo"],
                ["Foo"],
                id="response_schema",
            ),
            pytest.param(
                openapi.Operation(
                    responses=openapi.Responses(
                        {
                            "200": openapi.Response(
                                description="Bar",
                                content={
                                    "application/json": openapi.MediaType(
                                        schema=openapi.Schema(
                                            {
                                                "type": "object",
                                                "properties": {"bar": {"$ref": "#!/components/schemas/Bar"}},
                                            }
                                        ),
                                    )
                                },
                            )
                        }
                    )
                ),
                ["Bar"],
                ["Foo", "Bar"],
                id="response_schema_nested",
            ),
            pytest.param(
                openapi.Operation(
                    responses=openapi.Responses(
                        {
                            "200": openapi.Response(
                                description="BarMultiple",
                                content={
                                    "application/json": openapi.MediaType(
                                        schema=openapi.Schema(
                                            {
                                                "type": "object",
                                                "properties": {"bar": {"$ref": "#!/components/schemas/BarMultiple"}},
                                            }
                                        ),
                                    )
                                },
                            )
                        }
                    )
                ),
                ["BarMultiple"],
                ["Foo", "BarMultiple"],
                id="response_schema_nested_multiple",
            ),
            pytest.param(
                openapi.Operation(
                    responses=openapi.Responses(
                        {
                            "200": openapi.Response(
                                description="BarList",
                                content={
                                    "application/json": openapi.MediaType(
                                        schema=openapi.Schema(
                                            {
                                                "type": "object",
                                                "properties": {"bar": {"$ref": "#!/components/schemas/BarList"}},
                                            }
                                        ),
                                    )
                                },
                            )
                        }
                    )
                ),
                ["BarList"],
                ["Foo", "BarList"],
                id="response_schema_nested_list",
            ),
            pytest.param(
                openapi.Operation(
                    responses=openapi.Responses(
                        {
                            "200": openapi.Response(
                                description="BarDict",
                                content={
                                    "application/json": openapi.MediaType(
                                        schema=openapi.Schema(
                                            {
                                                "type": "object",
                                                "properties": {"bar": {"$ref": "#!/components/schemas/BarDict"}},
                                            }
                                        ),
                                    )
                                },
                            )
                        }
                    )
                ),
                ["BarDict"],
                ["Foo", "BarDict"],
                id="response_schema_nested_dict",
            ),
            pytest.param(
                openapi.Operation(
                    responses=openapi.Responses(
                        {
                            "200": openapi.Response(
                                description="FooBarNested",
                                content={
                                    "application/json": openapi.MediaType(
                                        schema=openapi.Schema(
                                            {
                                                "type": "object",
                                                "properties": {"bar": {"$ref": "#!/components/schemas/FooBarNested"}},
                                            }
                                        ),
                                    )
                                },
                            )
                        }
                    )
                ),
                ["FooBarNested"],
                ["Foo", "Bar", "FooBarNested"],
                id="response_schema_nested_nested",
            ),
            pytest.param(
                openapi.Operation(
                    responses=openapi.Responses(
                        {
                            "200": openapi.Response(
                                description="Foo",
                                content={
                                    "application/json": openapi.MediaType(
                                        schema=openapi.Schema(
                                            {
                                                "type": "object",
                                                "properties": {
                                                    "foo": {
                                                        "type": "array",
                                                        "items": {"$ref": "#!/components/schemas/Foo"},
                                                    }
                                                },
                                            }
                                        ),
                                    )
                                },
                            )
                        }
                    )
                ),
                ["Foo"],
                ["Foo"],
                id="response_array",
            ),
            pytest.param(
                openapi.Operation(
                    responses=openapi.Responses(
                        {
                            "200": openapi.Response(
                                description="Foo",
                                content={
                                    "application/json": openapi.MediaType(
                                        schema=openapi.Schema(
                                            {"type": "object", "properties": {"foo": {"type": "foo"}}}
                                        ),
                                    )
                                },
                            )
                        }
                    )
                ),
                [],
                [],
                id="response_wrong",
            ),
            pytest.param(
                openapi.Operation(
                    requestBody=openapi.Reference(ref="#!/components/schemas/Foo"), responses=openapi.Responses({})
                ),
                ["Foo"],
                ["Foo"],
                id="body_reference",
            ),
            pytest.param(
                openapi.Operation(
                    requestBody=openapi.Reference(ref="#!/components/schemas/Bar"), responses=openapi.Responses({})
                ),
                ["Bar"],
                ["Foo", "Bar"],
                id="body_reference_nested",
            ),
            pytest.param(
                openapi.Operation(
                    requestBody=openapi.Reference(ref="#!/components/schemas/BarMultiple"),
                    responses=openapi.Responses({}),
                ),
                ["BarMultiple"],
                ["Foo", "BarMultiple"],
                id="body_reference_nested_multiple",
            ),
            pytest.param(
                openapi.Operation(
                    requestBody=openapi.Reference(ref="#!/components/schemas/BarList"), responses=openapi.Responses({})
                ),
                ["BarList"],
                ["Foo", "BarList"],
                id="body_reference_nested_list",
            ),
            pytest.param(
                openapi.Operation(
                    requestBody=openapi.Reference(ref="#!/components/schemas/BarDict"), responses=openapi.Responses({})
                ),
                ["BarDict"],
                ["Foo", "BarDict"],
                id="body_reference_nested_dict",
            ),
            pytest.param(
                openapi.Operation(
                    requestBody=openapi.Reference(ref="#!/components/schemas/FooBarNested"),
                    responses=openapi.Responses({}),
                ),
                ["FooBarNested"],
                ["Foo", "Bar", "FooBarNested"],
                id="body_reference_nested_nested",
            ),
            pytest.param(
                openapi.Operation(
                    requestBody=openapi.RequestBody(
                        description="Foo",
                        content={
                            "application/json": openapi.MediaType(
                                schema=openapi.Schema(
                                    {"type": "object", "properties": {"foo": {"$ref": "#!/components/schemas/Foo"}}}
                                ),
                            )
                        },
                    ),
                    responses=openapi.Responses({}),
                ),
                ["Foo"],
                ["Foo"],
                id="body_schema",
            ),
            pytest.param(
                openapi.Operation(
                    requestBody=openapi.RequestBody(
                        description="Bar",
                        content={
                            "application/json": openapi.MediaType(
                                schema=openapi.Schema(
                                    {"type": "object", "properties": {"foo": {"$ref": "#!/components/schemas/Bar"}}}
                                ),
                            )
                        },
                    ),
                    responses=openapi.Responses({}),
                ),
                ["Bar"],
                ["Foo", "Bar"],
                id="body_schema_nested",
            ),
            pytest.param(
                openapi.Operation(
                    requestBody=openapi.RequestBody(
                        description="BarMultiple",
                        content={
                            "application/json": openapi.MediaType(
                                schema=openapi.Schema(
                                    {
                                        "type": "object",
                                        "properties": {"foo": {"$ref": "#!/components/schemas/BarMultiple"}},
                                    }
                                ),
                            )
                        },
                    ),
                    responses=openapi.Responses({}),
                ),
                ["BarMultiple"],
                ["Foo", "BarMultiple"],
                id="body_schema_nested_multiple",
            ),
            pytest.param(
                openapi.Operation(
                    requestBody=openapi.RequestBody(
                        description="BarList",
                        content={
                            "application/json": openapi.MediaType(
                                schema=openapi.Schema(
                                    {"type": "object", "properties": {"foo": {"$ref": "#!/components/schemas/BarList"}}}
                                ),
                            )
                        },
                    ),
                    responses=openapi.Responses({}),
                ),
                ["BarList"],
                ["Foo", "BarList"],
                id="body_schema_nested_list",
            ),
            pytest.param(
                openapi.Operation(
                    requestBody=openapi.RequestBody(
                        description="BarDict",
                        content={
                            "application/json": openapi.MediaType(
                                schema=openapi.Schema(
                                    {"type": "object", "properties": {"foo": {"$ref": "#!/components/schemas/BarDict"}}}
                                ),
                            )
                        },
                    ),
                    responses=openapi.Responses({}),
                ),
                ["BarDict"],
                ["Foo", "BarDict"],
                id="body_schema_nested_dict",
            ),
            pytest.param(
                openapi.Operation(
                    requestBody=openapi.RequestBody(
                        description="FooBarNested",
                        content={
                            "application/json": openapi.MediaType(
                                schema=openapi.Schema(
                                    {
                                        "type": "object",
                                        "properties": {"foo": {"$ref": "#!/components/schemas/FooBarNested"}},
                                    }
                                ),
                            )
                        },
                    ),
                    responses=openapi.Responses({}),
                ),
                ["FooBarNested"],
                ["Foo", "Bar", "FooBarNested"],
                id="body_schema_nested_nested",
            ),
            pytest.param(
                openapi.Operation(
                    requestBody=openapi.RequestBody(
                        description="Foo",
                        content={
                            "application/json": openapi.MediaType(
                                schema=openapi.Schema(
                                    {
                                        "type": "object",
                                        "properties": {
                                            "foo": {"type": "array", "items": {"$ref": "#!/components/schemas/Foo"}}
                                        },
                                    }
                                ),
                            )
                        },
                    ),
                    responses=openapi.Responses({}),
                ),
                ["Foo"],
                ["Foo"],
                id="body_array",
            ),
            pytest.param(
                openapi.Operation(
                    requestBody=openapi.RequestBody(
                        description="Foo",
                        content={
                            "application/json": openapi.MediaType(
                                schema=openapi.Schema({"type": "object", "properties": {"foo": {"type": "foo"}}}),
                            )
                        },
                    ),
                    responses=openapi.Responses({}),
                ),
                [],
                [],
                id="body_wrong",
            ),
            pytest.param(
                openapi.Operation(
                    parameters=[openapi.Reference(ref="#!/components/schemas/Foo")], responses=openapi.Responses({})
                ),
                ["Foo"],
                ["Foo"],
                id="parameter_reference",
            ),
            pytest.param(
                openapi.Operation(
                    parameters=[openapi.Reference(ref="#!/components/schemas/Bar")], responses=openapi.Responses({})
                ),
                ["Bar"],
                ["Foo", "Bar"],
                id="parameter_reference_nested",
            ),
            pytest.param(
                openapi.Operation(
                    parameters=[openapi.Reference(ref="#!/components/schemas/BarMultiple")],
                    responses=openapi.Responses({}),
                ),
                ["BarMultiple"],
                ["Foo", "BarMultiple"],
                id="parameter_reference_nested_multiple",
            ),
            pytest.param(
                openapi.Operation(
                    parameters=[openapi.Reference(ref="#!/components/schemas/BarList")], responses=openapi.Responses({})
                ),
                ["BarList"],
                ["Foo", "BarList"],
                id="parameter_reference_nested_list",
            ),
            pytest.param(
                openapi.Operation(
                    parameters=[openapi.Reference(ref="#!/components/schemas/BarDict")], responses=openapi.Responses({})
                ),
                ["BarDict"],
                ["Foo", "BarDict"],
                id="parameter_reference_nested_dict",
            ),
            pytest.param(
                openapi.Operation(
                    parameters=[openapi.Reference(ref="#!/components/schemas/FooBarNested")],
                    responses=openapi.Responses({}),
                ),
                ["FooBarNested"],
                ["Foo", "Bar", "FooBarNested"],
                id="parameter_reference_nested_nested",
            ),
            pytest.param(
                openapi.Operation(
                    parameters=[
                        openapi.Parameter(
                            in_="query",
                            name="foo",
                            schema=openapi.Schema(
                                {"type": "object", "properties": {"foo": {"$ref": "#!/components/schemas/Foo"}}}
                            ),
                        )
                    ],
                    responses=openapi.Responses({}),
                ),
                ["Foo"],
                ["Foo"],
                id="parameter_schema",
            ),
            pytest.param(
                openapi.Operation(
                    parameters=[
                        openapi.Parameter(
                            in_="query",
                            name="bar",
                            schema=openapi.Schema(
                                {"type": "object", "properties": {"bar": {"$ref": "#!/components/schemas/Bar"}}}
                            ),
                        )
                    ],
                    responses=openapi.Responses({}),
                ),
                ["Bar"],
                ["Foo", "Bar"],
                id="parameter_schema_nested",
            ),
            pytest.param(
                openapi.Operation(
                    parameters=[
                        openapi.Parameter(
                            in_="query",
                            name="bar",
                            schema=openapi.Schema(
                                {"type": "object", "properties": {"bar": {"$ref": "#!/components/schemas/BarMultiple"}}}
                            ),
                        )
                    ],
                    responses=openapi.Responses({}),
                ),
                ["BarMultiple"],
                ["Foo", "BarMultiple"],
                id="parameter_schema_nested_multiple",
            ),
            pytest.param(
                openapi.Operation(
                    parameters=[
                        openapi.Parameter(
                            in_="query",
                            name="bar",
                            schema=openapi.Schema(
                                {"type": "object", "properties": {"bar": {"$ref": "#!/components/schemas/BarList"}}}
                            ),
                        )
                    ],
                    responses=openapi.Responses({}),
                ),
                ["BarList"],
                ["Foo", "BarList"],
                id="parameter_schema_nested_list",
            ),
            pytest.param(
                openapi.Operation(
                    parameters=[
                        openapi.Parameter(
                            in_="query",
                            name="bar",
                            schema=openapi.Schema(
                                {"type": "object", "properties": {"bar": {"$ref": "#!/components/schemas/BarDict"}}}
                            ),
                        )
                    ],
                    responses=openapi.Responses({}),
                ),
                ["BarDict"],
                ["Foo", "BarDict"],
                id="parameter_schema_nested_dict",
            ),
            pytest.param(
                openapi.Operation(
                    parameters=[
                        openapi.Parameter(
                            in_="query",
                            name="bar",
                            schema=openapi.Schema(
                                {
                                    "type": "object",
                                    "properties": {"bar": {"$ref": "#!/components/schemas/FooBarNested"}},
                                }
                            ),
                        )
                    ],
                    responses=openapi.Responses({}),
                ),
                ["FooBarNested"],
                ["Foo", "Bar", "FooBarNested"],
                id="parameter_schema_nested_nested",
            ),
            pytest.param(
                openapi.Operation(
                    parameters=[
                        openapi.Parameter(
                            in_="query",
                            name="foo",
                            schema=openapi.Schema(
                                {
                                    "type": "object",
                                    "properties": {
                                        "foo": {"type": "array", "items": {"$ref": "#!/components/schemas/Foo"}}
                                    },
                                }
                            ),
                        )
                    ],
                    responses=openapi.Responses({}),
                ),
                ["Foo"],
                ["Foo"],
                id="parameter_array",
            ),
            pytest.param(
                openapi.Operation(
                    parameters=[
                        openapi.Parameter(
                            in_="query",
                            name="foo",
                            schema=openapi.Schema({"type": "object", "properties": {"foo": {"type": "foo"}}}),
                        )
                    ],
                    responses=openapi.Responses({}),
                ),
                [],
                [],
                id="parameter_wrong",
            ),
            pytest.param(
                openapi.Operation(
                    callbacks={"200": openapi.Reference(ref="#!/components/schemas/Foo")},
                    responses=openapi.Responses({}),
                ),
                ["Foo"],
                ["Foo"],
                id="callback_reference",
            ),
            pytest.param(
                openapi.Operation(
                    callbacks={"200": openapi.Reference(ref="#!/components/schemas/Bar")},
                    responses=openapi.Responses({}),
                ),
                ["Bar"],
                ["Foo", "Bar"],
                id="callback_reference_nested",
            ),
            pytest.param(
                openapi.Operation(
                    callbacks={"200": openapi.Reference(ref="#!/components/schemas/BarMultiple")},
                    responses=openapi.Responses({}),
                ),
                ["BarMultiple"],
                ["Foo", "BarMultiple"],
                id="callback_reference_nested_multiple",
            ),
            pytest.param(
                openapi.Operation(
                    callbacks={"200": openapi.Reference(ref="#!/components/schemas/BarList")},
                    responses=openapi.Responses({}),
                ),
                ["BarList"],
                ["Foo", "BarList"],
                id="callback_reference_nested_list",
            ),
            pytest.param(
                openapi.Operation(
                    callbacks={"200": openapi.Reference(ref="#!/components/schemas/BarDict")},
                    responses=openapi.Responses({}),
                ),
                ["BarDict"],
                ["Foo", "BarDict"],
                id="callback_reference_nested_dict",
            ),
            pytest.param(
                openapi.Operation(
                    callbacks={"200": openapi.Reference(ref="#!/components/schemas/FooBarNested")},
                    responses=openapi.Responses({}),
                ),
                ["FooBarNested"],
                ["Foo", "Bar", "FooBarNested"],
                id="callback_reference_nested_nested",
            ),
            pytest.param(
                openapi.Operation(
                    callbacks={
                        "foo": openapi.Callback(
                            {
                                "/callback": openapi.Path(
                                    get=openapi.Operation(
                                        responses=openapi.Responses(
                                            {
                                                "200": openapi.Response(
                                                    description="Foo",
                                                    content={
                                                        "application/json": openapi.MediaType(
                                                            schema=openapi.Schema(
                                                                {
                                                                    "type": "object",
                                                                    "properties": {
                                                                        "foo": {"$ref": "#!/components/schemas/Foo"}
                                                                    },
                                                                }
                                                            )
                                                        )
                                                    },
                                                )
                                            }
                                        )
                                    )
                                )
                            }
                        )
                    },
                    responses=openapi.Responses({}),
                ),
                ["Foo"],
                ["Foo"],
                id="callback_schema",
            ),
            pytest.param(
                openapi.Operation(
                    callbacks={
                        "foo": openapi.Callback(
                            {
                                "/callback": openapi.Path(
                                    get=openapi.Operation(
                                        responses=openapi.Responses(
                                            {
                                                "200": openapi.Response(
                                                    description="Bar",
                                                    content={
                                                        "application/json": openapi.MediaType(
                                                            schema=openapi.Schema(
                                                                {
                                                                    "type": "object",
                                                                    "properties": {
                                                                        "bar": {"$ref": "#!/components/schemas/Bar"}
                                                                    },
                                                                }
                                                            )
                                                        )
                                                    },
                                                )
                                            }
                                        )
                                    )
                                )
                            }
                        )
                    },
                    responses=openapi.Responses({}),
                ),
                ["Bar"],
                ["Foo", "Bar"],
                id="callback_schema_nested",
            ),
            pytest.param(
                openapi.Operation(
                    callbacks={
                        "foo": openapi.Callback(
                            {
                                "/callback": openapi.Path(
                                    get=openapi.Operation(
                                        responses=openapi.Responses(
                                            {
                                                "200": openapi.Response(
                                                    description="BarMultiple",
                                                    content={
                                                        "application/json": openapi.MediaType(
                                                            schema=openapi.Schema(
                                                                {
                                                                    "type": "object",
                                                                    "properties": {
                                                                        "bar": {
                                                                            "$ref": "#!/components/schemas/BarMultiple"
                                                                        }
                                                                    },
                                                                }
                                                            )
                                                        )
                                                    },
                                                )
                                            }
                                        )
                                    )
                                )
                            }
                        )
                    },
                    responses=openapi.Responses({}),
                ),
                ["BarMultiple"],
                ["Foo", "BarMultiple"],
                id="callback_schema_nested_multiple",
            ),
            pytest.param(
                openapi.Operation(
                    callbacks={
                        "foo": openapi.Callback(
                            {
                                "/callback": openapi.Path(
                                    get=openapi.Operation(
                                        responses=openapi.Responses(
                                            {
                                                "200": openapi.Response(
                                                    description="BarList",
                                                    content={
                                                        "application/json": openapi.MediaType(
                                                            schema=openapi.Schema(
                                                                {
                                                                    "type": "object",
                                                                    "properties": {
                                                                        "bar": {"$ref": "#!/components/schemas/BarList"}
                                                                    },
                                                                }
                                                            )
                                                        )
                                                    },
                                                )
                                            }
                                        )
                                    )
                                )
                            }
                        )
                    },
                    responses=openapi.Responses({}),
                ),
                ["BarList"],
                ["Foo", "BarList"],
                id="callback_schema_nested_list",
            ),
            pytest.param(
                openapi.Operation(
                    callbacks={
                        "foo": openapi.Callback(
                            {
                                "/callback": openapi.Path(
                                    get=openapi.Operation(
                                        responses=openapi.Responses(
                                            {
                                                "200": openapi.Response(
                                                    description="BarDict",
                                                    content={
                                                        "application/json": openapi.MediaType(
                                                            schema=openapi.Schema(
                                                                {
                                                                    "type": "object",
                                                                    "properties": {
                                                                        "bar": {"$ref": "#!/components/schemas/BarDict"}
                                                                    },
                                                                }
                                                            )
                                                        )
                                                    },
                                                )
                                            }
                                        )
                                    )
                                )
                            }
                        )
                    },
                    responses=openapi.Responses({}),
                ),
                ["BarDict"],
                ["Foo", "BarDict"],
                id="callback_schema_nested_dict",
            ),
            pytest.param(
                openapi.Operation(
                    callbacks={
                        "foo": openapi.Callback(
                            {
                                "/callback": openapi.Path(
                                    get=openapi.Operation(
                                        responses=openapi.Responses(
                                            {
                                                "200": openapi.Response(
                                                    description="FooBarNested",
                                                    content={
                                                        "application/json": openapi.MediaType(
                                                            schema=openapi.Schema(
                                                                {
                                                                    "type": "object",
                                                                    "properties": {
                                                                        "bar": {
                                                                            "$ref": "#!/components/schemas/FooBarNested"
                                                                        }
                                                                    },
                                                                }
                                                            )
                                                        )
                                                    },
                                                )
                                            }
                                        )
                                    )
                                )
                            }
                        )
                    },
                    responses=openapi.Responses({}),
                ),
                ["FooBarNested"],
                ["Foo", "Bar", "FooBarNested"],
                id="callback_schema_nested_nested",
            ),
            pytest.param(
                openapi.Operation(
                    callbacks={
                        "foo": openapi.Callback(
                            {
                                "/callback": openapi.Path(
                                    get=openapi.Operation(
                                        responses=openapi.Responses(
                                            {
                                                "200": openapi.Response(
                                                    description="Foo",
                                                    content={
                                                        "application/json": openapi.MediaType(
                                                            schema=openapi.Schema(
                                                                {
                                                                    "type": "object",
                                                                    "properties": {"foo": {"type": "foo"}},
                                                                }
                                                            )
                                                        )
                                                    },
                                                )
                                            }
                                        )
                                    )
                                )
                            }
                        )
                    },
                    responses=openapi.Responses({}),
                ),
                [],
                [],
                id="callback_wrong",
            ),
        ],
    )
    def test_used(self, registry, schemas, spec, operation, register_schemas, output):
        for schema in register_schemas:
            registry.register(schemas[schema].schema, name=schema)

        expected_output = {id(schemas[schema].schema) for schema in output}

        spec.add_path("/", openapi.Path(get=operation))

        assert set(registry.used(spec).keys()) == expected_output

    @pytest.mark.parametrize(
        ["multiple", "result"],
        (
            pytest.param(
                False,
                openapi.Reference(ref="#/components/schemas/Foo"),
                id="schema",
            ),
            pytest.param(
                True,
                openapi.Schema({"type": "array", "items": {"$ref": "#/components/schemas/Foo"}}),
                id="array",
            ),
        ),
    )
    def test_get_openapi_ref(self, multiple, result, registry, foo_schema):
        schema = foo_schema.schema
        registry.register(schema, name="Foo")
        assert registry.get_openapi_ref(schema, multiple=multiple) == result

    @pytest.mark.parametrize(
        "schema",
        [
            pytest.param(
                openapi.Schema({"type": "array", "items": {"type": "string"}}),
                id="array_items_without_ref",
            ),
            pytest.param(
                openapi.Schema({"allOf": "not-a-list"}),
                id="composer_not_a_list",
            ),
            pytest.param(
                openapi.Schema({"properties": "not-a-dict"}),
                id="properties_not_a_dict",
            ),
        ],
    )
    def test_get_schema_references_from_schema_malformed(self, registry, schema):
        assert registry._get_schema_references_from_schema(schema) == []

    @pytest.mark.parametrize(
        "responses",
        [
            pytest.param(
                openapi.Responses(
                    {"200": openapi.Response(description="Foo", content={"application/json": openapi.MediaType()})}
                ),
                id="media_type_without_schema",
            ),
        ],
    )
    def test_get_schema_references_from_operation_responses_malformed(self, registry, responses):
        assert registry._get_schema_references_from_operation_responses(responses) == []

    @pytest.mark.parametrize(
        "request_body",
        [
            pytest.param(
                openapi.RequestBody(content={"application/json": openapi.MediaType()}),
                id="media_type_without_schema",
            ),
        ],
    )
    def test_get_schema_references_from_operation_request_body_malformed(self, registry, request_body):
        assert registry._get_schema_references_from_operation_request_body(request_body) == []

    def test_get_schema_references_from_operation_parameters_without_schema(self, registry):
        parameters = [openapi.Parameter(name="foo", in_="query", schema=None)]

        assert registry._get_schema_references_from_operation_parameters(parameters) == []


class TestCaseSchemaGenerator:
    @pytest.fixture(scope="function")
    def owner_schema(self, app):
        if app.schema.schema_library.name == "pydantic":
            schema = pydantic.create_model("Owner", name=(str, ...), __module__="pydantic.main")
            name = "pydantic.main.Owner"
        elif app.schema.schema_library.name == "typesystem":
            schema = typesystem.Schema(title="Owner", fields={"name": typesystem.fields.String()})
            name = "typesystem.schemas.Owner"
        elif app.schema.schema_library.name == "marshmallow":
            schema = type("Owner", (marshmallow.Schema,), {"name": marshmallow.fields.String()})
            name = "abc.Owner"
        else:
            raise ValueError(f"Wrong schema lib: {app.schema.schema_library.name}")
        return namedtuple("OwnerSchema", ("schema", "name"))(schema, name)

    @pytest.fixture(scope="function")
    def puppy_schema(self, app, owner_schema):
        if app.schema.schema_library.name == "pydantic":
            schema = pydantic.create_model(
                "Puppy", name=(str, ...), owner=(owner_schema.schema, ...), __module__="pydantic.main"
            )
            name = "pydantic.main.Puppy"
        elif app.schema.schema_library.name == "typesystem":
            schema = typesystem.Schema(
                title="Puppy",
                fields={
                    "name": typesystem.fields.String(),
                    "owner": typesystem.Reference(
                        to="Owner", definitions=typesystem.Definitions({"Owner": owner_schema.schema})
                    ),
                },
            )
            name = "typesystem.schemas.Puppy"
        elif app.schema.schema_library.name == "marshmallow":
            schema = type(
                "Puppy",
                (marshmallow.Schema,),
                {
                    "name": marshmallow.fields.String(),
                    "owner": marshmallow.fields.Nested(owner_schema.schema),
                },
            )
            name = "abc.Puppy"
        else:
            raise ValueError(f"Wrong schema lib: {app.schema.schema_library.name}")
        return namedtuple("PuppySchema", ("schema", "name"))(schema, name)

    @pytest.fixture(scope="function")
    def body_param_schema(self, app):
        if app.schema.schema_library.name == "pydantic":
            schema = pydantic.create_model("BodyParam", name=(str, ...), __module__="pydantic.main")
            name = "pydantic.main.BodyParam"
        elif app.schema.schema_library.name == "typesystem":
            schema = typesystem.Schema(title="BodyParam", fields={"name": typesystem.fields.String()})
            name = "typesystem.schemas.BodyParam"
        elif app.schema.schema_library.name == "marshmallow":
            schema = type("BodyParam", (marshmallow.Schema,), {"name": marshmallow.fields.String()})
            name = "abc.BodyParam"
        else:
            raise ValueError(f"Wrong schema lib: {app.schema.schema_library.name}")
        return namedtuple("BodyParamSchema", ("schema", "name"))(schema, name)

    @pytest.fixture(scope="function")
    def schemas(self, owner_schema, puppy_schema, body_param_schema):
        return {"Owner": owner_schema, "Puppy": puppy_schema, "BodyParam": body_param_schema}

    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app, puppy_schema, body_param_schema):  # noqa: C901
        @app.route("/endpoint/", methods=["GET"])
        class PuppyEndpoint(HTTPEndpoint):
            async def get(self) -> t.Annotated[types.Schema, types.SchemaMetadata(puppy_schema.schema)]:
                """
                description: Endpoint.
                responses:
                  200:
                    description: Component.
                """
                return {"name": "Canna"}

        @app.route("/custom-component/", methods=["GET"])
        async def get() -> t.Annotated[types.Schema, types.SchemaMetadata(puppy_schema.schema)]:
            """
            description: Custom component.
            responses:
              200:
                description: Component.
            """
            return {"name": "Canna"}

        @app.route("/many-components/", methods=["GET"])
        async def many_components() -> t.Annotated[types.SchemaList, types.SchemaMetadata(puppy_schema.schema)]:
            """
            description: Many custom components.
            responses:
              200:
                description: Many components.
            """
            return [{"name": "foo"}, {"name": "bar"}]

        @app.route("/query-param/", methods=["GET"])
        async def query_param(param1: int, param2: str | None = None, param3: bool = True):
            """
            description: Query param.
            responses:
              200:
                description: Param.
            """
            return {"name": param2}

        @app.route("/path-param/{param:int}/", methods=["GET"])
        async def path_param(param: int):
            """
            description: Path param.
            responses:
              200:
                description: Param.
            """
            return {"name": param}

        @app.route("/body-param/", methods=["POST"])
        async def body_param(param: t.Annotated[types.Schema, types.SchemaMetadata(body_param_schema.schema)]):
            """
            description: Body param.
            responses:
              200:
                description: Param.
            """
            return {"name": param["name"]}

        @app.route("/default-response/", methods=["GET"])
        async def default_response():
            """
            description: Default response.
            """
            return {"name": "Canna"}

        @app.route("/multiple-responses/", methods=["GET"])
        async def multiple_responses():
            """
            description: Multiple responses.
            responses:
              200:
                description: OK.
              400:
                description: Bad Request.
            """
            return {}

        @app.route("/custom-params/", methods=["GET"])
        async def custom_params(name: str):
            """
            description: Custom params.
            parameters:
              - in: query
                name: name
                schema:
                    type: string
                required: true
                description: The query param
            responses:
              200:
                description: OK.
            """
            return {}

        @app.route("/custom-body/", methods=["POST"])
        async def custom_body():
            """
            description: Custom body.
            requestBody:
                description: The body request
                required: true
                content:
                    multipart/form-data:
                        schema:
                            type: object
                            properties:
                                model:
                                    type: string
                                    format: binary
                                    description: The model file
                                name:
                                    type: string
                                    description: The model name
                                description:
                                    type: string
                                    description: The model description
            responses:
              200:
                description: OK.
            """
            return {}

        @app.route("/wrong-schema/", methods=["POST"])
        async def wrong():
            """
            Wrong schema.
            """
            return {}

        sub_app = Flama(schema=None, docs=None, schema_library=app.schema.schema_library.name)
        sub_app.add_route("/custom-component/", endpoint=get, methods=["GET"])
        app.mount("/mount", sub_app)

        nested_app = Flama(schema=None, docs=None, schema_library=app.schema.schema_library.name)
        nested_app.add_route("/nested-component/", endpoint=get, methods=["GET"])
        mounted_app = Flama(schema=None, docs=None, schema_library=app.schema.schema_library.name)
        mounted_app.mount("/mount", nested_app)
        app.mount("/nested", mounted_app)

    def test_schema_info(self, app):
        schema = app.schema.schema["info"]

        assert schema["title"] == "Foo"
        assert schema["version"] == "1.0.0"
        assert schema["description"] == "Bar"

    def test_components_schemas(self, app, schemas):
        used_schemas = app.schema.schema["components"]["schemas"]

        # Check declared components are only those that are in use
        assert set(used_schemas.keys()) == {
            schemas["Owner"].name,
            schemas["Puppy"].name,
            schemas["BodyParam"].name,
            "flama.core.APIError",
        }

    @pytest.mark.parametrize(
        "path,verb,expected_schema",
        [
            pytest.param(
                "/query-param/",
                "get",
                {
                    "description": "Query param.",
                    "responses": {
                        "200": {"description": "Param."},
                        "default": {
                            "description": "Unexpected error.",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/flama.core.APIError"}}
                            },
                        },
                    },
                    "parameters": [
                        {
                            "name": "param1",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "integer"},
                        },
                        {
                            "name": "param2",
                            "in": "query",
                            "required": False,
                            "schema": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                        },
                        {
                            "name": "param3",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "boolean", "default": True},
                        },
                    ],
                },
                id="query_param",
            ),
            pytest.param(
                "/path-param/{param}/",
                "get",
                {
                    "description": "Path param.",
                    "responses": {
                        "200": {"description": "Param."},
                        "default": {
                            "description": "Unexpected error.",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/flama.core.APIError"}}
                            },
                        },
                    },
                    "parameters": [
                        {
                            "name": "param",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ],
                },
                id="path_param",
            ),
            pytest.param(
                "/body-param/",
                "post",
                {
                    "description": "Body param.",
                    "responses": {
                        "200": {"description": "Param."},
                        "default": {
                            "description": "Unexpected error.",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/flama.core.APIError"}}
                            },
                        },
                    },
                    "requestBody": {
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/BodyParam"}}}
                    },
                },
                id="body_param",
            ),
            pytest.param(
                "/custom-component/",
                "get",
                {
                    "description": "Custom component.",
                    "responses": {
                        "200": {
                            "description": "Component.",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Puppy"}}},
                        },
                        "default": {
                            "description": "Unexpected error.",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/flama.core.APIError"}}
                            },
                        },
                    },
                },
                id="response_schema_single",
            ),
            pytest.param(
                "/many-components/",
                "get",
                {
                    "description": "Many custom components.",
                    "responses": {
                        "200": {
                            "description": "Many components.",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Puppy"}}},
                        },
                        "default": {
                            "description": "Unexpected error.",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/flama.core.APIError"}}
                            },
                        },
                    },
                },
                id="response_schema_multiple",
            ),
            pytest.param(
                "/endpoint/",
                "get",
                {
                    "description": "Endpoint.",
                    "responses": {
                        "200": {
                            "description": "Component.",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Puppy"}}},
                        },
                        "default": {
                            "description": "Unexpected error.",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/flama.core.APIError"}}
                            },
                        },
                    },
                },
                id="response_schema_endpoint",
            ),
            pytest.param(
                "/mount/custom-component/",
                "get",
                {
                    "description": "Custom component.",
                    "responses": {
                        "200": {
                            "description": "Component.",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Puppy"}}},
                        },
                        "default": {
                            "description": "Unexpected error.",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/flama.core.APIError"}}
                            },
                        },
                    },
                },
                id="response_schema_mount",
            ),
            pytest.param(
                "/nested/mount/nested-component/",
                "get",
                {
                    "description": "Custom component.",
                    "responses": {
                        "200": {
                            "description": "Component.",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Puppy"}}},
                        },
                        "default": {
                            "description": "Unexpected error.",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/flama.core.APIError"}}
                            },
                        },
                    },
                },
                id="response_schema_nested_mount",
            ),
            pytest.param(
                "/default-response/",
                "get",
                {
                    "description": "Default response.",
                    "responses": {
                        "default": {
                            "description": "Unexpected error.",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/flama.core.APIError"}}
                            },
                        }
                    },
                },
                id="default_response_schema",
            ),
            pytest.param(
                "/multiple-responses/",
                "get",
                {
                    "description": "Multiple responses.",
                    "responses": {
                        "200": {"description": "OK."},
                        "400": {"description": "Bad Request."},
                        "default": {
                            "description": "Unexpected error.",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/flama.core.APIError"}}
                            },
                        },
                    },
                },
                id="multiple_responses",
            ),
            pytest.param(
                "/custom-params/",
                "get",
                {
                    "description": "Custom params.",
                    "parameters": [
                        {
                            "in": "query",
                            "name": "name",
                            "schema": {"type": "string"},
                            "required": True,
                            "description": "The query param",
                        }
                    ],
                    "responses": {
                        "200": {"description": "OK."},
                        "default": {
                            "description": "Unexpected error.",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/flama.core.APIError"}}
                            },
                        },
                    },
                },
                id="custom_params",
            ),
            pytest.param(
                "/custom-body/",
                "post",
                {
                    "description": "Custom body.",
                    "requestBody": {
                        "content": {
                            "multipart/form-data": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "model": {
                                            "type": "string",
                                            "format": "binary",
                                            "description": "The model file",
                                        },
                                        "name": {"type": "string", "description": "The model name"},
                                        "description": {"type": "string", "description": "The model description"},
                                    },
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {"description": "OK."},
                        "default": {
                            "description": "Unexpected error.",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/flama.core.APIError"}}
                            },
                        },
                    },
                },
                id="custom_body",
            ),
            pytest.param(
                "/wrong-schema/",
                "post",
                {},
                id="wrong_schema",
            ),
        ],
    )
    def test_schema(self, app, schemas, path, verb, expected_schema):
        schema = _replace_refs(expected_schema, {k: v.name for k, v in schemas.items()})

        assert_recursive_contains(schema, app.schema.schema["paths"][path][verb])

    def test_build_endpoint_body_schema_already_registered(self, openapi_spec, body_param_schema):
        generator = openapi.SchemaGenerator(openapi_spec)
        generator.schemas.register(schema=body_param_schema.schema)

        endpoint = openapi.EndpointInfo(
            path="/body-param/",
            method="post",
            func=lambda: None,
            query_parameters={},
            path_parameters={},
            body_parameter=ds.Parameter(
                name="param",
                location=ds.ParameterLocation.body,
                type=t.Annotated[types.Schema, types.SchemaMetadata(body_param_schema.schema)],
            ),
            response_parameter=ds.Parameter(name="response", location=ds.ParameterLocation.response, type=None),
        )

        request_body = generator._build_endpoint_body(endpoint, {})

        assert request_body.content["application/json"] == openapi.MediaType(
            schema=generator.schemas.get_openapi_ref(body_param_schema.schema, multiple=False)
        )

    def test_get_api_schema_operation_error(self, app, openapi_spec, caplog_flama):
        generator = openapi.SchemaGenerator(openapi_spec)

        with patch.object(generator, "get_operation_schema", side_effect=ValueError("Cannot build operation")):
            api_schema = generator.get_api_schema(app.routes)

        assert api_schema["paths"] == {}
        assert any("Cannot generate schema for endpoint" in record.message for record in caplog_flama.records)

    def test_get_api_schema_recursive_schema_terminates(self, app):
        """A self-referencing (recursive) schema must not loop forever while collecting used schemas."""
        if app.schema.schema_library.name != "pydantic":
            pytest.skip("Recursive-model regression is exercised through the pydantic library")

        @app.route("/nodes/", methods=["GET"])
        def list_nodes() -> t.Annotated[types.SchemaList, types.SchemaMetadata(_RecursiveNode)]: ...  # pragma: no cover

        # Run generation in a worker thread so an infinite-loop regression fails fast instead of hanging the suite.
        result: dict[str, t.Any] = {}

        def run() -> None:
            result["schema"] = app.schema.schema

        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        worker.join(timeout=10)

        assert not worker.is_alive(), "OpenAPI generation for a recursive schema did not terminate"

        schemas = result["schema"]["components"]["schemas"]
        node_key = next(k for k in schemas if k.split(".")[-1] == "_RecursiveNode")
        assert "_RecursiveNode" in node_key
        # The recursive model references itself within the generated component schema.
        assert "_RecursiveNode" in str(schemas[node_key])

    def test_schema_references_resolve(self, app):
        """A reference to a component that the document never declares makes the whole document unusable."""
        schema = app.schema.schema
        references = set(re.findall(r'"\$ref": "([^"]+)"', json.dumps(schema)))

        assert references, "the document declares no reference, so nothing is being checked"
        assert {r for r in references if not r.startswith("#/components/schemas/")} == set()
        assert {r.rsplit("/", 1)[1] for r in references} <= set(schema["components"]["schemas"])

    def test_enum_is_described_where_it_is_used(self, app):
        """An enum is not published as a component, so a reference to one would never resolve."""
        if app.schema.schema_library.name != "pydantic":
            pytest.skip("Only pydantic emits an enum as a definition of its own")

        @app.route("/enum/", methods=["GET"])
        def get_enum() -> t.Annotated[types.Schema, types.SchemaMetadata(_EnumNode)]: ...  # pragma: no cover

        schema = app.schema.schema
        node = next(v for k, v in schema["components"]["schemas"].items() if k.split(".")[-1] == "_EnumNode")
        references = set(re.findall(r'"\$ref": "([^"]+)"', json.dumps(schema)))

        assert node["properties"]["status"]["enum"] == ["available", "adopted"]
        assert {r.rsplit("/", 1)[1] for r in references} <= set(schema["components"]["schemas"])

    @pytest.fixture(scope="function")
    def docstring_schema(self, app):
        """A schema nothing else references, so only the docstring can pull it into the document."""
        if app.schema.schema_library.name == "pydantic":
            schema = pydantic.create_model("DocstringRef", value=(str, ...), __module__="pydantic.main")
        elif app.schema.schema_library.name == "typesystem":
            schema = typesystem.Schema(title="DocstringRef", fields={"value": typesystem.fields.String()})
        elif app.schema.schema_library.name == "marshmallow":
            schema = type("DocstringRef", (marshmallow.Schema,), {"value": marshmallow.fields.String()})
        else:
            raise ValueError(f"Wrong schema lib: {app.schema.schema_library.name}")

        app.schema.register_schema("DocstringRef", schema)
        return schema

    @pytest.mark.parametrize(
        ["section", "docstring"],
        [
            pytest.param(
                "requestBody",
                """
                description: A body declared by hand.
                requestBody:
                    content:
                        application/json:
                            schema:
                                $ref: '#/components/schemas/DocstringRef'
                responses:
                  200:
                    description: OK.
                """,
                id="request_body",
            ),
            pytest.param(
                "responses",
                """
                description: A response declared by hand.
                responses:
                  200:
                    description: OK.
                    content:
                        application/json:
                            schema:
                                $ref: '#/components/schemas/DocstringRef'
                """,
                id="response",
            ),
        ],
    )
    def test_get_api_schema_collects_references_declared_in_a_docstring(
        self, app, docstring_schema, section, docstring
    ):
        """A reference written by hand must pull its component into the document, wherever it appears."""

        async def handler(request_data: types.RequestData) -> None:
            return None  # pragma: no cover

        handler.__doc__ = docstring
        app.add_route("/docstring/", handler, methods=["POST"])

        schema = app.schema.schema

        assert section in schema["paths"]["/docstring/"]["post"]
        assert "DocstringRef" in schema["components"]["schemas"]

    def test_get_api_schema_response_without_description(self, app):
        """A response description is optional, so an undocumented one is emitted without the field."""

        @app.route("/undocumented/", methods=["GET"])
        async def undocumented() -> None:
            """
            description: No response documented.
            """
            return None  # pragma: no cover

        response = app.schema.schema["paths"]["/undocumented/"]["get"]["responses"]["200"]

        assert "description" not in response


class TestCaseResponseAnnotations:
    """A handler may annotate its return with a response class instead of a schema."""

    @pytest.fixture(scope="function")
    def frame_schema(self, app):
        if app.schema.schema_library.name == "pydantic":
            return pydantic.create_model("StreamFrame", token=(str, ...), __module__="pydantic.main")

        if app.schema.schema_library.name == "typesystem":
            return typesystem.Schema(title="StreamFrame", fields={"token": typesystem.fields.String()})

        if app.schema.schema_library.name == "marshmallow":
            return type("StreamFrame", (marshmallow.Schema,), {"token": marshmallow.fields.String()})

        raise ValueError(f"Wrong schema lib: {app.schema.schema_library.name}")

    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app, frame_schema):
        @app.route("/html/", methods=["GET"])
        async def html() -> HTMLResponse:
            """
            description: A page.
            responses:
              200:
                description: Markup.
            """
            return HTMLResponse("<p/>")  # pragma: no cover

        @app.route("/sse/", methods=["GET"])
        async def sse() -> ServerSentEventResponse:
            """
            description: An undocumented stream.
            responses:
              200:
                description: Events.
            """
            return ServerSentEventResponse(iter([]))  # pragma: no cover

        @app.route("/ndjson/", methods=["GET"])
        async def ndjson() -> NDJSONResponse[frame_schema]:  # ty: ignore[invalid-type-form]
            """
            description: A documented stream.
            responses:
              200:
                description: Frames.
            """
            return NDJSONResponse(iter([]))  # pragma: no cover

        @app.route("/unusable/", methods=["GET"])
        async def unusable() -> NDJSONResponse[int]:
            """
            description: A stream parametrised with something that is not a schema.
            responses:
              200:
                description: Frames.
            """
            return NDJSONResponse(iter([]))  # pragma: no cover

        @app.route("/json/", methods=["GET"])
        async def json_body() -> JSONResponse[frame_schema]:  # ty: ignore[invalid-type-form]
            """
            description: A documented body.
            responses:
              200:
                description: A document.
            """
            return JSONResponse({})  # pragma: no cover

    @pytest.mark.parametrize(
        ["path", "media_type"],
        [
            pytest.param("/html/", "text/html", id="buffered_response"),
            pytest.param("/sse/", "text/event-stream", id="streaming_response"),
            # A type argument that no schema library recognises leaves the payload undescribed.
            pytest.param("/unusable/", "application/x-ndjson", id="frame_argument_is_not_a_schema"),
        ],
    )
    def test_response_declares_only_its_media_type(self, app, path, media_type):
        content = app.schema.schema["paths"][path]["get"]["responses"]["200"]["content"]

        assert content == {media_type: {}}

    @pytest.mark.parametrize(
        ["path", "media_type", "key", "unexpected"],
        [
            # A sequential payload is described item by item, a buffered one as a whole.
            pytest.param("/ndjson/", "application/x-ndjson", "itemSchema", "schema", id="streaming_uses_item_schema"),
            pytest.param("/json/", "application/json", "schema", "itemSchema", id="buffered_uses_schema"),
        ],
    )
    def test_parametrised_response_declares_its_payload(self, app, path, media_type, key, unexpected):
        schema = app.schema.schema
        content = schema["paths"][path]["get"]["responses"]["200"]["content"][media_type]

        assert unexpected not in content
        reference = content[key]["$ref"]
        assert reference.rsplit(".", 1)[-1] == "StreamFrame"

        # A reference is only useful if the component it points at was collected into the document.
        assert reference.rsplit("/", 1)[-1] in schema["components"]["schemas"]
