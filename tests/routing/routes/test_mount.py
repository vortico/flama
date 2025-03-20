from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from flama import exceptions, types, url
from flama.applications import Flama
from flama.routing.router import Router
from flama.routing.routes.base import BaseRoute
from flama.routing.routes.http import Route
from flama.routing.routes.mount import Mount


class TestCaseMount:
    @pytest.fixture(scope="function")
    def app(self):
        return Flama(schema=None, docs=None)

    @pytest.fixture(scope="function")
    def mount(self, app):
        return Mount("/foo/{x:int}/", app, name="foo")

    @pytest.mark.parametrize(
        ["app", "routes", "exception"],
        (
            pytest.param(
                MagicMock(spec=Flama),
                None,
                None,
                id="app",
            ),
            pytest.param(
                None,
                [MagicMock(spec=Route)],
                None,
                id="routes",
            ),
            pytest.param(
                None,
                None,
                exceptions.ApplicationError("Either 'path' and 'app' or 'mount' variables are needed"),
                id="wrong",
            ),
        ),
        indirect=["exception"],
    )
    def test_init(self, app, routes, exception):
        with exception:
            mount = Mount("/foo/", app, routes=routes)

            if app is None and routes:
                app = Router(routes=routes)

            assert mount.app == app
            assert mount.path == "/foo/"

    @pytest.mark.parametrize(
        ["scope_type", "handle_call"],
        (
            pytest.param("http", True, id="http"),
            pytest.param("websocket", True, id="websocket"),
            pytest.param("lifespan", True, id="lifespan"),
            pytest.param("wrong", False, id="wrong"),
        ),
    )
    async def test_call(self, scope_type, handle_call, mount, asgi_scope, asgi_receive, asgi_send):
        scope = types.Scope({**asgi_scope, "type": scope_type})
        route_scope = types.Scope({"foo": "bar"})
        handle = AsyncMock()
        expected_calls = [call(types.Scope({**scope, **route_scope}), asgi_receive, asgi_send)] if handle_call else []

        with patch.object(mount, "handle", new=handle), patch.object(mount, "route_scope", return_value=route_scope):
            await mount(scope, asgi_receive, asgi_send)

        assert handle.call_args_list == expected_calls

    def test_eq(self, app):
        assert Mount("/", app, name="app_mock") == Mount("/", app, name="app_mock")
        assert Mount("/", app, name="app_mock") != Mount("/", app, name="bar")

    @pytest.mark.parametrize(
        ["app", "used"],
        (
            pytest.param(MagicMock(spec=Router), False, id="router"),
            pytest.param(MagicMock(spec=Flama, router=MagicMock(spec=Router, components=[])), True, id="app"),
        ),
    )
    def test_build(self, mount, app, used):
        root_app = MagicMock(spec=Flama)
        expected_calls = [call(app)] if used else [call(root_app)]

        route = MagicMock(spec=Route)
        mount.app = app
        mount.app.routes = [route]

        mount.build(root_app)

        assert route.build.call_args_list == expected_calls

    @pytest.mark.parametrize(
        ["scope_type", "path_match_return", "result"],
        (
            pytest.param("http", MagicMock(match=url.Path.Match.exact), BaseRoute.Match.full, id="match_exact-http"),
            pytest.param(
                "http", MagicMock(match=url.Path.Match.partial), BaseRoute.Match.full, id="match_partial-http"
            ),
            pytest.param("http", MagicMock(match=url.Path.Match.none), BaseRoute.Match.none, id="no_match-http"),
            pytest.param(
                "websocket", MagicMock(match=url.Path.Match.exact), BaseRoute.Match.full, id="match_exact-websocket"
            ),
            pytest.param(
                "websocket", MagicMock(match=url.Path.Match.partial), BaseRoute.Match.full, id="match_partial-websocket"
            ),
            pytest.param(
                "websocket", MagicMock(match=url.Path.Match.none), BaseRoute.Match.none, id="no_match-websocket"
            ),
            pytest.param("wrong", None, BaseRoute.Match.none, id="wrong_scope_type"),
        ),
    )
    def test_match(self, scope_type, path_match_return, result, asgi_scope, mount):
        asgi_scope["type"] = scope_type

        with patch.object(mount.path, "match", return_value=path_match_return):
            assert mount.match(asgi_scope) == result

    async def test_handle(self, mount, asgi_scope, asgi_receive, asgi_send):
        app = AsyncMock(spec=Flama)
        mount = Mount("/", app)

        await mount.handle(asgi_scope, asgi_receive, asgi_send)

        assert app.call_args_list == [call(asgi_scope, asgi_receive, asgi_send)]

    @pytest.mark.parametrize(
        ["app", "used"],
        (
            pytest.param(Router(), False, id="router"),
            pytest.param(Flama(docs=None, schema=None), True, id="app"),
        ),
    )
    def test_route_scope(self, mount, asgi_scope, app, used):
        def bar(): ...

        mount.app = app
        mount.app.add_route("/bar", bar)

        asgi_scope["path"] = "/foo/1/bar"
        route_scope = mount.route_scope(asgi_scope)

        assert route_scope == {
            "app": app if used else asgi_scope["app"],
            "path": "/bar",
            "root_path": "" if used else "/foo/1/",
        }

    @pytest.mark.parametrize(
        ["name", "params", "expected_url", "exception"],
        (
            pytest.param(
                "foo", {"x": 1, "path": "/foo"}, url.URL(scheme="http", path="/foo/1/"), None, id="match_full_name"
            ),
            pytest.param("foo:bar", {"x": 1}, url.URL(scheme="http", path="/foo/1/bar"), None, id="match_route"),
            pytest.param(
                "foo:nested",
                {"x": 1, "path": "/foo/"},
                url.URL(scheme="http", path="/foo/1/nested"),
                None,
                id="match_nested_app",
            ),
            pytest.param(
                "wrong",
                {"x": 1},
                None,
                exceptions.NotFoundException(params={"x": 1}, name="wrong"),
                id="not_found_mount",
            ),
            pytest.param(
                "foo:wrong",
                {"x": 1},
                None,
                exceptions.NotFoundException(params={"x": 1}, name="foo:wrong"),
                id="not_found_route",
            ),
        ),
        indirect=["exception"],
    )
    def test_resolve_url(self, name, params, expected_url, exception, mount):
        mount.app.add_route("/bar", MagicMock(), name="bar")
        mount.app.mount("/nested", MagicMock(), name="nested")

        with exception:
            assert mount.resolve_url(name, **params) == expected_url

    def test_routes(self, mount):
        route = MagicMock(spec=Route)

        mount.app = MagicMock(spec=Flama)
        mount.app.routes = [route]

        assert mount.routes == [route]
