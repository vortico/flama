from unittest.mock import MagicMock, Mock, call

import pytest

from flama.resources.modules import ResourcesModule
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
        assert [(r.path, r.methods, getattr(r.endpoint, "__wrapped__", r.endpoint), r.tags) for r in route.routes] == [
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
        assert [(r.path, r.methods, getattr(r.endpoint, "__wrapped__", r.endpoint), r.tags) for r in route.routes] == [
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

    @pytest.mark.parametrize(
        ["exception"],
        [pytest.param(ValueError("Wrong resource"), id="bad_type")],
        indirect=["exception"],
    )
    def test_add_resource_wrong(self, app, exception):
        with exception:
            app.resources.add_resource("/puppy/", Mock())

    def test_add_resource_class(self, app, puppy_resource) -> None:
        """Cover the ``isclass(resource) and issubclass(Resource)`` branch."""
        cls = type(puppy_resource)
        route = app.resources.add_resource("/puppy-class/", cls)

        assert isinstance(route, ResourceRoute)
        assert route.path == "/puppy-class/"

    def test_method_decorator(self, app) -> None:
        decorator = app.resources.method("/", methods=["POST"], name="foo", include_in_schema=False)
        assert callable(decorator)

    @pytest.mark.parametrize(
        ["method", "args"],
        [
            pytest.param("add_repository", ("foo", Mock()), id="add"),
            pytest.param("remove_repository", ("foo",), id="remove"),
        ],
    )
    def test_repository_forwarding(self, method: str, args: tuple) -> None:
        worker = MagicMock()
        module = ResourcesModule(worker=worker)

        getattr(module, method)(*args)

        assert getattr(worker, method).call_args_list == [call(*args)]

    @pytest.mark.parametrize(
        ["method", "args"],
        [
            pytest.param("add_repository", ("foo", Mock()), id="add_without_worker"),
            pytest.param("remove_repository", ("foo",), id="remove_without_worker"),
        ],
    )
    def test_repository_forwarding_without_worker(self, method: str, args: tuple) -> None:
        module = ResourcesModule(worker=None)

        getattr(module, method)(*args)
