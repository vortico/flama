import pytest

from flama import endpoints, http, injection, websockets
from flama.applications import Flama
from flama.client import Client


class Puppy:
    name = "Canna"


class Owner:
    name = "Perdy"

    def __init__(self, puppy: Puppy):
        self.puppy = puppy


class Unknown:
    pass


class Foo:
    name = "Foo"


class TestCaseComponentsInjection:
    @pytest.fixture(scope="class")
    def puppy_component(self):
        class PuppyComponent(injection.Component):
            def resolve(self) -> Puppy:
                return Puppy()

        return PuppyComponent()

    @pytest.fixture(scope="class")
    def unknown_param_component(self):
        class UnknownParamComponent(injection.Component):
            def resolve(self, foo: Unknown) -> Foo:
                return Foo()

        return UnknownParamComponent()

    @pytest.fixture(scope="class")
    def owner_component(self):
        class OwnerComponent(injection.Component):
            def resolve(self, puppy: Puppy) -> Owner:
                return Owner(puppy=puppy)

        return OwnerComponent()

    @pytest.fixture(scope="function", autouse=True)
    def add_components(self, app, puppy_component, owner_component, unknown_param_component):
        for component in (puppy_component, owner_component, unknown_param_component):
            app.add_component(component)

    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.route("/http-view/")
        async def puppy_http_view(puppy: Puppy):
            return http.JSONResponse({"puppy": puppy.name})

        @app.route("/http-endpoint/", methods=["GET"])
        class PuppyHTTPEndpoint(endpoints.HTTPEndpoint):
            async def get(self, puppy: Puppy):
                return http.JSONResponse({"puppy": puppy.name})

        @app.websocket_route("/websocket-view/")
        async def puppy_websocket_view(session: websockets.WebSocket, puppy: Puppy):
            await session.accept()
            await session.send_json({"puppy": puppy.name})
            await session.close()

        @app.route("/nested-component/")
        async def nested_component_view(owner: Owner):
            return {"name": owner.name, "puppy": {"name": owner.puppy.name}}

        @app.route("/unknown-component/")
        def unknown_component_view(unknown: Unknown):
            return http.JSONResponse({"foo": "bar"})

        @app.route("/unknown-param-in-component/")
        def unknown_param_in_component_view(foo: Foo):
            return http.JSONResponse({"foo": "bar"})

    @pytest.mark.parametrize(
        ["url", "method", "params", "status_code", "result", "exception"],
        (
            pytest.param("/http-view/", "get", None, 200, {"puppy": "Canna"}, None, id="http_view"),
            pytest.param("/http-endpoint/", "get", None, 200, {"puppy": "Canna"}, None, id="http_endpoint"),
            pytest.param(
                "/http-endpoint/",
                "websocket",
                None,
                None,
                {"puppy": "Canna"},
                None,
                marks=pytest.mark.skip(
                    reason="Cannot test websockets with current client"
                ),  # CAVEAT: Client doesn't support websockets
                id="websocket",
            ),
            pytest.param(
                "/nested-component/",
                "get",
                None,
                200,
                {"name": "Perdy", "puppy": {"name": "Canna"}},
                None,
                id="nested_component",
            ),
            pytest.param(
                "/unknown-component/",
                "get",
                None,
                None,
                None,
                (
                    injection.ComponentNotFound,
                    "No component able to handle parameter 'unknown' for function 'unknown_component_view'",
                ),
                id="unknown_component",
            ),
            pytest.param(
                "/unknown-param-in-component/",
                "get",
                None,
                None,
                None,
                (
                    injection.ComponentNotFound,
                    "No component able to handle parameter 'foo' in component 'UnknownParamComponent' for function "
                    "'unknown_param_in_component_view'",
                ),
                id="unknown_param_in_component",
            ),
        ),
        indirect=["exception"],
    )
    async def test_injection(self, client, url, method, params, status_code, result, exception):
        with exception:
            if method == "websocket":
                with client.websocket_connect(url) as websocket:
                    assert websocket.receive_json() == result
            else:
                response = await client.request(method, url, params=params)

                assert response.status_code == status_code
                assert response.json() == result

    async def test_unhandled_component(self):
        class UnhandledComponent(injection.Component):
            def resolve(self):
                pass

        app = Flama(components=[UnhandledComponent()])

        @app.route("/")
        def foo(unknown: Unknown):
            return http.JSONResponse({"foo": "bar"})

        with pytest.raises(
            injection.ComponentError,
            match="Component 'UnhandledComponent' must include a return annotation on the 'resolve' method, "
            "or override 'can_handle_parameter'",
        ):
            async with Client(app) as client:
                await client.request("get", "/")
