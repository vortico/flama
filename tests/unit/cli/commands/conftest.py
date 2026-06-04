import typing as t
from unittest.mock import MagicMock, patch

import pytest

from flama.models.base import LLMModel, MLModel
from flama.models.transport.output.llm.event import TextEvent


@pytest.fixture(scope="function")
def ml_component(request: pytest.FixtureRequest) -> MagicMock:
    spec = getattr(request, "param", MLModel)
    component = MagicMock()
    component.model = MagicMock(spec=spec)
    component.model.inspect.return_value = {"meta": {}, "manifest": []}
    if hasattr(spec, "predict"):
        component.model.predict.return_value = [0, 1]
    return component


@pytest.fixture(scope="function")
def llm_component(request: pytest.FixtureRequest) -> MagicMock:
    spec = getattr(request, "param", LLMModel)
    component = MagicMock()
    component.model = MagicMock(spec=spec)
    component.model.inspect.return_value = {"meta": {}, "manifest": []}
    if hasattr(spec, "query"):

        async def _query(prompt: str | None = None, /, **kwargs: t.Any) -> list[TextEvent]:
            return [TextEvent(channel="output", text="Hello world")]

        component.model.query = _query
        component.model.params = {}
        component.model.default_transport = "chat"
    return component


@pytest.fixture(scope="function")
def patched_ml_builder(ml_component: MagicMock) -> t.Generator[MagicMock, None, None]:
    meta = MagicMock()
    meta.framework.family = "ml"
    with (
        patch("flama._cli.commands.model.ModelComponentBuilder") as builder,
        patch("flama.serialize.serializer.Serializer.meta", return_value=meta),
    ):
        builder.build.return_value = ml_component
        yield builder


@pytest.fixture(scope="function")
def patched_llm_builder(llm_component: MagicMock) -> t.Generator[MagicMock, None, None]:
    meta = MagicMock()
    meta.framework.family = "llm"
    with (
        patch("flama._cli.commands.model.ModelComponentBuilder") as builder,
        patch("flama.serialize.serializer.Serializer.meta", return_value=meta),
    ):
        builder.build.return_value = llm_component
        yield builder
