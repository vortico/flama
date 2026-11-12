import inspect
import typing as t
from unittest.mock import AsyncMock, MagicMock, call, patch

import marshmallow
import pydantic
import pytest

from flama import endpoints, exceptions, types
from flama.applications import Flama
from flama.http.requests.http import Request
from flama.http.responses.api import APIResponse
from flama.http.responses.ndjson import NDJSONResponse
from flama.http.responses.plain_text import PlainTextResponse
from flama.http.responses.sse import ServerSentEventResponse
from flama.routing.routes._base import BaseRoute
from flama.routing.routes.http import BaseHTTPEndpointWrapper, HTTPEndpointWrapper, HTTPFunctionWrapper, Route


class TestCaseBaseHTTPEndpointWrapper:
    @pytest.fixture(scope="function")
    def handler(self, request):
        async def foo():
            return {"foo": "bar"}

        return foo

    @pytest.fixture(scope="function")
    def wrapper_cls(self):
        class _Wrapper(BaseHTTPEndpointWrapper):
            async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None: ...

        return _Wrapper

    @pytest.fixture(scope="function")
    def endpoint(self, handler, wrapper_cls):
        return wrapper_cls(handler)

    @pytest.fixture(scope="function")
    def output_schema(self, app):
        if app.schema.schema_library.name == "pydantic":
            return pydantic.create_model("OutputSchema", name=(str, ...))

        return type("OutputSchema", (marshmallow.Schema,), {"name": marshmallow.fields.String()})

    @pytest.mark.parametrize(
        ["annotation", "result", "exception"],
        [
            pytest.param(inspect.Signature.empty, None, None, id="unannotated"),
            pytest.param(t.Any, None, None, id="any"),
            pytest.param(None, None, None, id="none"),
            pytest.param("schema", "schema", None, id="schema"),
            pytest.param("schema_list", "schema", None, id="schema_list"),
            pytest.param(PlainTextResponse, None, None, id="response"),
            pytest.param("schema_response", "schema", None, id="schema_response"),
            # A response's type argument that names no schema leaves its payload undescribed.
            pytest.param(NDJSONResponse[int], None, None, id="response_of_no_schema"),
            pytest.param(APIResponse | ServerSentEventResponse, None, None, id="union_of_responses"),
            pytest.param(
                dict,
                None,
                exceptions.ApplicationError(
                    "Route 'TestCaseBaseHTTPEndpointWrapper.handler.<locals>.foo' returns 'dict', but a route returns "
                    "a schema, a response, or None, or has no return annotation"
                ),
                id="dict",
            ),
            pytest.param(list[str], None, exceptions.ApplicationError("returns 'list[str]'"), id="list"),
            pytest.param(int, None, exceptions.ApplicationError("returns 'int'"), id="primitive"),
            pytest.param("optional_schema", None, exceptions.ApplicationError("but a route returns"), id="optional"),
            pytest.param(
                APIResponse | None, None, exceptions.ApplicationError("but a route returns"), id="optional_response"
            ),
        ],
        indirect=["exception"],
    )
    def test_output_schema(self, endpoint, handler, output_schema, annotation, result, exception):
        annotation = {
            "schema": types.Schema[output_schema],
            "schema_list": types.SchemaList[output_schema],
            "schema_response": APIResponse[output_schema],
            "optional_schema": types.Schema[output_schema] | None,
        }.get(annotation, annotation)

        with exception:
            schema = endpoint._output_schema(handler, inspect.Signature(return_annotation=annotation))

            assert schema is (output_schema if result == "schema" else None)

    @pytest.mark.parametrize(
        ["response", "result", "exception"],
        [
            pytest.param({"foo": "bar"}, APIResponse({"foo": "bar"}), None, id="dict"),
            pytest.param(["foo"], APIResponse(["foo"]), None, id="list"),
            pytest.param(PlainTextResponse("foo"), PlainTextResponse("foo"), None, id="response"),
            pytest.param(None, APIResponse(""), None, id="none"),
            pytest.param(
                "foo",
                None,
                exceptions.SerializationError(
                    detail="Route returned a 'str', but a route returns a response, a mapping, a list, or None"
                ),
                id="str",
            ),
            pytest.param(b"foo", None, exceptions.SerializationError(detail="Route returned a 'bytes'"), id="bytes"),
            pytest.param(1, None, exceptions.SerializationError(detail="Route returned a 'int'"), id="int"),
        ],
        indirect=["exception"],
    )
    def test_build_api_response(self, endpoint, response, result, exception):
        with exception:
            assert endpoint._build_api_response(response, None) == result

    @pytest.mark.parametrize(
        ["own_schema", "expected"],
        [
            pytest.param(None, "handler", id="without_schema"),
            pytest.param("own", "own", id="with_schema"),
        ],
    )
    def test_build_api_response_schema(self, endpoint, own_schema, expected):
        response = MagicMock(spec=APIResponse, schema=own_schema)

        assert endpoint._build_api_response(response, "handler") is response
        assert response.schema == expected


