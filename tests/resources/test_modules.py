from unittest.mock import Mock

import pytest

from flama.applications import Flama
from flama.resources import BaseResource
from flama.resources.crud import CRUDResourceType
from flama.resources.routing import ResourceRoute
from flama.sqlalchemy import SQLAlchemyModule


class TestCaseResourcesModule:
    @pytest.fixture(scope="function")
    def tags(self):
        return {
            "create": {"tag": "create"},
            "retrieve": {"tag": "retrieve"},
            "update": {"tag": "update"},
            "delete": {"tag": "delete"},
        }

    @pytest.fixture(scope="function")
    def app(self):
        return Flama(schema=None, docs=None, modules={SQLAlchemyModule("sqlite+aiosqlite://")})

    def test_add_resource(self, app, puppy_model, puppy_schema, tags):
        class PuppyResource(BaseResource, metaclass=CRUDResourceType):
            name = "puppy"
            model = puppy_model
            schema = puppy_schema

        resource = PuppyResource()
        app.resources.add_resource("/puppy/", resource, tags=tags)

        try:
            assert len(app.routes) == 1
            assert isinstance(app.routes[0], ResourceRoute)
            resource_route = app.routes[0]
            assert len(resource_route.routes) == 4
            assert [(route.path, route.methods, route.endpoint, route.tags) for route in resource_route.routes] == [
                ("/", {"POST"}, resource.create, {"tag": "create"}),
                ("/{element_id}/", {"GET", "HEAD"}, resource.retrieve, {"tag": "retrieve"}),
                ("/{element_id}/", {"PUT"}, resource.update, {"tag": "update"}),
                ("/{element_id}/", {"DELETE"}, resource.delete, {"tag": "delete"}),
            ]
        finally:
            del app.resources.worker._repositories[PuppyResource._meta.name]

    def test_add_resource_decorator(self, app, puppy_model, puppy_schema, tags):
        class PuppyResource(BaseResource, metaclass=CRUDResourceType):
            name = "puppy"
            model = puppy_model
            schema = puppy_schema

        resource = app.resources.resource("/puppy/", tags=tags)(
            PuppyResource()
        )  # Apply decoration to an instance in order to check endpoints

        try:
            assert len(app.routes) == 1
            assert isinstance(app.routes[0], ResourceRoute)
            resource_route = app.routes[0]
            assert len(resource_route.routes) == 4
            assert [(route.path, route.methods, route.endpoint, route.tags) for route in resource_route.routes] == [
                ("/", {"POST"}, resource.create, {"tag": "create"}),
                ("/{element_id}/", {"GET", "HEAD"}, resource.retrieve, {"tag": "retrieve"}),
                ("/{element_id}/", {"PUT"}, resource.update, {"tag": "update"}),
                ("/{element_id}/", {"DELETE"}, resource.delete, {"tag": "delete"}),
            ]
        finally:
            del app.resources.worker._repositories[PuppyResource._meta.name]

    def test_add_resource_wrong(self, app):
        with pytest.raises(ValueError, match=""):
            app.resources.add_resource("/puppy/", Mock())

    def test_mount_resource_declarative(self, puppy_model, puppy_schema, tags):
        class PuppyResource(BaseResource, metaclass=CRUDResourceType):
            name = "puppy"
            model = puppy_model
            schema = puppy_schema

        route = ResourceRoute("/puppy/", PuppyResource, tags=tags)

        app = Flama(routes=[route], schema=None, docs=None)

        try:
            assert len(app.router.routes) == 1
            assert len(app.routes) == 1
            assert isinstance(app.routes[0], ResourceRoute)
            resource_route = app.routes[0]
            assert len(resource_route.routes) == 4
            assert [(route.path, route.methods, route.endpoint, route.tags) for route in resource_route.routes] == [
                ("/", {"POST"}, resource_route.resource.create, {"tag": "create"}),
                ("/{element_id}/", {"GET", "HEAD"}, resource_route.resource.retrieve, {"tag": "retrieve"}),
                ("/{element_id}/", {"PUT"}, resource_route.resource.update, {"tag": "update"}),
                ("/{element_id}/", {"DELETE"}, resource_route.resource.delete, {"tag": "delete"}),
            ]
            assert isinstance(resource_route.resource, PuppyResource)
            assert PuppyResource._meta.name in app.resources.worker._repositories
        finally:
            del app.resources.worker._repositories[PuppyResource._meta.name]
