import dataclasses

import pytest

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
)


class TestCaseOpenAPISpec:
    @pytest.fixture
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

    @pytest.fixture
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

    @pytest.fixture
    def example(self, fake):
        return Example(summary=fake.sentence(), description=fake.text(), value={})

    @pytest.fixture
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

    @pytest.fixture
    def server_variable(self, fake):
        return ServerVariable(enum=fake.pylist(value_types=[str]), default=fake.word(), description=fake.sentence())

    @pytest.fixture
    def server(self, fake, server_variable):
        return Server(url=fake.url(), variables={"var": server_variable}, description=fake.sentence())

    @pytest.fixture
    def link(self, fake, server):
        return Link(
            operationId=fake.word(),
            parameters=fake.pydict(value_types=[str]),
            requestBody={},
            description=fake.sentence(),
            server=server,
        )

    @pytest.fixture
    def encoding(self, fake, header):
        return Encoding(
            contentType="",
            headers={"header": header},
            style=fake.word(),
            explode=fake.pybool(),
            allowReserved=fake.pybool(),
        )

    @pytest.fixture
    def media_type(self, fake, schema, example, encoding):
        return MediaType(schema=schema, example=example, encoding={"enc": encoding})

    @pytest.fixture
    def response(self, header, media_type, link):
        return Response(
            description="Foo",
            headers={"header": header},
            content={"content": media_type},
            links={"link": link},
        )

    @pytest.fixture
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

    @pytest.fixture
    def request_body(self, fake, media_type):
        return RequestBody(content=media_type, description=fake.sentence(), required=fake.pybool())

    @pytest.fixture
    def security(self, fake):
        return Security({fake.word(): fake.pylist(value_types=[str])})

    @pytest.fixture
    def external_docs(self, fake):
        return ExternalDocs(url=fake.url(), description=fake.sentence())

    @pytest.fixture
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

    @pytest.fixture
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
            servers=[server],
            parameters=[parameter],
        )

    @pytest.fixture
    def callback(self, fake, path):
        return Callback({fake.word(): path})

    @pytest.mark.parametrize(
        ["spec", "result"],
        [
            pytest.param(
                {"info": {"title": "Title", "version": "1.0.0"}},
                {
                    "openapi": "3.1.0",
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
                    "openapi": "3.1.0",
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
