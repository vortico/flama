import pytest
from starlette.responses import JSONResponse
from starlette.testclient import TestClient
from starlette.websockets import WebSocket

from flama import Component
from flama.applications import Flama
from flama.endpoints import HTTPEndpoint
from flama.exceptions import ComponentNotFound, ConfigurationError


class Puppy:
    name = "Canna"


class Unknown(Puppy):
    pass


class Foo:
    name = "Foo"


class TestCaseComponentsInjection:
    @pytest.fixture(scope="class")
    def puppy_component(self):
        class PuppyComponent(Component):
            def resolve(self) -> Puppy:
                return Puppy()

        return PuppyComponent()

    @pytest.fixture(scope="class")
    def unknown_param_component(self):
        class UnknownParamComponent(Component):
            def resolve(self, foo: Unknown) -> Foo:
                pass

        return UnknownParamComponent()

    @pytest.fixture
    def app(self, app, puppy_component, unknown_param_component):
        return Flama(components=[puppy_component, unknown_param_component])

    @pytest.fixture(autouse=True)
    def add_endpoints(self, app):
        @app.route("/http-view/")
        async def puppy_http_view(puppy: Puppy):
            return JSONResponse({"puppy": puppy.name})

        @app.route("/http-endpoint/", methods=["GET"])
        class PuppyHTTPEndpoint(HTTPEndpoint):
            async def get(self, puppy: Puppy):
                return JSONResponse({"puppy": puppy.name})

        @app.websocket_route("/websocket-view/")
        async def puppy_websocket_view(session: WebSocket, puppy: Puppy):
            await session.accept()
            await session.send_json({"puppy": puppy.name})
            await session.close()

        @app.route("/unknown-component/")
        def unknown_component_view(unknown: Unknown):
            return JSONResponse({"foo": "bar"})

        @app.route("/unknown-param-in-component/")
        def unknown_param_in_component_view(foo: Foo):
            return JSONResponse({"foo": "bar"})

    def test_injection_http_view(self, client):
        response = client.get("/http-view/")
        assert response.status_code == 200
        assert response.json() == {"puppy": "Canna"}

    def test_injection_http_endpoint(self, client):
        response = client.get("/http-endpoint/")
        assert response.status_code == 200
        assert response.json() == {"puppy": "Canna"}

    def test_injection_websocket_view(self, client):
        with client.websocket_connect("/websocket-view/") as websocket:
            assert websocket.receive_json() == {"puppy": "Canna"}

    def test_unknown_component(self, client):
        with pytest.raises(
            ComponentNotFound,
            match='No component able to handle parameter "unknown" for function "unknown_component_view"',
        ):
            client.get("/unknown-component/")

    def test_unknown_param_in_component(self, client):
        with pytest.raises(
            ComponentNotFound,
            match='No component able to handle parameter "foo" in component "UnknownParamComponent" for function '
            '"unknown_param_in_component_view"',
        ):
            client.get("/unknown-param-in-component/")

    def test_unhandled_component(self):
        class UnhandledComponent(Component):
            def resolve(self):
                pass

        app = Flama(components=[UnhandledComponent()])

        @app.route("/")
        def foo(unknown: Unknown):
            return JSONResponse({"foo": "bar"})

        with pytest.raises(
            ConfigurationError,
            match=r'Component "UnhandledComponent" must include a return annotation on the `resolve\(\)` method, '
            "or override `can_handle_parameter`",
        ), TestClient(app) as client:
            client.get("/")
