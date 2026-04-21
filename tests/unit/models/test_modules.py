import pathlib
from unittest.mock import MagicMock, patch

import pytest

from flama.models import LLMResource, LLMResourceType, MLResource, MLResourceType
from flama.resources.routing import ResourceRoute


class TestCaseResourcesModule:
    @pytest.fixture(scope="function")
    def tags(self):
        return {"inspect": {"tag": "inspect"}, "predict": {"tag": "predict"}, "stream": {"tag": "stream"}}

    @pytest.fixture(scope="function")
    def llm_tags(self):
        return {
            "inspect": {"tag": "inspect"},
            "configure": {"tag": "configure"},
            "query": {"tag": "query"},
            "stream": {"tag": "stream"},
        }

    def test_add_model(self, app, component, tags):
        component_ = component

        class PuppyMLResource(MLResource, metaclass=MLResourceType):
            name = "puppy"
            verbose_name = "Puppy"
            component = component_

        route = app.models.add_model_resource("/", PuppyMLResource, tags=tags)

        assert len(app.routes) == 1
        assert isinstance(app.routes[0], ResourceRoute)
        resource_route = app.routes[0]
        assert len(resource_route.routes) == 3
        assert [(route.path, route.methods, route.endpoint, route.tags) for route in resource_route.routes] == [
            ("/", {"HEAD", "GET"}, route.resource.inspect, {"tag": "inspect"}),
            ("/predict/", {"POST"}, route.resource.predict, {"tag": "predict"}),
            ("/stream/", {"POST"}, route.resource.stream, {"tag": "stream"}),
        ]

    def test_add_model_decorator(self, app, component, tags):
        component_ = component

        class PuppyMLResource(MLResource, metaclass=MLResourceType):
            name = "puppy"
            verbose_name = "Puppy"
            component = component_

        resource = app.models.model_resource("/", tags=tags)(
            PuppyMLResource()
        )  # Apply decoration to an instance in order to check endpoints

        assert len(app.routes) == 1
        assert isinstance(app.routes[0], ResourceRoute)
        resource_route = app.routes[0]
        assert len(resource_route.routes) == 3
        assert [(route.path, route.methods, route.endpoint, route.tags) for route in resource_route.routes] == [
            ("/", {"HEAD", "GET"}, resource.inspect, {"tag": "inspect"}),
            ("/predict/", {"POST"}, resource.predict, {"tag": "predict"}),
            ("/stream/", {"POST"}, resource.stream, {"tag": "stream"}),
        ]

    def test_add_model_resource(self, app, component, tags):
        component_ = component

        class PuppyMLResource(MLResource, metaclass=MLResourceType):
            name = "puppy"
            verbose_name = "Puppy"
            component = component_

        resource = PuppyMLResource()

        app.models.add_model_resource("/", resource, tags=tags)

        assert len(app.routes) == 1
        assert isinstance(app.routes[0], ResourceRoute)
        resource_route = app.routes[0]
        assert len(resource_route.routes) == 3
        assert [(route.path, route.methods, route.endpoint, route.tags) for route in resource_route.routes] == [
            ("/", {"HEAD", "GET"}, resource.inspect, {"tag": "inspect"}),
            ("/predict/", {"POST"}, resource.predict, {"tag": "predict"}),
            ("/stream/", {"POST"}, resource.stream, {"tag": "stream"}),
        ]

    def test_add_llm(self, app, llm_component, llm_tags):
        with patch(
            "flama.models.llm_resource.ModelComponentBuilder.load",
            return_value=llm_component,
        ):
            app.models.add_llm("/llm/", model=pathlib.Path("/fake/model.flm"), name="puppy", tags=llm_tags)

        assert len(app.routes) == 1
        assert isinstance(app.routes[0], ResourceRoute)
        resource_route = app.routes[0]
        assert len(resource_route.routes) == 4
        assert [(route.path, route.methods) for route in resource_route.routes] == [
            ("/", {"HEAD", "GET"}),
            ("/", {"PUT"}),
            ("/query/", {"POST"}),
            ("/stream/", {"POST"}),
        ]

    def test_add_llm_decorator(self, app, llm_component, llm_tags):
        component_ = llm_component

        class PuppyLLMResource(LLMResource, metaclass=LLMResourceType):
            name = "puppy"
            verbose_name = "Puppy"
            component = component_

        app.models.llm_resource("/", tags=llm_tags)(PuppyLLMResource())

        assert len(app.routes) == 1
        assert isinstance(app.routes[0], ResourceRoute)
        resource_route = app.routes[0]
        assert len(resource_route.routes) == 4
        assert [(route.path, route.methods) for route in resource_route.routes] == [
            ("/", {"HEAD", "GET"}),
            ("/", {"PUT"}),
            ("/query/", {"POST"}),
            ("/stream/", {"POST"}),
        ]

    @pytest.mark.parametrize(
        ["has_artifact"],
        (
            pytest.param(False, id="no-artifact"),
            pytest.param(True, id="with-artifact"),
        ),
    )
    def test_add_llm_resource(self, app, llm_component, llm_tags, has_artifact):
        if has_artifact:
            llm_component._artifact = MagicMock()

        component_ = llm_component

        class PuppyLLMResource(LLMResource, metaclass=LLMResourceType):
            name = "puppy"
            verbose_name = "Puppy"
            component = component_

        resource = PuppyLLMResource()

        app.models.add_llm_resource("/", resource, tags=llm_tags)

        assert len(app.routes) == 1
        assert isinstance(app.routes[0], ResourceRoute)
        resource_route = app.routes[0]
        assert len(resource_route.routes) == 4
        assert [(route.path, route.methods) for route in resource_route.routes] == [
            ("/", {"HEAD", "GET"}),
            ("/", {"PUT"}),
            ("/query/", {"POST"}),
            ("/stream/", {"POST"}),
        ]
        if has_artifact:
            assert app.models._artifacts == [llm_component._artifact]
