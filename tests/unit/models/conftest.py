import typing as t
from unittest.mock import MagicMock, Mock

import pytest

from flama import Flama
from flama.injection import Parameter
from flama.models import ModelComponent
from flama.models.base import LLMModel, MLModel
from flama.models.engine.backend.llm.base import TransformerLLMBackend
from flama.models.engine.backend.ml.base import MLBackend
from flama.models.engine.llm.delta import EngineDelta
from flama.models.engine.llm.input import EngineInput


class _StubMLBackend(MLBackend):
    """Deterministic ML backend used by integration tests."""

    def predict(self, x: t.Iterable[t.Iterable[t.Any]], /) -> t.Any:
        return [list(item)[0] for item in x]


class _StubLLMBackend(TransformerLLMBackend):
    """Deterministic LLM backend used by integration tests.

    The fake encoder maps bytes to IDs and back, so the rendered prompt round-trips losslessly; tokens are
    emitted as space-separated words from the rendered prompt.
    """

    @classmethod
    def runnable(cls) -> bool:
        return True

    @property
    def _tokenizer(self) -> t.Any:
        return MagicMock()

    @property
    def _renderer(self) -> t.Any:
        return MagicMock()

    @property
    def chat_template(self) -> str | None:
        return "{% for m in messages %}{{ m.role }}: {{ m.content }}\n{% endfor %}"

    def chat_template_sample(self) -> str | None:
        return None

    def _max_context(self) -> int | None:
        return 8192

    def encode(self, text: str, /, *, add_special_tokens: bool = True) -> list[int]:
        return [ord(c) for c in text]

    def apply_chat_template(
        self,
        messages: list[dict[str, t.Any]],
        /,
        *,
        add_generation_prompt: bool = True,
        **kwargs: t.Any,
    ) -> list[int]:
        rendered = "".join(f"{m['role']}: {m['content']}\n" for m in messages)
        return [ord(c) for c in rendered]

    async def generate(self, inputs: EngineInput, /, **params: t.Any) -> t.AsyncIterator[EngineDelta]:
        prompt = "".join(chr(i) for i in inputs.tokens)
        for token in prompt.split():
            yield EngineDelta(text=token, token_count=1)
        yield EngineDelta(finish_reason="stop")


@pytest.fixture(scope="function")
def app():
    return Flama(schema=None, docs=None)


@pytest.fixture(
    scope="function",
    params=[
        pytest.param("tensorflow", id="tensorflow"),
        pytest.param("sklearn", id="sklearn"),
        pytest.param("torch", id="torch"),
    ],
)
def model(request):
    backend = _StubMLBackend(Mock())
    return MLModel(backend, Mock(), Mock())


@pytest.fixture(scope="function")
def component(model):
    class SpecificModelComponent(ModelComponent):
        def can_handle_parameter(self, parameter: Parameter) -> bool:
            return parameter.annotation == type(model)

    return SpecificModelComponent(model)


@pytest.fixture(scope="function")
def llm_model():
    meta = Mock()
    meta.to_dict.return_value = {
        "id": "stub-id",
        "timestamp": "2024-01-01T00:00:00Z",
        "model": {"obj": None, "info": None, "params": {}, "metrics": {}},
        "framework": {"family": "llm", "lib": "transformers", "version": "0.0.0", "config": None},
        "extra": {},
    }
    backend = _StubLLMBackend(object())
    return LLMModel(backend, meta, None)


@pytest.fixture(scope="function")
def llm_component(llm_model):
    class SpecificModelComponent(ModelComponent):
        def can_handle_parameter(self, parameter: Parameter) -> bool:
            return parameter.annotation == type(llm_model)

    return SpecificModelComponent(llm_model)
