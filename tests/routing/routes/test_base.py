import functools
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from flama import exceptions, routing, types
from flama.applications import Flama
from flama.url import Path


class TestCaseBaseEndpointWrapper:
    @pytest.fixture(scope="function")
    def wrapper_cls(self):
        class _Wrapper(routing.BaseEndpointWrapper):
            async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None: ...

        return _Wrapper

    @pytest.fixture(scope="function")
    def handler(self):
        async def foo(): ...

        return foo

    @pytest.fixture(scope="function")
    def endpoint(self, wrapper_cls, handler):
        return wrapper_cls(handler)

    @pytest.mark.parametrize(
        ["pagination", "exception"],
        [
            pytest.param(None, None, id="ok"),
            pytest.param("wrong", KeyError("wrong"), id="wrong_pagination"),
        ],
        indirect=["exception"],
    )
    def test_init(self, wrapper_cls, handler, pagination, exception):
        with exception:
            endpoint = wrapper_cls(handler, pagination=pagination)

            assert endpoint.handler == handler

    def test_get(self, endpoint):
        endpoint_ = endpoint

        class Foo:
            endpoint = endpoint_

        assert isinstance(Foo.endpoint, functools.partial)

    def test_eq(self, wrapper_cls, handler):
        async def bar(): ...

        endpoint = wrapper_cls(handler)
        endpoint_foo = wrapper_cls(handler)
        endpoint_bar = wrapper_cls(bar)

        assert endpoint == endpoint_foo
        assert endpoint != endpoint_bar
        assert endpoint_foo != endpoint_bar


class TestCaseBaseRoute:
    @pytest.fixture(scope="function")
    def wrapper_cls(self):
        class _Wrapper(routing.BaseEndpointWrapper):
            async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None: ...

        return _Wrapper

    @pytest.fixture(scope="function")
    def route_cls(self):
        class _Route(routing.BaseRoute):
            async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
                return await self.handle(scope, receive, send)

        return _Route

    @pytest.fixture(scope="function")
    def route(self, route_cls, wrapper_cls):
        return route_cls("/", wrapper_cls(lambda: None), name="foo", include_in_schema=False)

    def test_init(self, route_cls):
        def foo(): ...

        app = foo
        route = route_cls(
            "/",
            app,
            name="foo",
            include_in_schema=False,
            tags={"tag": "tag", "list_tag": ["foo", "bar"], "dict_tag": {"foo": "bar"}},
        )

        assert route.path == "/"
        assert route.app == app
        assert route.endpoint == foo
        assert route.name == "foo"
        assert route.include_in_schema is False
        assert route.tags == {"tag": "tag", "list_tag": ["foo", "bar"], "dict_tag": {"foo": "bar"}}

    def test_eq(self, route_cls):
        def foo(): ...

        assert route_cls("/", foo, name="foo") == route_cls("/", foo, name="foo")
        assert route_cls("/", foo, name="foo") != route_cls("/", foo, name="bar")

    def test_repr(self, route_cls):
        def foo(): ...

        assert repr(route_cls("/", foo, name="foo")) == "_Route(path='/', name='foo')"

    @pytest.mark.parametrize(["app"], (pytest.param(MagicMock(spec=Flama), id="app"), pytest.param(None, id="no_app")))
    def test_build(self, app, route):
        expected_calls = [call(app)] if app else []
        with patch.object(route, "parameters") as parameters_mock:
            route.build(app)

        assert parameters_mock.build.call_args_list == expected_calls

    def test_endpoint_handlers(self, route):
        assert route.endpoint_handlers() == {}

    async def test_handle(self, route_cls, asgi_scope, asgi_receive, asgi_send):
        app = AsyncMock()
        route = route_cls("/", app)

        await route.handle(asgi_scope, asgi_receive, asgi_send)

        assert app.call_args_list == [call(asgi_scope, asgi_receive, asgi_send)]

    @pytest.mark.parametrize(
        ["path_match_return", "result"],
        (
            pytest.param(MagicMock(match=Path.Match.exact), routing.BaseRoute.Match.full, id="match"),
            pytest.param(MagicMock(match=Path.Match.none), routing.BaseRoute.Match.none, id="no_match"),
        ),
    )
    def test_match(self, path_match_return, result, route, asgi_scope):
        with patch.object(route.path, "match", return_value=path_match_return):
            assert route.match(asgi_scope) == result

    def test_route_scope(self, route, asgi_scope):
        assert route.route_scope(asgi_scope) == types.Scope({})

    @pytest.mark.parametrize(
        ["name", "params", "exception"],
        (
            pytest.param(
                "foo",
                {"bar": 1},
                None,
                id="found",
            ),
            pytest.param(
                "bar",
                {},
                exceptions.NotFoundException(name="bar"),
                id="not_found_wrong_name",
            ),
            pytest.param(
                "foo",
                {"wrong": 1},
                exceptions.NotFoundException(params={"wrong": 1}, name="foo"),
                id="not_found_wrong_params",
            ),
            pytest.param(
                "foo",
                {"bar": 1, "wrong": 1},
                exceptions.NotFoundException(params={"bar": 1, "wrong": 1}, name="foo"),
                id="error_remaining_params",
            ),
        ),
        indirect=["exception"],
    )
    def test_resolve_url(self, route_cls, name, params, exception):
        route = route_cls("/foo/{bar:int}", lambda bar: None, name="foo")

        with exception:
            assert route.resolve_url(name=name, **params)
