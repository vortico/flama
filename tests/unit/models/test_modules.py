import pathlib
from unittest.mock import MagicMock, patch

import pytest

from flama.models import LLMResource, LLMResourceType, MLResource, MLResourceType
from flama.resources.routing import ResourceRoute


class TestCaseResourcesModule:
    @pytest.fixture(scope="function")
    def tags(self):
        return {
            "inspect": {"tag": "inspect"},
            "predict": {"tag": "predict"},
            "stream": {"tag": "stream"},
        }

    @pytest.fixture(scope="function")
    def llm_tags(self):
        return {
            "inspect": {"tag": "inspect"},
            "configure": {"tag": "configure"},
            "query": {"tag": "query"},
            "stream": {"tag": "stream"},
        }

    @pytest.fixture(scope="function")
    def ml_resource_class(self, component) -> type[MLResource]:
        component_ = component

        class PuppyMLResource(MLResource, metaclass=MLResourceType):
            name = "puppy"
            verbose_name = "Puppy"
            component = component_

        return PuppyMLResource

    @pytest.fixture(scope="function")
    def llm_resource_class(self, llm_component) -> type[LLMResource]:
        component_ = llm_component

        class PuppyLLMResource(LLMResource, metaclass=LLMResourceType):
            name = "puppy"
            verbose_name = "Puppy"
            component = component_

        return PuppyLLMResource

    def test_add_model(self, app, component, tags):
        with patch("flama.models.ml_resource.MLModelComponentBuilder.load", return_value=component):
            app.models.add_model("/", model=pathlib.Path("/fake/model.flm"), name="puppy", tags=tags)

        assert len(app.routes) == 1
        assert isinstance(app.routes[0], ResourceRoute)
        resource_route = app.routes[0]
        assert len(resource_route.routes) == 3
        assert [(route.path, route.methods) for route in resource_route.routes] == [
            ("/", {"HEAD", "GET"}),
            ("/predict/", {"POST"}),
            ("/stream/", {"POST"}),
        ]

    @pytest.mark.parametrize(
        ["kind"],
        [pytest.param("class", id="class"), pytest.param("instance", id="instance")],
    )
    def test_add_model_resource(self, app, ml_resource_class, tags, kind):
        target = ml_resource_class if kind == "class" else ml_resource_class()

        route = app.models.add_model_resource("/", target, tags=tags)

        assert len(app.routes) == 1
        assert isinstance(app.routes[0], ResourceRoute)
        resource_route = app.routes[0]
        assert len(resource_route.routes) == 3
        assert [(r.path, r.methods, r.endpoint, r.tags) for r in resource_route.routes] == [
            ("/", {"HEAD", "GET"}, route.resource.inspect, {"tag": "inspect"}),
            ("/predict/", {"POST"}, route.resource.predict, {"tag": "predict"}),
            ("/stream/", {"POST"}, route.resource.stream, {"tag": "stream"}),
        ]

    def test_model_resource(self, app, ml_resource_class, tags):
        resource = ml_resource_class()

        decorated = app.models.model_resource("/", tags=tags)(resource)

        assert decorated is resource
        assert len(app.routes) == 1
        assert isinstance(app.routes[0], ResourceRoute)
        resource_route = app.routes[0]
        assert len(resource_route.routes) == 3
        assert [(r.path, r.methods, r.endpoint, r.tags) for r in resource_route.routes] == [
            ("/", {"HEAD", "GET"}, resource.inspect, {"tag": "inspect"}),
            ("/predict/", {"POST"}, resource.predict, {"tag": "predict"}),
            ("/stream/", {"POST"}, resource.stream, {"tag": "stream"}),
        ]

    def test_add_llm(self, app, llm_component, llm_tags):
        with patch("flama.models.llm_resource.LLMModelComponentBuilder.load", return_value=llm_component):
            app.models.add_llm("/llm/", model=pathlib.Path("/fake/model.flm"), name="puppy", tags=llm_tags)

        assert len(app.routes) == 1
        assert isinstance(app.routes[0], ResourceRoute)
        resource_route = app.routes[0]
        assert len(resource_route.routes) == 5
        assert [(route.path, route.methods) for route in resource_route.routes] == [
            ("/", {"HEAD", "GET"}),
            ("/", {"PUT"}),
            ("/query/", {"POST"}),
            ("/stream/", {"POST"}),
            ("/chat/", {"HEAD", "GET"}),
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
        assert len(resource_route.routes) == 5
        assert [(route.path, route.methods) for route in resource_route.routes] == [
            ("/", {"HEAD", "GET"}),
            ("/", {"PUT"}),
            ("/query/", {"POST"}),
            ("/stream/", {"POST"}),
            ("/chat/", {"HEAD", "GET"}),
        ]

    @pytest.mark.parametrize(
        ["kind", "has_artifact"],
        [
            pytest.param("class", False, id="class-no-artifact"),
            pytest.param("class", True, id="class-with-artifact"),
            pytest.param("instance", False, id="instance-no-artifact"),
            pytest.param("instance", True, id="instance-with-artifact"),
        ],
    )
    def test_add_llm_resource(self, app, llm_component, llm_resource_class, llm_tags, kind, has_artifact):
        if has_artifact:
            llm_component._artifact = MagicMock()
        target = llm_resource_class if kind == "class" else llm_resource_class()

        app.models.add_llm_resource("/", target, tags=llm_tags)

        assert len(app.routes) == 1
        assert isinstance(app.routes[0], ResourceRoute)
        resource_route = app.routes[0]
        assert len(resource_route.routes) == 5
        assert [(route.path, route.methods) for route in resource_route.routes] == [
            ("/", {"HEAD", "GET"}),
            ("/", {"PUT"}),
            ("/query/", {"POST"}),
            ("/stream/", {"POST"}),
            ("/chat/", {"HEAD", "GET"}),
        ]
        if has_artifact:
            assert app.models._artifacts == [llm_component._artifact]

    def test_llm_resource(self, app, llm_resource_class, llm_tags):
        resource = llm_resource_class()

        decorated = app.models.llm_resource("/", tags=llm_tags)(resource)

        assert decorated is resource
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