class TestCaseHTTPFunctionWrapper:
    @pytest.fixture(scope="function")
    def app(self):
        app = MagicMock(spec=Flama)
        app.router = MagicMock(resolve_route=MagicMock(side_effect=lambda x: (AsyncMock(), x)))
        app.injector = MagicMock(inject=AsyncMock(side_effect=lambda x, y: x))
        return app

    @pytest.fixture(scope="function")
    def endpoint(self):
        async def foo():
            return {"foo": "bar"}

        return HTTPFunctionWrapper(foo, signature=inspect.signature(foo))

    async def test_call(self, app, endpoint):
        scope, receive, send = (
            types.Scope({"app": app, "path": "/", "root_app": app, "type": "http", "method": "GET"}),
            AsyncMock(),
            AsyncMock(),
        )

        await endpoint(scope, receive, send)

        assert receive.call_args_list == []
        assert send.call_args_list == [
            call(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"content-length", b"13"), (b"content-type", b"application/json")],
                }
            ),
            call({"type": "http.response.body", "body": b'{"foo":"bar"}'}),
        ]

    @pytest.mark.parametrize(
        ["failing"],
        [
            pytest.param(False, id="handler_succeeds"),
            pytest.param(True, id="handler_raises"),
        ],
    )
    async def test_call_closes_request(self, app, failing):
        async def foo():
            if failing:
                raise ValueError("handler failed")
            return {"foo": "bar"}

        endpoint = HTTPFunctionWrapper(foo, signature=inspect.signature(foo))
        scope, receive, send = (
            types.Scope({"app": app, "path": "/", "root_app": app, "type": "http", "method": "GET"}),
            AsyncMock(),
            AsyncMock(),
        )

        with patch.object(Request, "close", new_callable=AsyncMock) as close:
            if failing:
                with pytest.raises(ValueError, match="handler failed"):
                    await endpoint(scope, receive, send)
            else:
                await endpoint(scope, receive, send)

        assert close.await_count == 1


class TestCaseHTTPEndpointWrapper:
    @pytest.fixture(scope="function")
    def app(self):
        app = MagicMock(spec=Flama)
        app.router = MagicMock(resolve_route=MagicMock(side_effect=lambda x: (AsyncMock(), x)))
        app.injector = MagicMock(inject=AsyncMock(side_effect=lambda x, y: x))
        return app

    @pytest.fixture(scope="function")
    def endpoint(self):
        class Endpoint(endpoints.HTTPEndpoint):
            async def get(self):
                return {"foo": "bar"}

        return HTTPEndpointWrapper(Endpoint)

    @pytest.mark.parametrize(
        ["base", "schemas"],
        [
            pytest.param(endpoints.HTTPEndpoint, {"GET": int, "HEAD": int, "POST": str}, id="http"),
            # A JSON-RPC method's result is always sent within a JSON-RPC response.
            pytest.param(endpoints.JSONRPCEndpoint, {}, id="jsonrpc"),
        ],
    )
    def test_schemas(self, base, schemas):
        class Endpoint(base):
            handlers = {"items/get": "get", "items/post": "post"}

            async def get(self) -> int: ...

            async def post(self) -> str: ...

        with patch.object(
            HTTPEndpointWrapper, "_output_schema", side_effect=lambda handler, signature: signature.return_annotation
        ):
            wrapper = HTTPEndpointWrapper(Endpoint)

        assert wrapper.schemas == schemas

    async def test_call(self, app, endpoint):
        scope, receive, send = (
            types.Scope({"app": app, "path": "/", "root_app": app, "type": "http", "method": "GET"}),
            AsyncMock(),
            AsyncMock(),
        )

        await endpoint(scope, receive, send)

        assert receive.call_args_list == []
        assert send.call_args_list == [
            call(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"content-length", b"13"), (b"content-type", b"application/json")],
                }
            ),
            call({"type": "http.response.body", "body": b'{"foo":"bar"}'}),
        ]

    @pytest.mark.parametrize(
        ["failing"],
        [
            pytest.param(False, id="handler_succeeds"),
            pytest.param(True, id="handler_raises"),
        ],
    )
    async def test_call_closes_request(self, app, failing):
        class Endpoint(endpoints.HTTPEndpoint):
            async def get(self):
                if failing:
                    raise ValueError("handler failed")
                return {"foo": "bar"}

        endpoint = HTTPEndpointWrapper(Endpoint)
        scope, receive, send = (
            types.Scope({"app": app, "path": "/", "root_app": app, "type": "http", "method": "GET"}),
            AsyncMock(),
            AsyncMock(),
        )

        with patch.object(Request, "close", new_callable=AsyncMock) as close:
            if failing:
                with pytest.raises(ValueError, match="handler failed"):
                    await endpoint(scope, receive, send)
            else:
                await endpoint(scope, receive, send)

        assert close.await_count == 1


