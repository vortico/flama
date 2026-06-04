import inspect

import pytest

from flama import exceptions
from flama.applications import Flama
from flama.client import Client
from flama.resources import data_structures
from flama.resources.resource import Resource
from flama.resources.routing import ResourceRoute, resource_method
from flama.routing import Mount, Route


class TestCaseResourceRoute:
    @pytest.mark.parametrize(
        ["tags", "exception"],
        [
            pytest.param(
                {
                    "create": {"tag": "create"},
                    "retrieve": {"tag": "retrieve"},
                    "update": {"tag": "update"},
                    "partial_update": {"tag": "partial-update"},
                    "delete": {"tag": "delete"},
                    "list": {"tag": "list"},
                    "replace": {"tag": "replace"},
                    "partial_replace": {"tag": "partial-replace"},
                    "drop": {"tag": "drop"},
                },
                None,
                id="ok",
            ),
            pytest.param(
                {"wrong": "wrong"},
                exceptions.ApplicationError("Tags must be defined only for existing routes."),
                id="unknown_tag",
            ),
        ],
        indirect=["exception"],
    )
    def test_init(self, app, puppy_resource, tags, exception) -> None:
        with exception:
            resource_route = ResourceRoute("/puppy/", puppy_resource, tags=tags, parent=app)

            for route in resource_route.routes:
                assert isinstance(route, Route)
            assert [
                (route.path, route.methods, getattr(route.endpoint, "__wrapped__", route.endpoint), route.tags)
                for route in resource_route.routes
            ] == [
                ("/", {"POST"}, resource_route.resource.create, tags["create"]),
                ("/{resource_id}/", {"GET", "HEAD"}, resource_route.resource.retrieve, tags["retrieve"]),
                ("/{resource_id}/", {"PUT"}, resource_route.resource.update, tags["update"]),
                ("/{resource_id}/", {"PATCH"}, resource_route.resource.partial_update, tags["partial_update"]),
                ("/{resource_id}/", {"DELETE"}, resource_route.resource.delete, tags["delete"]),
                ("/", {"GET", "HEAD"}, resource_route.resource.list, tags["list"]),
                ("/", {"PUT"}, resource_route.resource.replace, tags["replace"]),
                ("/", {"PATCH"}, resource_route.resource.partial_replace, tags["partial_replace"]),
                ("/", {"DELETE"}, resource_route.resource.drop, tags["drop"]),
            ]

    def test_nested_mount(self, app, puppy_resource) -> None:
        app.add_route(route=Route("/", lambda: {"Hello": "world"}))

        sub_app = Flama(schema=None, docs=None, schema_library=app.schema.schema_library.name)
        sub_app.resources.add_resource("/puppy/", puppy_resource)
        app.mount("/", sub_app)

        assert len(app.router.routes) == 2
        assert len(app.routes) == 2
        mount = app.routes[1]
        assert isinstance(mount, Mount)
        assert len(mount.routes) == 1
        resource_route = mount.routes[0]
        assert isinstance(resource_route, ResourceRoute)
        assert [
            (route.path, route.methods, getattr(route.endpoint, "__wrapped__", route.endpoint))
            for route in resource_route.routes
        ] == [
            ("/", {"POST"}, resource_route.resource.create),
            ("/{resource_id}/", {"GET", "HEAD"}, resource_route.resource.retrieve),
            ("/{resource_id}/", {"PUT"}, resource_route.resource.update),
            ("/{resource_id}/", {"PATCH"}, resource_route.resource.partial_update),
            ("/{resource_id}/", {"DELETE"}, resource_route.resource.delete),
            ("/", {"GET", "HEAD"}, resource_route.resource.list),
            ("/", {"PUT"}, resource_route.resource.replace),
            ("/", {"PATCH"}, resource_route.resource.partial_replace),
            ("/", {"DELETE"}, resource_route.resource.drop),
        ]

    async def test_request_nested_resource(self, app) -> None:
        class PuppyResource(Resource):
            name = "puppy"
            verbose_name = "Puppy"

            @ResourceRoute.method("/", methods=["GET"], name="puppy-list", tags={"foo": "bar"})
            async def list(self):
                return {"name": "Canna"}

        sub_app = Flama(schema=None, docs=None)
        sub_app.resources.add_resource("/puppy/", PuppyResource)
        app.mount("/", sub_app)

        async with Client(app=app) as client:
            response = await client.get("/puppy/")
            assert response.status_code == 200

    def test_method(self) -> None:
        def foo(x: int):
            return x

        decorated_foo = ResourceRoute.method(
            path="/", methods=["POST"], name="foo", include_in_schema=False, tags={"additional": "bar"}
        )(foo)

        assert isinstance(decorated_foo, data_structures.ResourceMethod)
        assert decorated_foo.func.method == foo
        assert decorated_foo.func.name == "foo"
        assert decorated_foo.func.signature == inspect.signature(foo)
        assert decorated_foo.meta.path == "/"
        assert decorated_foo.meta.methods == {"POST"}
        assert decorated_foo.meta.name == "foo"
        assert decorated_foo.meta.include_in_schema is False
        assert decorated_foo.meta.tags == {"additional": "bar"}


class TestCaseResourceMethodDecorator:
    def test_deprecated_shim_warns_and_forwards(self) -> None:
        def foo(x: int):
            return x

        with pytest.warns(DeprecationWarning, match="Deprecated decorator"):
            decorated_foo = resource_method(
                path="/", methods=["POST"], name="foo", include_in_schema=False, tags={"additional": "bar"}
            )(foo)

        assert isinstance(decorated_foo, data_structures.ResourceMethod)
        assert decorated_foo.func.method == foo
        assert decorated_foo.meta.path == "/"
        assert decorated_foo.meta.methods == {"POST"}
        assert decorated_foo.meta.name == "foo"
        assert decorated_foo.meta.include_in_schema is False
        assert decorated_foo.meta.tags == {"additional": "bar"}
