import pytest

from flama import exceptions
from flama.applications import Flama
from flama.client import Client
from flama.resources.crud import CRUDResource
from flama.resources.resource import Resource
from flama.resources.routing import ResourceRoute
from flama.routing import Mount, Route
from flama.sqlalchemy import SQLAlchemyModule


class TestCaseResourceRoute:
    @pytest.fixture(scope="function")
    def app(self):
        return Flama(schema=None, docs=None, modules={SQLAlchemyModule("sqlite+aiosqlite://")})

    @pytest.fixture(scope="function")
    def resource(self, puppy_model, puppy_schema):
        class PuppyResource(CRUDResource):
            name = "puppy"
            model = puppy_model
            schema = puppy_schema

        return PuppyResource()

    def test_init(self, resource):
        resource_route = ResourceRoute(
            "/puppy/",
            resource,
            tags={
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
        )

        assert resource_route.path == "/puppy/"
        assert resource_route.resource == resource
        for route in resource_route.routes:
            assert isinstance(route, Route)
        assert [
            (
                route.path,
                route.methods,
                route.endpoint.__wrapped__ if route.endpoint._meta.pagination else route.endpoint,
                route.tags,
            )
            for route in resource_route.routes
        ] == [
            ("/", {"POST"}, resource_route.resource.create, {"tag": "create"}),
            ("/{resource_id}/", {"GET", "HEAD"}, resource_route.resource.retrieve, {"tag": "retrieve"}),
            ("/{resource_id}/", {"PUT"}, resource_route.resource.update, {"tag": "update"}),
            ("/{resource_id}/", {"PATCH"}, resource_route.resource.partial_update, {"tag": "partial-update"}),
            ("/{resource_id}/", {"DELETE"}, resource_route.resource.delete, {"tag": "delete"}),
            ("/", {"GET", "HEAD"}, resource_route.resource.list, {"tag": "list"}),
            ("/", {"PUT"}, resource_route.resource.replace, {"tag": "replace"}),
            ("/", {"PATCH"}, resource_route.resource.partial_replace, {"tag": "partial-replace"}),
            ("/", {"DELETE"}, resource_route.resource.drop, {"tag": "drop"}),
        ]

    def test_init_wrong_tags(self, resource):
        with pytest.raises(exceptions.ApplicationError, match="Tags must be defined only for existing routes."):
            ResourceRoute(
                "/puppy/",
                resource,
                tags={
                    "create": {"tag": "create"},
                    "retrieve": {"tag": "retrieve"},
                    "update": {"tag": "update"},
                    "partial_update": {"tag": "partial-update"},
                    "delete": {"tag": "delete"},
                    "list": {"tag": "list"},
                    "replace": {"tag": "replace"},
                    "partial_replace": {"tag": "partial-replace"},
                    "drop": {"tag": "drop"},
                    "wrong": "wrong",
                },
            )

    def test_mount_resource_declarative(self, resource):
        routes = [Route("/", lambda: {"Hello": "world"}), ResourceRoute("/puppy/", resource)]

        app = Flama(routes=routes, schema=None, docs=None)

        assert len(app.router.routes) == 2

        assert len(app.routes) == 2
        resource_route = app.routes[1]
        assert isinstance(resource_route, ResourceRoute)
        assert [
            (
                route.path,
                route.methods,
                route.endpoint.__wrapped__ if route.endpoint._meta.pagination else route.endpoint,
            )
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

    def test_nested_mount_resource(self, resource):
        app = Flama(schema=None, docs=None)
        app.add_route(route=Route("/", lambda: {"Hello": "world"}))

        sub_app = Flama(schema=None, docs=None)
        sub_app.resources.add_resource("/puppy/", resource)
        app.mount("/", sub_app)

        assert len(app.router.routes) == 2

        assert len(app.routes) == 2
        mount = app.routes[1]
        assert isinstance(mount, Mount)
        assert len(mount.routes) == 1
        resource_route = mount.routes[0]
        assert isinstance(resource_route, ResourceRoute)
        assert [
            (
                route.path,
                route.methods,
                route.endpoint.__wrapped__ if route.endpoint._meta.pagination else route.endpoint,
            )
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

    async def test_request_nested_resource(self, app):
        class PuppyResource(Resource):
            name = "puppy"
            verbose_name = "Puppy"

            @ResourceRoute.method("/", methods=["GET"], name="puppy-list", tags={"foo": "bar"})
            async def list(self):
                return {"name": "Canna"}

        sub_app = Flama(schema=None, docs=None)
        sub_app.resources.add_resource("/puppy/", PuppyResource)
        app.mount("/", sub_app)
        app.mark = 1
        sub_app.mark = 2

        async with Client(app) as client:
            response = await client.get("/puppy/")
            assert response.status_code == 200

    def test_method(self):
        @ResourceRoute.method(
            path="/", methods=["POST"], name="foo", include_in_schema=False, tags={"additional": "bar"}
        )
        def foo(x: int):
            return x

        assert hasattr(foo, "_meta")
        assert foo._meta.path == "/"
        assert foo._meta.methods == {"POST"}
        assert foo._meta.name == "foo"
        assert foo._meta.include_in_schema is False
        assert foo._meta.tags == {"additional": "bar"}