class TestCaseRoute:
    @pytest.fixture(scope="function")
    def route(self):
        return Route("/", lambda: None, name="foo", include_in_schema=False)

    @pytest.fixture(scope="function")
    def endpoint(self, request):
        if request.param == "function":

            def foo(): ...

            return foo

        elif request.param == "endpoint":

            class FooEndpoint(endpoints.HTTPEndpoint):
                def get(self): ...

                def post(self): ...

            return FooEndpoint
        elif request.param is None:
            return None
        else:
            raise ValueError("Wrong value")

    @pytest.mark.parametrize(
        ["endpoint", "name", "wrapper", "methods", "expected_methods", "exception"],
        (
            pytest.param(
                "function",
                "foo",
                HTTPFunctionWrapper,
                {"GET", "POST"},
                {"GET", "POST", "HEAD"},
                None,
                id="function_explicit_methods",
            ),
            pytest.param(
                "function",
                "foo",
                HTTPFunctionWrapper,
                {"POST"},
                {"POST"},
                None,
                id="function_no_get_method",
            ),
            pytest.param(
                "function",
                "foo",
                HTTPFunctionWrapper,
                None,
                {"GET", "HEAD"},
                None,
                id="function_no_methods",
            ),
            pytest.param(
                "endpoint",
                "FooEndpoint",
                HTTPEndpointWrapper,
                {"GET", "POST"},
                {"GET", "POST", "HEAD"},
                None,
                id="endpoint_explicit_methods",
            ),
            pytest.param(
                "endpoint",
                "FooEndpoint",
                HTTPEndpointWrapper,
                {"POST"},
                {"POST"},
                None,
                id="endpoint_no_get_method",
            ),
            pytest.param(
                "endpoint",
                "FooEndpoint",
                HTTPEndpointWrapper,
                None,
                {"GET", "POST", "HEAD"},
                None,
                id="endpoint_no_methods",
            ),
            pytest.param(
                None,
                None,
                None,
                None,
                None,
                exceptions.ApplicationError("Endpoint must be a callable or an HTTPEndpoint subclass"),
                id="error_handler",
            ),
        ),
        indirect=["endpoint", "exception"],
    )
    def test_init(self, endpoint, name, wrapper, methods, expected_methods, exception):
        with exception:
            route = Route("/", endpoint, methods=methods, include_in_schema=False)

            assert route.path == "/"
            assert isinstance(route.app, wrapper)
            assert route.endpoint == endpoint
            assert route.name == name
            assert route.include_in_schema is False
            assert route.methods == expected_methods

    @pytest.mark.parametrize(
        ["scope_type", "handle_call"],
        (
            pytest.param("http", True, id="http"),
            pytest.param("wrong", False, id="wrong"),
        ),
    )
    async def test_call(self, route, asgi_scope, asgi_receive, asgi_send, scope_type, handle_call):
        scope = types.Scope({**asgi_scope, "type": scope_type})
        route_scope = types.Scope({"foo": "bar"})
        handle = AsyncMock()
        expected_calls = [call(types.Scope({**scope, **route_scope}), asgi_receive, asgi_send)] if handle_call else []

        with patch.object(route, "handle", new=handle), patch.object(route, "route_scope", return_value=route_scope):
            await route(scope, asgi_receive, asgi_send)

        assert handle.call_args_list == expected_calls

    def test_eq(self):
        def foo(): ...

        assert Route("/", foo, methods={"GET"}) == Route("/", foo, methods={"GET"})
        assert Route("/", foo, methods={"GET"}) != Route("/", foo, methods={"POST"})

    def test_repr(self):
        def foo(): ...

        assert repr(Route("/", foo)) == "Route(path='/', name='foo', methods=['GET', 'HEAD'])"

    @pytest.mark.parametrize(
        ["endpoint", "result"],
        (
            pytest.param("function", False, id="function"),
            pytest.param("endpoint", True, id="endpoint"),
        ),
        indirect=["endpoint"],
    )
    def test_is_endpoint(self, endpoint, result):
        assert Route.is_endpoint(endpoint) is result

    @pytest.mark.parametrize(
        ["endpoint", "methods", "expected_methods"],
        (
            pytest.param("function", {"GET"}, {"GET", "HEAD"}, id="function_explicit_methods"),
            pytest.param("function", None, {"GET", "HEAD"}, id="function_no_methods"),
            pytest.param("function", {"POST"}, {"POST"}, id="function_no_get_method"),
            pytest.param("endpoint", {"GET"}, {"GET", "HEAD"}, id="endpoint_explicit_methods"),
            pytest.param("endpoint", None, {"GET", "HEAD", "POST"}, id="endpoint_no_methods"),
            pytest.param("function", {"POST"}, {"POST"}, id="endpoint_no_get_method"),
        ),
        indirect=["endpoint"],
    )
    def test_endpoint_handlers(self, endpoint, methods, expected_methods):
        result = {m: getattr(endpoint, m.lower() if m != "HEAD" else "get", endpoint) for m in expected_methods}

        route = Route("/", endpoint, methods=methods)

        assert route.endpoint_handlers() == result

    @pytest.mark.parametrize(
        ["scope_type", "scope_method", "path_match_return", "result"],
        (
            pytest.param("http", "GET", BaseRoute.Match.full, BaseRoute.Match.full, id="match"),
            pytest.param("http", "POST", BaseRoute.Match.full, BaseRoute.Match.partial, id="partial"),
            pytest.param("http", "GET", BaseRoute.Match.none, BaseRoute.Match.none, id="no_match"),
            pytest.param("websocket", "GET", None, BaseRoute.Match.none, id="wrong_scope_type"),
        ),
    )
    def test_match(self, scope_type, scope_method, path_match_return, result, asgi_scope):
        def foo(): ...

        route = Route("/", foo, methods={"GET"})

        asgi_scope["type"] = scope_type
        asgi_scope["method"] = scope_method

        with patch.object(BaseRoute, "match", return_value=path_match_return):
            assert route.match(asgi_scope) == result


