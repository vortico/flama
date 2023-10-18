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


class ParamObject1:
    def __init__(self, param):
        self.param = param


class ParamObject2:
    def __init__(self, param):
        self.param = param


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

    @pytest.fixture(scope="class")
    def param_component_1(self):
        class ParamComponent1(injection.Component):
            def resolve(self, param: str) -> ParamObject1:
                return ParamObject1(param=param)

        return ParamComponent1()

    @pytest.fixture(scope="class")
    def param_component_2(self):
        class ParamComponent2(injection.Component):
            def resolve(self, param: str) -> ParamObject2:
                return ParamObject2(param=param)

        return ParamComponent2()

    @pytest.fixture(scope="function", autouse=True)
    def add_components(
        self, app, puppy_component, owner_component, param_component_1, param_component_2, unknown_param_component
    ):
        for component in [
            puppy_component,
            owner_component,
            param_component_1,
            param_component_2,
            unknown_param_component,
        ]:
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

        @app.route("/param-1-component/")
        async def param_1_components_view(param: ParamObject1):
            return {"param": param.param}

        @app.route("/param-2-component/")
        async def param_2_components_view(param: ParamObject2):
            return {"param": param.param}

        @app.route("/same-param-components/")
        async def same_param_components_view(param1: ParamObject1, param2: ParamObject2):
            return {"param1": param1.param, "param2": param2.param}

        @app.route("/unknown-component/")
        def unknown_component_view(unknown: Unknown):
            return http.JSONResponse({"foo": "bar"})

        @app.route("/unknown-param-in-component/")
        def unknown_param_in_component_view(foo: Foo):
            return http.JSONResponse({"foo": "bar"})

    async def test_injection_http_view(self, client):
        response = await client.request("get", "/http-view/")
        assert response.status_code == 200
        assert response.json() == {"puppy": "Canna"}

    async def test_injection_http_endpoint(self, client):
        response = await client.request("get", "/http-endpoint/")
        assert response.status_code == 200
        assert response.json() == {"puppy": "Canna"}

    @pytest.mark.skip(reason="Cannot test websockets with current client")  # CAVEAT: Client doesn't support websockets
    def test_injection_websocket_view(self, client):
        with client.websocket_connect("/websocket-view/") as websocket:
            assert websocket.receive_json() == {"puppy": "Canna"}

    async def test_nested_component(self, client):
        response = await client.request("get", "/nested-component/")
        assert response.status_code == 200
        assert response.json() == {"name": "Perdy", "puppy": {"name": "Canna"}}

    async def test_same_param_components_single_view(self, client):
        response = await client.request("get", "/same-param-components/", params={"param": "foo"})
        assert response.status_code == 200
        assert response.json() == {"param1": "foo", "param2": "foo"}

    async def test_same_param_components_multiple_views(self, client):
        response = await client.request("get", "/param-1-component/", params={"param": "foo"})
        assert response.status_code == 200
        assert response.json() == {"param": "foo"}

        response = await client.request("get", "/param-2-component/", params={"param": "foo"})
        assert response.status_code == 200
        assert response.json() == {"param": "foo"}

    async def test_unknown_component(self, client):
        with pytest.raises(
            injection.ComponentNotFound,
            match="No component able to handle parameter 'unknown' for function 'unknown_component_view'",
        ):
            await client.request("get", "/unknown-component/")

    async def test_unknown_param_in_component(self, client):
        with pytest.raises(
            injection.ComponentNotFound,
            match="No component able to handle parameter 'foo' in component 'UnknownParamComponent' for function "
            "'unknown_param_in_component_view'",
        ):
            await client.request("get", "/unknown-param-in-component/")

    async def test_unhandled_component(self):
        class UnhandledComponent(injection.Component):
            def resolve(self):
                pass

        app = Flama(components=[UnhandledComponent()])

        @app.route("/")
        def foo(unknown: Unknown):
            return http.JSONResponse({"foo": "bar"})

        with pytest.raises(
            AssertionError,
            match="Component 'UnhandledComponent' must include a return annotation on the 'resolve' method, "
            "or override 'can_handle_parameter'",
        ):
            async with Client(app) as client:
                await client.request("get", "/")
