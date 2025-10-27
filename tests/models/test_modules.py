import pytest

from flama.models import ModelResource, ModelResourceType
from flama.resources.routing import ResourceRoute


class TestCaseResourcesModule:
    @pytest.fixture(scope="function")
    def tags(self):
        return {"inspect": {"tag": "inspect"}, "predict": {"tag": "predict"}}

    def test_add_model(self, app, component, tags):
        component_ = component

        class PuppyModelResource(ModelResource, metaclass=ModelResourceType):
            name = "puppy"
            verbose_name = "Puppy"
            component = component_

        route = app.models.add_model_resource("/", PuppyModelResource, tags=tags)

        assert len(app.routes) == 1
        assert isinstance(app.routes[0], ResourceRoute)
        resource_route = app.routes[0]
        assert len(resource_route.routes) == 2
        assert [(route.path, route.methods, route.endpoint, route.tags) for route in resource_route.routes] == [
            ("/", {"HEAD", "GET"}, route.resource.inspect, {"tag": "inspect"}),
            ("/predict/", {"POST"}, route.resource.predict, {"tag": "predict"}),
        ]

    def test_add_model_decorator(self, app, component, tags):
        component_ = component

        class PuppyModelResource(ModelResource, metaclass=ModelResourceType):
            name = "puppy"
            verbose_name = "Puppy"
            component = component_

        resource = app.models.model_resource("/", tags=tags)(
            PuppyModelResource()
        )  # Apply decoration to an instance in order to check endpoints

        assert len(app.routes) == 1
        assert isinstance(app.routes[0], ResourceRoute)
        resource_route = app.routes[0]
        assert len(resource_route.routes) == 2
        assert [(route.path, route.methods, route.endpoint, route.tags) for route in resource_route.routes] == [
            ("/", {"HEAD", "GET"}, resource.inspect, {"tag": "inspect"}),
            ("/predict/", {"POST"}, resource.predict, {"tag": "predict"}),
        ]

    def test_add_model_resource(self, app, component, tags):
        component_ = component

        class PuppyModelResource(ModelResource, metaclass=ModelResourceType):
            name = "puppy"
            verbose_name = "Puppy"
            component = component_

        resource = PuppyModelResource()

        app.models.add_model_resource("/", resource, tags=tags)

        assert len(app.routes) == 1
        assert isinstance(app.routes[0], ResourceRoute)
        resource_route = app.routes[0]
        assert len(resource_route.routes) == 2
        assert [(route.path, route.methods, route.endpoint, route.tags) for route in resource_route.routes] == [
            ("/", {"HEAD", "GET"}, resource.inspect, {"tag": "inspect"}),
            ("/predict/", {"POST"}, resource.predict, {"tag": "predict"}),
        ]
