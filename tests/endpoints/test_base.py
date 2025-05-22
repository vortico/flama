import typing as t
from unittest.mock import MagicMock, call, patch

import pytest

from flama import Flama, endpoints, types


class TestCaseBaseEndpoint:
    @pytest.fixture(scope="function")
    def app(self, route):
        app = MagicMock(spec=Flama)
        app.router = MagicMock(resolve_route=MagicMock(side_effect=lambda x: (route, x)))
        return app

    @pytest.fixture(scope="function")
    def route(self):
        return MagicMock()

    @pytest.fixture
    def endpoint(self):
        class _Endpoint(endpoints.BaseEndpoint):
            @classmethod
            def allowed_handlers(cls) -> dict[str, t.Callable]: ...

            async def dispatch(self) -> None: ...

        return _Endpoint

    def test_init(self, endpoint, app, route, asgi_scope, asgi_receive, asgi_send):
        asgi_scope = types.Scope(
            {
                **asgi_scope,
                "app": app,
                "root_app": app,
                "type": "http",
                "method": "GET",
                "path": "/",
                "path_params": {},
                "endpoint": endpoint,
                "route": route,
            }
        )
        e = endpoint(asgi_scope, asgi_receive, asgi_send)
        assert e.state == {
            "scope": asgi_scope,
            "receive": asgi_receive,
            "send": asgi_send,
            "exc": None,
            "app": app,
            "route": route,
        }

    def test_await(self, endpoint, app, route, asgi_scope, asgi_receive, asgi_send):
        e = endpoint(
            types.Scope(
                {
                    **asgi_scope,
                    "app": app,
                    "root_app": app,
                    "type": "http",
                    "method": "GET",
                    "path": "/",
                    "path_params": {},
                    "endpoint": endpoint,
                    "route": route,
                }
            ),
            asgi_receive,
            asgi_send,
        )

        with patch.object(e, "dispatch"):
            e.__await__()

            assert e.dispatch.call_args_list == [call()]
