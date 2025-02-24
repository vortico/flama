from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from flama import endpoints, exceptions, http, types
from flama.applications import Flama
from flama.routing.routes.base import BaseRoute
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

    @pytest.mark.parametrize(
        ["response", "result"],
        [
            pytest.param({"foo": "bar"}, http.APIResponse(content={"foo": "bar"}), id="dict"),
            pytest.param(["foo"], http.APIResponse(content=["foo"]), id="list"),
            pytest.param("foo", http.APIResponse(content="foo"), id="str"),
            pytest.param(b"foo", http.APIResponse(content=b"foo"), id="bytes"),
            pytest.param(http.Response(content=b"foo"), http.Response(content=b"foo"), id="response"),
            pytest.param(None, http.APIResponse(content=""), id="none"),
        ],
    )
    def test_build_api_response(self, endpoint, response, result):
        assert endpoint._build_api_response(response) == result


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

        return HTTPFunctionWrapper(foo)

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
