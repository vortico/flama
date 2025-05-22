import typing as t
from unittest.mock import AsyncMock, MagicMock, call, patch

import marshmallow
import pydantic
import pytest
import typesystem
import typesystem.fields

from flama import Component, Flama, endpoints, schemas, types


class Puppy:
    name = "Canna"


class PuppyComponent(Component):
    def resolve(self) -> Puppy:
        return Puppy()


class TestCaseHTTPEndpoint:
    @pytest.fixture(scope="class")
    def app(self, app):
        return Flama(schema=None, docs=None, components=[PuppyComponent()])

    @pytest.fixture
    def endpoint(self, app, asgi_scope, asgi_receive, asgi_send):
        @app.route("/")
        class FooEndpoint(endpoints.HTTPEndpoint):
            def get(self): ...

        asgi_scope["app"] = app
        asgi_scope["root_app"] = app
        asgi_scope["type"] = "http"
        return FooEndpoint(asgi_scope, asgi_receive, asgi_send)

    @pytest.fixture(scope="class")
    def puppy_schema(self, app):
        if app.schema.schema_library.lib == pydantic:
            schema = pydantic.create_model("Puppy", name=(str, ...))
        elif app.schema.schema_library.lib == typesystem:
            schema = typesystem.Schema(title="Puppy", fields={"name": typesystem.fields.String()})
        elif app.schema.schema_library.lib == marshmallow:
            schema = type("Puppy", (marshmallow.Schema,), {"name": marshmallow.fields.String()})
        else:
            raise ValueError("Wrong schema lib")

        return schema

    @pytest.fixture(scope="class")
    def puppy_endpoint(self, app, puppy_schema):
        @app.route("/puppy/")
        class PuppyEndpoint(endpoints.HTTPEndpoint):
            def get(self, puppy: Puppy) -> t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(puppy_schema)]:
                return {"name": puppy.name}

            async def post(
                self, puppy: t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(puppy_schema)]
            ) -> t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(puppy_schema)]:
                return puppy

        return PuppyEndpoint

    @pytest.mark.parametrize(
        ["method", "params", "status_code", "expected_response"],
        (
            pytest.param("get", {}, 200, {"name": "Canna"}, id="get"),
            pytest.param("post", {"json": {"name": "Canna"}}, 200, {"name": "Canna"}, id="post"),
            pytest.param(
                "patch",
                {},
                405,
                {"detail": "Method Not Allowed", "error": "HTTPException", "status_code": 405},
                id="method_not_allowed",
            ),
        ),
    )
    async def test_request(self, app, client, puppy_endpoint, method, params, status_code, expected_response):
        response = await client.request(method, "/puppy/", **params)

        assert response.status_code == status_code
        assert response.json() == expected_response

    def test_init(self, app, asgi_scope, asgi_receive, asgi_send):
        with patch("flama.http.Request") as request_mock:

            class FooEndpoint(endpoints.HTTPEndpoint):
                def get(self): ...

            route = app.add_route("/", FooEndpoint)
            asgi_scope = types.Scope(
                {
                    **asgi_scope,
                    "app": app,
                    "root_app": app,
                    "type": "http",
                    "method": "GET",
                    "path": "/",
                    "path_params": {},
                    "endpoint": FooEndpoint,
                    "route": route,
                }
            )
            endpoint = endpoints.HTTPEndpoint(asgi_scope, asgi_receive, asgi_send)
            assert endpoint.state == {
                "scope": asgi_scope,
                "receive": asgi_receive,
                "send": asgi_send,
                "exc": None,
                "app": app,
                "route": route,
                "request": request_mock(),
            }

    def test_allowed_methods(self, endpoint):
        assert endpoint.allowed_methods() == {"GET", "HEAD"}

        class BarEndpoint(endpoints.HTTPEndpoint):
            def post(self): ...

        assert BarEndpoint.allowed_methods() == {"POST"}

    def test_handler(self, endpoint):
        endpoint.state["request"].scope["method"] = "GET"
        assert endpoint.handler == endpoint.get

    async def test_dispatch(self, app, endpoint):
        injected_mock = MagicMock()
        app.injector.inject = AsyncMock(return_value=injected_mock)
        with patch("flama.concurrency.run") as run_mock:
            await endpoint.dispatch()

            assert app.injector.inject.call_args_list == [call(endpoint.get, endpoint.state)]
            assert run_mock.call_args_list == [call(injected_mock)]
