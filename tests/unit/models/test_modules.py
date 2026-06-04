import logging
import pathlib
import typing as t
from unittest.mock import call, patch

import pytest

from flama.models import LLMResource, LLMResourceType, MLResource, MLResourceType
from flama.models.engine.llm.decoder.decoder import Decoder, MarkerScanner
from flama.resources.exceptions import ResourceServingLayerUnknown
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
            "create_stream": {"tag": "create_stream"},
            "get_stream": {"tag": "get_stream"},
            "chat": {"tag": "chat"},
            "openai_chat_completions": {"tag": "openai_chat_completions"},
            "openai_completions": {"tag": "openai_completions"},
            "openai_responses": {"tag": "openai_responses"},
            "openai_models": {"tag": "openai_models"},
            "ollama_chat": {"tag": "ollama_chat"},
            "ollama_generate": {"tag": "ollama_generate"},
            "ollama_tags": {"tag": "ollama_tags"},
            "ollama_version": {"tag": "ollama_version"},
            "anthropic_messages": {"tag": "anthropic_messages"},
            "anthropic_models": {"tag": "anthropic_models"},
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
        ["tags_fixture", "component_fixture", "expected_routes"],
        [
            pytest.param(
                "ml_tags",
                "component",
                [
                    ("/", {"HEAD", "GET"}),
                    ("/predict/", {"POST"}),
                    ("/stream/", {"POST"}),
                ],
                id="ml",
            ),
            pytest.param(
                "llm_tags",
                "llm_component",
                [
                    ("/", {"HEAD", "GET"}),
                    ("/", {"PUT"}),
                    ("/query/", {"POST"}),
                    ("/stream/", {"POST"}),
                    ("/stream/{stream_id}/", {"HEAD", "GET"}),
                    ("/chat/", {"HEAD", "GET"}),
                    ("/openai/v1/chat/completions", {"POST"}),
                    ("/openai/v1/completions", {"POST"}),
                    ("/openai/v1/responses", {"POST"}),
                    ("/openai/v1/models", {"HEAD", "GET"}),
                    ("/ollama/api/chat", {"POST"}),
                    ("/ollama/api/generate", {"POST"}),
                    ("/ollama/api/show", {"POST"}),
                    ("/ollama/api/tags", {"HEAD", "GET"}),
                    ("/ollama/api/version", {"HEAD", "GET"}),
                    ("/ollama/v1/chat/completions", {"POST"}),
                    ("/ollama/v1/completions", {"POST"}),
                    ("/ollama/v1/responses", {"POST"}),
                    ("/ollama/v1/models", {"HEAD", "GET"}),
                    ("/anthropic/v1/messages", {"POST"}),
                    ("/anthropic/v1/models", {"HEAD", "GET"}),
                ],
                id="llm",
            ),
        ],
    )
    def test_add_model(
        self,
        app,
        component,
        llm_component,
        ml_tags,
        llm_tags,
        request: pytest.FixtureRequest,
        tags_fixture: str,
        component_fixture: str,
        expected_routes: list[tuple[str, set[str]]],
    ) -> None:
        tags = request.getfixturevalue(tags_fixture)
        target_component = request.getfixturevalue(component_fixture)

        with patch("flama.models.modules.ModelComponentBuilder.build", return_value=target_component) as build:
            app.models.add_model("/", model=pathlib.Path("/fake/model.flm"), name="puppy", tags=tags)

        assert build.call_args_list == [call(pathlib.Path("/fake/model.flm"), name="puppy", decoder=None, params=None)]
        assert len(app.routes) == 1
        assert isinstance(app.routes[0], ResourceRoute)
        resource_route = app.routes[0]
        assert len(resource_route.routes) == len(expected_routes)
        assert [(route.path, route.methods) for route in resource_route.routes] == expected_routes

    @pytest.mark.parametrize(
        "params",
        [
            pytest.param(None, id="default_none"),
            pytest.param({"temperature": 0.7, "max_tokens": 200}, id="explicit_params"),
        ],
    )
    def test_add_model_forwards_params(self, app, llm_component, llm_tags, params):
        with patch("flama.models.modules.ModelComponentBuilder.build", return_value=llm_component) as build:
            kwargs: dict = {"tags": llm_tags}
            if params is not None:
                kwargs["params"] = params
            app.models.add_model("/", model=pathlib.Path("/fake/model.flm"), name="puppy", **kwargs)

        ((_, call_kwargs),) = build.call_args_list
        assert call_kwargs["params"] == params

    @pytest.mark.parametrize(
        ["params", "expected_build_params", "expected_reasoning"],
        [
            pytest.param(
                {"reasoning": False, "temperature": 0.7},
                {"temperature": 0.7},
                False,
                id="reasoning_bool_lifted_off_params",
            ),
            pytest.param(
                {"reasoning": True, "temperature": 0.7},
                {"temperature": 0.7},
                True,
                id="reasoning_true_lifted_off_params",
            ),
            pytest.param(
                {"reasoning_effort": "max", "temperature": 0.7},
                {"reasoning_effort": "max", "temperature": 0.7},
                True,
                id="reasoning_effort_flows_through_unvalidated",
            ),
            pytest.param(
                {"reasoning": False, "reasoning_effort": "low"},
                {"reasoning_effort": "low"},
                False,
                id="reasoning_lifted_and_effort_flows_through",
            ),
        ],
    )
    def test_add_model_routes_reasoning_params(
        self,
        app,
        llm_component,
        llm_tags,
        params: dict[str, t.Any],
        expected_build_params: dict[str, t.Any],
        expected_reasoning: bool,
    ) -> None:
        with patch("flama.models.modules.ModelComponentBuilder.build", return_value=llm_component) as build:
            app.models.add_model("/", model=pathlib.Path("/fake/model.flm"), name="puppy", tags=llm_tags, params=params)

        ((_, call_kwargs),) = build.call_args_list
        assert call_kwargs["params"] == expected_build_params
        assert app.routes[0].resource.reasoning is expected_reasoning

    def test_add_model_rejects_reasoning_for_ml(self, app, component, ml_tags):
        component.model.meta.framework.family = "ml"
        with patch("flama.models.modules.ModelComponentBuilder.build", return_value=component):
            with pytest.raises(ValueError, match="'reasoning' is not supported by family 'ml'"):
                app.models.add_model(
                    "/",
                    model=pathlib.Path("/fake/model.flm"),
                    name="puppy",
                    tags=ml_tags,
                    params={"reasoning": True},
                )

    @pytest.mark.parametrize(
        ["decoder"],
        [
            pytest.param(Decoder("think"), id="registry_string"),
            pytest.param(Decoder(MarkerScanner(name="custom", start="<x>", end="</x>")), id="explicit_scanner"),
        ],
    )
    def test_add_model_passes_decoder(self, app, llm_component, llm_tags, decoder: Decoder):
        with patch("flama.models.modules.ModelComponentBuilder.build", return_value=llm_component) as build:
            app.models.add_model(
                "/", model=pathlib.Path("/fake/model.flm"), name="puppy", tags=llm_tags, decoder=decoder
            )

        ((_, kwargs),) = build.call_args_list
        assert kwargs["decoder"] is decoder

    @pytest.mark.parametrize(
        ["serving", "expected_routes"],
        [
            pytest.param(
                None,
                [
                    ("/", {"HEAD", "GET"}),
                    ("/", {"PUT"}),
                    ("/query/", {"POST"}),
                    ("/stream/", {"POST"}),
                    ("/stream/{stream_id}/", {"HEAD", "GET"}),
                    ("/chat/", {"HEAD", "GET"}),
                    ("/openai/v1/chat/completions", {"POST"}),
                    ("/openai/v1/completions", {"POST"}),
                    ("/openai/v1/responses", {"POST"}),
                    ("/openai/v1/models", {"HEAD", "GET"}),
                    ("/ollama/api/chat", {"POST"}),
                    ("/ollama/api/generate", {"POST"}),
                    ("/ollama/api/show", {"POST"}),
                    ("/ollama/api/tags", {"HEAD", "GET"}),
                    ("/ollama/api/version", {"HEAD", "GET"}),
                    ("/ollama/v1/chat/completions", {"POST"}),
                    ("/ollama/v1/completions", {"POST"}),
                    ("/ollama/v1/responses", {"POST"}),
                    ("/ollama/v1/models", {"HEAD", "GET"}),
                    ("/anthropic/v1/messages", {"POST"}),
                    ("/anthropic/v1/models", {"HEAD", "GET"}),
                ],
                id="default",
            ),
            pytest.param(
                ("native",),
                [
                    ("/", {"HEAD", "GET"}),
                    ("/", {"PUT"}),
                    ("/query/", {"POST"}),
                    ("/stream/", {"POST"}),
                    ("/stream/{stream_id}/", {"HEAD", "GET"}),
                    ("/chat/", {"HEAD", "GET"}),
                ],
                id="explicit_native",
            ),
            pytest.param(
                ("openai",),
                [
                    ("/openai/v1/chat/completions", {"POST"}),
                    ("/openai/v1/completions", {"POST"}),
                    ("/openai/v1/responses", {"POST"}),
                    ("/openai/v1/models", {"HEAD", "GET"}),
                ],
                id="explicit_openai",
            ),
            pytest.param(
                ("native", "openai"),
                [
                    ("/", {"HEAD", "GET"}),
                    ("/", {"PUT"}),
                    ("/query/", {"POST"}),
                    ("/stream/", {"POST"}),
                    ("/stream/{stream_id}/", {"HEAD", "GET"}),
                    ("/chat/", {"HEAD", "GET"}),
                    ("/openai/v1/chat/completions", {"POST"}),
                    ("/openai/v1/completions", {"POST"}),
                    ("/openai/v1/responses", {"POST"}),
                    ("/openai/v1/models", {"HEAD", "GET"}),
                ],
                id="native_and_openai",
            ),
            pytest.param(
                ("ollama",),
                [
                    ("/ollama/api/chat", {"POST"}),
                    ("/ollama/api/generate", {"POST"}),
                    ("/ollama/api/show", {"POST"}),
                    ("/ollama/api/tags", {"HEAD", "GET"}),
                    ("/ollama/api/version", {"HEAD", "GET"}),
                    ("/ollama/v1/chat/completions", {"POST"}),
                    ("/ollama/v1/completions", {"POST"}),
                    ("/ollama/v1/responses", {"POST"}),
                    ("/ollama/v1/models", {"HEAD", "GET"}),
                ],
                id="explicit_ollama",
            ),
            pytest.param(
                ("anthropic",),
                [
                    ("/anthropic/v1/messages", {"POST"}),
                    ("/anthropic/v1/models", {"HEAD", "GET"}),
                ],
                id="explicit_anthropic",
            ),
        ],
    )
    def test_add_model_forwards_serving(
        self,
        app,
        llm_component,
        llm_tags,
        serving: tuple[str, ...] | None,
        expected_routes: list[tuple[str, set[str]]],
    ) -> None:
        with patch("flama.models.modules.ModelComponentBuilder.build", return_value=llm_component):
            kwargs: dict = {}
            if serving is not None:
                kwargs["serving"] = serving
            app.models.add_model("/", model=pathlib.Path("/fake/model.flm"), name="puppy", **kwargs)

        resource_route = app.routes[0]
        assert isinstance(resource_route, ResourceRoute)
        assert [(route.path, route.methods) for route in resource_route.routes] == expected_routes

    def test_add_model_rejects_unknown_serving(self, app, llm_component, llm_tags) -> None:
        with patch("flama.models.modules.ModelComponentBuilder.build", return_value=llm_component):
            with pytest.raises(ResourceServingLayerUnknown, match=r"unknown serving layer\(s\)"):
                app.models.add_model(
                    "/",
                    model=pathlib.Path("/fake/model.flm"),
                    name="puppy",
                    tags=llm_tags,
                    serving=("bogus",),
                )

    def test_add_model_logs_breadcrumb(self, app, component, ml_tags, caplog_flama: pytest.LogCaptureFixture) -> None:
        component.model.meta.framework.family = "ml"
        with (
            patch("flama.models.modules.ModelComponentBuilder.build", return_value=component),
            caplog_flama.at_level(logging.INFO, logger="flama.models.modules"),
        ):
            app.models.add_model("/", model=pathlib.Path("/fake/model.flm"), name="puppy", tags=ml_tags)

        messages = [r.getMessage() for r in caplog_flama.records if r.name == "flama.models.modules"]
        assert any("Adding model 'puppy'" in m and "/fake/model.flm" in m and "family=ml" in m for m in messages)

    def test_add_model_resource_tracks_component_for_startup(self, app, llm_resource_class, llm_tags) -> None:
        before = list(app.models._components)

        app.models.add_model_resource("/", llm_resource_class, tags=llm_tags)

        added = [c for c in app.models._components if c not in before]
        assert added == [llm_resource_class.component]

    async def test_on_startup_materialises_registered_components(
        self, app, llm_component, llm_resource_class, llm_tags
    ) -> None:
        calls: list[str] = []

        async def _startup() -> None:
            calls.append("started")

        llm_component.startup = _startup

        app.models.add_model_resource("/", llm_resource_class, tags=llm_tags)
        await app.models.on_startup()

        assert calls == ["started"]

    @pytest.mark.parametrize(
        ["resource_factory", "resource_class_fixture", "tags_fixture", "expected"],
        [
            pytest.param(
                lambda cls: cls,
                "ml_resource_class",
                "ml_tags",
                [
                    ("/", {"HEAD", "GET"}),
                    ("/predict/", {"POST"}),
                    ("/stream/", {"POST"}),
                ],
                id="ml_class",
            ),
            pytest.param(
                lambda cls: cls(),
                "ml_resource_class",
                "ml_tags",
                [
                    ("/", {"HEAD", "GET"}),
                    ("/predict/", {"POST"}),
                    ("/stream/", {"POST"}),
                ],
                id="ml_instance",
            ),
            pytest.param(
                lambda cls: cls,
                "llm_resource_class",
                "llm_tags",
                [
                    ("/", {"HEAD", "GET"}),
                    ("/", {"PUT"}),
                    ("/query/", {"POST"}),
                    ("/stream/", {"POST"}),
                    ("/stream/{stream_id}/", {"HEAD", "GET"}),
                    ("/chat/", {"HEAD", "GET"}),
                    ("/openai/v1/chat/completions", {"POST"}),
                    ("/openai/v1/completions", {"POST"}),
                    ("/openai/v1/responses", {"POST"}),
                    ("/openai/v1/models", {"HEAD", "GET"}),
                    ("/ollama/api/chat", {"POST"}),
                    ("/ollama/api/generate", {"POST"}),
                    ("/ollama/api/show", {"POST"}),
                    ("/ollama/api/tags", {"HEAD", "GET"}),
                    ("/ollama/api/version", {"HEAD", "GET"}),
                    ("/ollama/v1/chat/completions", {"POST"}),
                    ("/ollama/v1/completions", {"POST"}),
                    ("/ollama/v1/responses", {"POST"}),
                    ("/ollama/v1/models", {"HEAD", "GET"}),
                    ("/anthropic/v1/messages", {"POST"}),
                    ("/anthropic/v1/models", {"HEAD", "GET"}),
                ],
                id="llm_class",
            ),
            pytest.param(
                lambda cls: cls(),
                "llm_resource_class",
                "llm_tags",
                [
                    ("/", {"HEAD", "GET"}),
                    ("/", {"PUT"}),
                    ("/query/", {"POST"}),
                    ("/stream/", {"POST"}),
                    ("/stream/{stream_id}/", {"HEAD", "GET"}),
                    ("/chat/", {"HEAD", "GET"}),
                    ("/openai/v1/chat/completions", {"POST"}),
                    ("/openai/v1/completions", {"POST"}),
                    ("/openai/v1/responses", {"POST"}),
                    ("/openai/v1/models", {"HEAD", "GET"}),
                    ("/ollama/api/chat", {"POST"}),
                    ("/ollama/api/generate", {"POST"}),
                    ("/ollama/api/show", {"POST"}),
                    ("/ollama/api/tags", {"HEAD", "GET"}),
                    ("/ollama/api/version", {"HEAD", "GET"}),
                    ("/ollama/v1/chat/completions", {"POST"}),
                    ("/ollama/v1/completions", {"POST"}),
                    ("/ollama/v1/responses", {"POST"}),
                    ("/ollama/v1/models", {"HEAD", "GET"}),
                    ("/anthropic/v1/messages", {"POST"}),
                    ("/anthropic/v1/models", {"HEAD", "GET"}),
                ],
                id="llm_instance",
            ),
        ],
    )
    def test_add_model_resource(
        self,
        app,
        ml_resource_class,
        llm_resource_class,
        ml_tags,
        llm_tags,
        request: pytest.FixtureRequest,
        resource_factory,
        resource_class_fixture: str,
        tags_fixture: str,
        expected: list[tuple[str, set[str]]],
    ) -> None:
        cls = request.getfixturevalue(resource_class_fixture)
        tags = request.getfixturevalue(tags_fixture)
        target = resource_factory(cls)

        app.models.add_model_resource("/", target, tags=tags)

        assert len(app.routes) == 1
        assert isinstance(app.routes[0], ResourceRoute)
        resource_route = app.routes[0]
        assert len(resource_route.routes) == len(expected)
        assert [(route.path, route.methods) for route in resource_route.routes] == expected

    @pytest.mark.parametrize(
        ["resource_class_fixture", "tags_fixture", "expected"],
        [
            pytest.param(
                "ml_resource_class",
                "ml_tags",
                [
                    ("/", {"HEAD", "GET"}),
                    ("/predict/", {"POST"}),
                    ("/stream/", {"POST"}),
                ],
                id="ml",
            ),
            pytest.param(
                "llm_resource_class",
                "llm_tags",
                [
                    ("/", {"HEAD", "GET"}),
                    ("/", {"PUT"}),
                    ("/query/", {"POST"}),
                    ("/stream/", {"POST"}),
                    ("/stream/{stream_id}/", {"HEAD", "GET"}),
                    ("/chat/", {"HEAD", "GET"}),
                    ("/openai/v1/chat/completions", {"POST"}),
                    ("/openai/v1/completions", {"POST"}),
                    ("/openai/v1/responses", {"POST"}),
                    ("/openai/v1/models", {"HEAD", "GET"}),
                    ("/ollama/api/chat", {"POST"}),
                    ("/ollama/api/generate", {"POST"}),
                    ("/ollama/api/show", {"POST"}),
                    ("/ollama/api/tags", {"HEAD", "GET"}),
                    ("/ollama/api/version", {"HEAD", "GET"}),
                    ("/ollama/v1/chat/completions", {"POST"}),
                    ("/ollama/v1/completions", {"POST"}),
                    ("/ollama/v1/responses", {"POST"}),
                    ("/ollama/v1/models", {"HEAD", "GET"}),
                    ("/anthropic/v1/messages", {"POST"}),
                    ("/anthropic/v1/models", {"HEAD", "GET"}),
                ],
                id="llm",
            ),
        ],
    )
    def test_model_resource(
        self,
        app,
        ml_resource_class,
        llm_resource_class,
        ml_tags,
        llm_tags,
        request: pytest.FixtureRequest,
        resource_class_fixture: str,
        tags_fixture: str,
        expected: list[tuple[str, set[str]]],
    ) -> None:
        resource = request.getfixturevalue(resource_class_fixture)()
        tags = request.getfixturevalue(tags_fixture)

        decorated = app.models.model_resource("/", tags=tags)(resource)

        assert decorated is resource
        assert len(app.routes) == 1
        assert isinstance(app.routes[0], ResourceRoute)
        resource_route = app.routes[0]
        assert len(resource_route.routes) == len(expected)
        assert [(route.path, route.methods) for route in resource_route.routes] == expected
