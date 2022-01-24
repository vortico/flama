import pytest

from flama.applications import Flama
from flama.resources import BaseResource
from flama.resources.crud import CRUDResource
from flama.resources.routing import ResourceRoute


class TestCaseRouter:
    @pytest.fixture(scope="function")
    def app(self):
        return Flama(schema=None, docs=None)

    @pytest.fixture(scope="function")
    def scope(self, app):
        return {
            "app": app,
            "client": ["testclient", 50000],
            "endpoint": None,
            "extensions": {"http.response.template": {}},
            "headers": [
                (b"host", b"testserver"),
                (b"user-agent", b"testclient"),
                (b"accept-encoding", b"gzip, deflate"),
                (b"accept", b"*/*"),
                (b"connection", b"keep-alive"),
            ],
            "http_version": "1.1",
            "method": "GET",
            "path": "/",
            "path_params": {},
            "query_string": b"",
            "root_path": "",
            "router": app.router,
            "scheme": "http",
            "server": ["testserver", 80],
            "type": "http",
        }

    def test_add_resource(self, app, puppy_model, puppy_schema):
        class PuppyResource(BaseResource, metaclass=CRUDResource):
            name = "puppy"
            model = puppy_model
            schema = puppy_schema

        resource = PuppyResource()
        app.resources.add_resource("/", resource)

        assert len(app.routes) == 1
        assert isinstance(app.routes[0], ResourceRoute)
        resource_route = app.routes[0]
        assert len(resource_route.routes) == 4
        assert [(route.path, route.methods, route.endpoint) for route in resource_route.routes] == [
            ("/puppy/", {"POST"}, resource.create),
            ("/puppy/{element_id}/", {"GET", "HEAD"}, resource.retrieve),
            ("/puppy/{element_id}/", {"PUT"}, resource.update),
            ("/puppy/{element_id}/", {"DELETE"}, resource.delete),
        ]

    def test_add_resource_decorator(self, app, puppy_model, puppy_schema):
        class PuppyResource(BaseResource, metaclass=CRUDResource):
            name = "puppy"
            model = puppy_model
            schema = puppy_schema

        resource = app.resources.resource("/")(
            PuppyResource()
        )  # Apply decoration to an instance in order to check endpoints

        assert len(app.routes) == 1
        assert isinstance(app.routes[0], ResourceRoute)
        resource_route = app.routes[0]
        assert len(resource_route.routes) == 4
        assert [(route.path, route.methods, route.endpoint) for route in resource_route.routes] == [
            ("/puppy/", {"POST"}, resource.create),
            ("/puppy/{element_id}/", {"GET", "HEAD"}, resource.retrieve),
            ("/puppy/{element_id}/", {"PUT"}, resource.update),
            ("/puppy/{element_id}/", {"DELETE"}, resource.delete),
        ]

    def test_mount_resource_declarative(self, puppy_model, puppy_schema):
        class PuppyResource(BaseResource, metaclass=CRUDResource):
            name = "puppy"
            model = puppy_model
            schema = puppy_schema

        route = ResourceRoute("/", PuppyResource)

        # Check app is None yet
        with pytest.raises(AttributeError):
            route.main_app

        app = Flama(routes=[route], schema=None, docs=None)

        assert len(app.router.routes) == 1

        assert len(app.routes) == 1
        assert isinstance(app.routes[0], ResourceRoute)
        resource_route = app.routes[0]
        assert resource_route.main_app == app
        assert len(resource_route.routes) == 4
        assert [(route.path, route.methods, route.endpoint) for route in resource_route.routes] == [
            ("/puppy/", {"POST"}, resource_route.resource.create),
            ("/puppy/{element_id}/", {"GET", "HEAD"}, resource_route.resource.retrieve),
            ("/puppy/{element_id}/", {"PUT"}, resource_route.resource.update),
            ("/puppy/{element_id}/", {"DELETE"}, resource_route.resource.delete),
        ]
        assert isinstance(resource_route.resource, PuppyResource)
        assert resource_route.resource.app == app

        # Check app can be deleted
        del resource_route.main_app

        # Check app is None again
        with pytest.raises(AttributeError):
            route.main_app
