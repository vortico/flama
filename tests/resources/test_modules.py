from unittest.mock import Mock

import pytest

from flama.resources.routing import ResourceRoute


class TestCaseResourcesModule:
    @pytest.fixture(scope="function")
    def tags(self):
        return {
            "create": {"tag": "create"},
            "retrieve": {"tag": "retrieve"},
            "update": {"tag": "update"},
            "partial_update": {"tag": "partial-update"},
            "delete": {"tag": "delete"},
            "list": {"tag": "list"},
            "replace": {"tag": "replace"},
            "partial_replace": {"tag": "partial-replace"},
            "drop": {"tag": "drop"},
        }

    @pytest.fixture(scope="function", autouse=True)
    def add_resources(self, app, puppy_resource, tags):
        app.resources.add_resource("/puppy-resource/", puppy_resource, tags=tags)
        app.resources.resource("/puppy-decorator/", tags=tags)(puppy_resource)

    def test_add_resource(self, client):
        route = next((route for route in client.app.routes if route.path == "/puppy-resource/"), None)

        assert route
        assert isinstance(route, ResourceRoute)
        assert [
            (r.path, r.methods, r.endpoint.__wrapped__ if r.endpoint._meta.pagination else r.endpoint, r.tags)
            for r in route.routes
        ] == [
            ("/", {"POST"}, route.resource.create, {"tag": "create"}),
            ("/{resource_id}/", {"GET", "HEAD"}, route.resource.retrieve, {"tag": "retrieve"}),
            ("/{resource_id}/", {"PUT"}, route.resource.update, {"tag": "update"}),
            ("/{resource_id}/", {"PATCH"}, route.resource.partial_update, {"tag": "partial-update"}),
            ("/{resource_id}/", {"DELETE"}, route.resource.delete, {"tag": "delete"}),
            ("/", {"GET", "HEAD"}, route.resource.list, {"tag": "list"}),
            ("/", {"PUT"}, route.resource.replace, {"tag": "replace"}),
            ("/", {"PATCH"}, route.resource.partial_replace, {"tag": "partial-replace"}),
            ("/", {"DELETE"}, route.resource.drop, {"tag": "drop"}),
        ]
        assert route.resource._meta.name in route.app.resources.worker._resources_repositories.registered

    def test_add_resource_decorator(self, client, puppy_resource):
        route = next((route for route in client.app.routes if route.path == "/puppy-resource/"), None)

        assert route
        assert isinstance(route, ResourceRoute)
        assert [
            (r.path, r.methods, r.endpoint.__wrapped__ if r.endpoint._meta.pagination else r.endpoint, r.tags)
            for r in route.routes
        ] == [
            ("/", {"POST"}, puppy_resource.create, {"tag": "create"}),
            ("/{resource_id}/", {"GET", "HEAD"}, puppy_resource.retrieve, {"tag": "retrieve"}),
            ("/{resource_id}/", {"PUT"}, puppy_resource.update, {"tag": "update"}),
            ("/{resource_id}/", {"PATCH"}, puppy_resource.partial_update, {"tag": "partial-update"}),
            ("/{resource_id}/", {"DELETE"}, puppy_resource.delete, {"tag": "delete"}),
            ("/", {"GET", "HEAD"}, puppy_resource.list, {"tag": "list"}),
            ("/", {"PUT"}, puppy_resource.replace, {"tag": "replace"}),
            ("/", {"PATCH"}, puppy_resource.partial_replace, {"tag": "partial-replace"}),
            ("/", {"DELETE"}, puppy_resource.drop, {"tag": "drop"}),
        ]
        assert route.resource._meta.name in route.app.resources.worker._resources_repositories.registered

    def test_add_resource_wrong(self, app):
        with pytest.raises(ValueError, match="Wrong resource"):
            app.resources.add_resource("/puppy/", Mock())
