import typing as t
from unittest.mock import MagicMock, patch

import pytest

from flama.models.base import BaseLLMModel, BaseMLModel


@pytest.fixture(scope="function")
def ml_component(request: pytest.FixtureRequest) -> MagicMock:
    spec = getattr(request, "param", BaseMLModel)
    component = MagicMock()
    component.model = MagicMock(spec=spec)
    component.model.inspect.return_value = {"meta": {}, "artifacts": {}}
    if hasattr(spec, "predict"):
        component.model.predict.return_value = [0, 1]
    return component


@pytest.fixture(scope="function")
def llm_component(request: pytest.FixtureRequest) -> MagicMock:
    spec = getattr(request, "param", BaseLLMModel)
    component = MagicMock()
    component.model = MagicMock(spec=spec)
    component.model.inspect.return_value = {"meta": {}, "artifacts": {}}
    if hasattr(spec, "query"):

        async def _query(prompt: str, **params: t.Any) -> str:
            return "Hello world"

        component.model.query = _query
        component.model.params = {}
    return component


@pytest.fixture(scope="function")
def patched_ml_builder(ml_component: MagicMock) -> t.Generator[MagicMock, None, None]:
    with patch("flama._cli.commands.model.ModelComponentBuilder") as builder:
        builder.build.return_value = ml_component
        yield builder


@pytest.fixture(scope="function")
def patched_llm_builder(llm_component: MagicMock) -> t.Generator[MagicMock, None, None]:
    with patch("flama._cli.commands.model.ModelComponentBuilder") as builder:
        builder.build.return_value = llm_component
        yield builder
