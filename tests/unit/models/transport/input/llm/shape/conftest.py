import typing as t
from unittest.mock import MagicMock

import pytest

from flama.models.engine.backend.llm._base import TransformerLLMBackend
from flama.models.engine.llm.delta import EngineDelta
from flama.models.engine.llm.input import EngineInput
from flama.serialize.data_structures import LLMModelCapabilities


class FakeBackend(TransformerLLMBackend):
    """Minimal :class:`LLMBackend` that records calls and round-trips bytes into IDs.

    Used by every transport test to assert how :meth:`Shape.render` interacts with the underlying
    backend without needing a real model.
    """

    def __init__(
        self,
        *,
        chat_template: str | None = "{{ messages }}",
        capabilities: LLMModelCapabilities | None = None,
    ) -> None:
        super().__init__(None)
        self._chat_template = chat_template
        self.capabilities = capabilities or LLMModelCapabilities()
        self.encode_calls: list[tuple[str, bool]] = []
        self.template_calls: list[list[dict[str, t.Any]]] = []
        self.template_kwargs: list[dict[str, t.Any]] = []

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
        return self._chat_template

    def chat_template_sample(self) -> str | None:
        return None

    def _max_context(self) -> int | None:
        return 8192

    def encode(self, text: str, /, *, add_special_tokens: bool = True) -> list[int]:
        self.encode_calls.append((text, add_special_tokens))
        return [ord(c) for c in text]

    def apply_chat_template(
        self,
        messages: list[dict[str, t.Any]],
        /,
        *,
        tokenize: bool = True,
        add_generation_prompt: bool = True,
        **kwargs: t.Any,
    ) -> list[int]:
        self.template_calls.append(messages)
        self.template_kwargs.append(kwargs)
        rendered = "|".join(f"{m['role']}:{m.get('content', '')}" for m in messages)
        return [ord(c) for c in rendered]

    async def generate(self, inputs: EngineInput, /, **params: t.Any) -> t.AsyncIterator[EngineDelta]:
        if False:
            yield EngineDelta()  # pragma: no cover


class FakeMultimodalBackend(FakeBackend):
    """:class:`FakeBackend` variant whose :attr:`capabilities` advertises image input."""

    def __init__(self, *, chat_template: str | None = "{{ messages }}") -> None:
        super().__init__(
            chat_template=chat_template,
            capabilities=LLMModelCapabilities(text=True, image=True, audio=True),
        )


@pytest.fixture(scope="function")
def backend() -> FakeBackend:
    """A fresh :class:`FakeBackend` per test."""
    return FakeBackend()


@pytest.fixture(scope="function")
def multimodal_backend() -> FakeMultimodalBackend:
    """A fresh :class:`FakeMultimodalBackend` per test (capabilities advertise image+audio)."""
    return FakeMultimodalBackend()


@pytest.fixture(scope="function")
def backend_no_template() -> FakeBackend:
    """A :class:`FakeBackend` whose chat template is missing — used to test the ``ValueError`` path."""
    return FakeBackend(chat_template=None)
