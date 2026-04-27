import pathlib
from unittest.mock import MagicMock, patch

import pytest

from flama.models import LLMResource, LLMResourceType, MLResource, MLResourceType
from flama.resources.routing import ResourceRoute


class TestCaseModelsModule:
    @pytest.fixture(scope="function")
    def ml_tags(self):
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

    @pytest.mark.parametrize(
        ["shape", "expected_routes"],
        [
            pytest.param(
                "ml",
                [
                    ("/", {"HEAD", "GET"}),
                    ("/predict/", {"POST"}),
                    ("/stream/", {"POST"}),
                ],
                id="ml",
            ),
            pytest.param(
                "llm",
                [
                    ("/", {"HEAD", "GET"}),
                    ("/", {"PUT"}),
                    ("/query/", {"POST"}),
                    ("/stream/", {"POST"}),
                ],
                id="llm",
            ),
        ],
    )
    def test_add_model(self, app, component, llm_component, ml_tags, llm_tags, shape, expected_routes):
        if shape == "llm":
            tags = llm_tags
            target_component = llm_component
        else:
            tags = ml_tags
            target_component = component

        with patch("flama.models.modules.ModelComponentBuilder.build", return_value=target_component):
            app.models.add_model("/", model=pathlib.Path("/fake/model.flm"), name="puppy", tags=tags)

        assert len(app.routes) == 1
        assert isinstance(app.routes[0], ResourceRoute)
        resource_route = app.routes[0]
        assert len(resource_route.routes) == len(expected_routes)
        assert [(route.path, route.methods) for route in resource_route.routes] == expected_routes

    @pytest.mark.parametrize(
        ["resource_kind", "shape"],
        [
            pytest.param("class", "ml", id="ml_class"),
            pytest.param("instance", "ml", id="ml_instance"),
            pytest.param("class", "llm", id="llm_class"),
            pytest.param("instance", "llm", id="llm_instance"),
        ],
    )
    def test_add_model_resource(
        self,
        app,
        ml_resource_class,
        llm_resource_class,
        ml_tags,
        llm_tags,
        resource_kind,
        shape,
    ):
        if shape == "llm":
            cls = llm_resource_class
            tags = llm_tags
            expected = [
                ("/", {"HEAD", "GET"}),
                ("/", {"PUT"}),
                ("/query/", {"POST"}),
                ("/stream/", {"POST"}),
            ]
        else:
            cls = ml_resource_class
            tags = ml_tags
            expected = [
                ("/", {"HEAD", "GET"}),
                ("/predict/", {"POST"}),
                ("/stream/", {"POST"}),
            ]

        target = cls if resource_kind == "class" else cls()

        app.models.add_model_resource("/", target, tags=tags)

        assert len(app.routes) == 1
        assert isinstance(app.routes[0], ResourceRoute)
        resource_route = app.routes[0]
        assert len(resource_route.routes) == len(expected)
        assert [(route.path, route.methods) for route in resource_route.routes] == expected

    def test_add_model_resource_artifact_collected(self, app, llm_component, llm_resource_class, llm_tags):
        llm_component._artifact = MagicMock()

        app.models.add_model_resource("/", llm_resource_class, tags=llm_tags)

        assert app.models._artifacts == [llm_component._artifact]

    @pytest.mark.parametrize(
        "shape",
        [
            pytest.param("ml", id="ml"),
            pytest.param("llm", id="llm"),
        ],
    )
    def test_model_resource(self, app, ml_resource_class, llm_resource_class, ml_tags, llm_tags, shape):
        if shape == "llm":
            resource = llm_resource_class()
            tags = llm_tags
            expected = [
                ("/", {"HEAD", "GET"}),
                ("/", {"PUT"}),
                ("/query/", {"POST"}),
                ("/stream/", {"POST"}),
            ]
        else:
            resource = ml_resource_class()
            tags = ml_tags
            expected = [
                ("/", {"HEAD", "GET"}),
                ("/predict/", {"POST"}),
                ("/stream/", {"POST"}),
            ]

        decorated = app.models.model_resource("/", tags=tags)(resource)

        assert decorated is resource
        assert len(app.routes) == 1
        assert isinstance(app.routes[0], ResourceRoute)
        resource_route = app.routes[0]
        assert len(resource_route.routes) == len(expected)
        assert [(route.path, route.methods) for route in resource_route.routes] == expected
