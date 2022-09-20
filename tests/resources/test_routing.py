import pytest

from flama.applications import Flama
from flama.resources import BaseResource
from flama.resources.crud import CRUDResourceType
from flama.resources.routing import ResourceRoute, resource_method
from flama.routing import Route


class TestCaseRouter:
    @pytest.fixture(scope="function")
    def app(self):
        return Flama(schema=None, docs=None, sqlalchemy_database="sqlite+aiosqlite://")

    def test_mount_resource_declarative(self, puppy_model, puppy_schema):
        class PuppyResource(BaseResource, metaclass=CRUDResourceType):
            name = "puppy"
            model = puppy_model
            schema = puppy_schema

        routes = [Route("/", lambda: {"Hello": "world"}), ResourceRoute("/puppy/", PuppyResource)]

        app = Flama(routes=routes, schema=None, docs=None)

        assert len(app.router.routes) == 2

        assert len(app.routes) == 2
        resource_route = app.routes[1]
        assert isinstance(resource_route, ResourceRoute)
        assert len(resource_route.routes) == 4
        for route in resource_route.routes:
            assert isinstance(route, Route)
        assert [(route.path, route.methods, route.endpoint) for route in resource_route.routes] == [
            ("/", {"POST"}, resource_route.resource.create),
            ("/{element_id}/", {"GET", "HEAD"}, resource_route.resource.retrieve),
            ("/{element_id}/", {"PUT"}, resource_route.resource.update),
            ("/{element_id}/", {"DELETE"}, resource_route.resource.delete),
        ]


class TestCaseResourceMethod:
    def test_resource_method(self):
        @resource_method(path="/", methods=["POST"], name="foo", additional="bar")
        def foo(x: int):
            return x

        assert hasattr(foo, "_meta")
        assert foo._meta.path == "/"
        assert foo._meta.methods == ("POST",)
        assert foo._meta.name == "foo"
        assert foo._meta.kwargs == {"additional": "bar"}