@pytest.mark.parametrize(
    ["path"],
    [
        pytest.param("/search/", id="function_handler"),
        pytest.param("/endpoint/", id="endpoint_handler"),
    ],
)
class TestCaseQueryMethod:
    """`QUERY` is safe and idempotent like `GET`, but carries a request body."""

    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.query("/search/")
        async def search(request_data: types.RequestData):
            """
            description: Search with a structured body.
            responses:
              200:
                description: Matches.
            """
            return {"criteria": request_data.data}

        @app.route("/endpoint/", methods=["QUERY"])
        class SearchEndpoint(endpoints.HTTPEndpoint):
            async def query(self, request_data: types.RequestData):
                """
                description: Search from an endpoint.
                responses:
                  200:
                    description: Matches.
                """
                return {"criteria": request_data.data}

    async def test_request_carries_a_body(self, client, path):
        response = await client.request("QUERY", path, json={"name": "puppy", "limit": 5})

        assert response.status_code == 200, response.text
        assert response.json() == {"criteria": {"name": "puppy", "limit": 5}}

    async def test_other_methods_are_rejected(self, client, path):
        response = await client.get(path)

        assert response.status_code == 405

    def test_operation_is_documented_under_query(self, app, path):
        assert list(app.schema.schema["paths"][path]) == ["query"]
