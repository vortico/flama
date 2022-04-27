import dataclasses

import pytest

from flama.schemas.openapi import (
    Callback,
    Contact,
    Encoding,
    Example,
    ExternalDocs,
    Header,
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
            title="Title",
            version="1.0.0",
            description="Description",
            terms_of_service="TOS",
            contact=Contact(name="Contact name", url="https://contact.com", email="contact@contact.com"),
            license=License(name="License name", url="https://license.com"),
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

    def test_init(self):
        assert OpenAPISpec(title="Title", version="1.0.0")
        assert OpenAPISpec(
            title="Title",
            version="1.0.0",
            description="Description",
            terms_of_service="TOS",
            contact=Contact(name="Contact name", url="Contact url", email="Contact email"),
            license=License(name="License name", url="License url"),
        )

    def test_asdict(self, spec):
        expected_result = {
            "openapi": "3.0.3",
            "info": {
                "title": "Title",
                "version": "1.0.0",
                "description": "Description",
                "termsOfService": "TOS",
                "contact": {"name": "Contact name", "url": "https://contact.com", "email": "contact@contact.com"},
                "license": {"name": "License name", "url": "https://license.com"},
            },
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
        }

        assert spec.asdict() == expected_result

    def test_add_path(self, spec, path):
        path_name = "foo"
        expected_result = spec.asdict()
        expected_result["paths"] = {"foo": spec.asdict(dataclasses.asdict(path))}

        spec.add_path(path_name, path)

        assert spec.asdict() == expected_result

    def test_add_schema(self, spec, schema):
        schema_name = "foo"
        expected_result = spec.asdict()
        expected_result["components"]["schemas"] = {schema_name: schema}

        spec.add_schema(schema_name, schema)

        assert spec.asdict() == expected_result

    def test_add_response(self, spec, response):
        response_name = "foo"
        expected_result = spec.asdict()
        expected_result["components"]["responses"] = {response_name: spec.asdict(dataclasses.asdict(response))}

        spec.add_response(response_name, response)

        assert spec.asdict() == expected_result

    def test_add_parameter(self, spec, parameter):
        parameter_name = "foo"
        expected_result = spec.asdict()
        expected_result["components"]["parameters"] = {parameter_name: spec.asdict(dataclasses.asdict(parameter))}

        spec.add_parameter(parameter_name, parameter)

        assert spec.asdict() == expected_result

    def test_add_example(self, spec, example):
        example_name = "foo"
        expected_result = spec.asdict()
        expected_result["components"]["examples"] = {example_name: spec.asdict(dataclasses.asdict(example))}

        spec.add_example(example_name, example)

        assert spec.asdict() == expected_result

    def test_add_request_body(self, spec, request_body):
        request_body_name = "foo"
        expected_result = spec.asdict()
        expected_result["components"]["requestBodies"] = {
            request_body_name: spec.asdict(dataclasses.asdict(request_body))
        }

        spec.add_request_body(request_body_name, request_body)

        assert spec.asdict() == expected_result

    def test_add_header(self, spec, header):
        header_name = "foo"
        expected_result = spec.asdict()
        expected_result["components"]["headers"] = {header_name: spec.asdict(dataclasses.asdict(header))}

        spec.add_header(header_name, header)

        assert spec.asdict() == expected_result

    def test_add_security(self, spec, security):
        security_name = "foo"
        expected_result = spec.asdict()
        expected_result["components"]["securitySchemes"] = {security_name: spec.asdict(security)}

        spec.add_security(security_name, security)

        assert spec.asdict() == expected_result

    def test_add_link(self, spec, link):
        link_name = "foo"
        expected_result = spec.asdict()
        expected_result["components"]["links"] = {link_name: spec.asdict(dataclasses.asdict(link))}

        spec.add_link(link_name, link)

        assert spec.asdict() == expected_result

    def test_add_callback(self, spec, callback):
        callback_name = "foo"
        expected_result = spec.asdict()
        expected_result["components"]["callbacks"] = {callback_name: spec.asdict(callback)}

        spec.add_callback(callback_name, callback)

        assert spec.asdict() == expected_result
