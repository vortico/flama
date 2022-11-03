import pytest

from flama.applications import Flama
from flama.resources import BaseResource
from flama.resources.crud import CRUDResourceType
from flama.resources.routing import ResourceRoute
from flama.sqlalchemy import SQLAlchemyModule


class TestCaseResourcesModule:
    @pytest.fixture(scope="function")
    def app(self):
        return Flama(schema=None, docs=None, modules={SQLAlchemyModule("sqlite+aiosqlite://")})

    def test_add_resource(self, app, puppy_model, puppy_schema):
        class PuppyResource(BaseResource, metaclass=CRUDResourceType):
            name = "puppy"
            model = puppy_model
            schema = puppy_schema

        resource = PuppyResource()
        app.resources.add_resource("/puppy/", resource)

        assert len(app.routes) == 1
        assert isinstance(app.routes[0], ResourceRoute)
        resource_route = app.routes[0]
        assert len(resource_route.routes) == 4
        assert [(route.path, route.methods, route.endpoint) for route in resource_route.routes] == [
            ("/", {"POST"}, resource.create),
            ("/{element_id}/", {"GET", "HEAD"}, resource.retrieve),
            ("/{element_id}/", {"PUT"}, resource.update),
            ("/{element_id}/", {"DELETE"}, resource.delete),
        ]

    def test_add_resource_decorator(self, app, puppy_model, puppy_schema):
        class PuppyResource(BaseResource, metaclass=CRUDResourceType):
            name = "puppy"
            model = puppy_model
            schema = puppy_schema

        resource = app.resources.resource("/puppy/")(
            PuppyResource()
        )  # Apply decoration to an instance in order to check endpoints

        assert len(app.routes) == 1
        assert isinstance(app.routes[0], ResourceRoute)
        resource_route = app.routes[0]
        assert len(resource_route.routes) == 4
        assert [(route.path, route.methods, route.endpoint) for route in resource_route.routes] == [
            ("/", {"POST"}, resource.create),
            ("/{element_id}/", {"GET", "HEAD"}, resource.retrieve),
            ("/{element_id}/", {"PUT"}, resource.update),
            ("/{element_id}/", {"DELETE"}, resource.delete),
        ]

    def test_mount_resource_declarative(self, puppy_model, puppy_schema):
        class PuppyResource(BaseResource, metaclass=CRUDResourceType):
            name = "puppy"
            model = puppy_model
            schema = puppy_schema

        route = ResourceRoute("/puppy/", PuppyResource)

        # Check app is None yet
        assert route.main_app is None

        app = Flama(routes=[route], schema=None, docs=None)

        assert len(app.router.routes) == 1

        assert len(app.routes) == 1
        assert isinstance(app.routes[0], ResourceRoute)
        resource_route = app.routes[0]
        assert resource_route.main_app == app
        assert len(resource_route.routes) == 4
        assert [(route.path, route.methods, route.endpoint) for route in resource_route.routes] == [
            ("/", {"POST"}, resource_route.resource.create),
            ("/{element_id}/", {"GET", "HEAD"}, resource_route.resource.retrieve),
            ("/{element_id}/", {"PUT"}, resource_route.resource.update),
            ("/{element_id}/", {"DELETE"}, resource_route.resource.delete),
        ]
        assert isinstance(resource_route.resource, PuppyResource)
        assert resource_route.resource.app == app

        # Check app can be deleted
        del resource_route.main_app

        # Check app is None again
        with pytest.raises(AttributeError):
            route.main_app
