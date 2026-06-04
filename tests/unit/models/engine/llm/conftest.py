import typing as t
from unittest.mock import MagicMock

import pytest

from flama.models.engine.backend.llm.base import LLMBackend, TransformerLLMBackend
from flama.models.engine.llm.codec import LLMCodec
from flama.models.engine.llm.decoder.decoder import ChannelPolicy, Decoder
from flama.models.engine.llm.decoder.markers import PassthroughScanner, Scanner
from flama.models.engine.llm.decoder.parsers import PassthroughParser, ToolParser
from flama.models.engine.llm.delta import EngineDelta
from flama.models.engine.llm.input import EngineInput
from flama.models.transport.output.llm.event import Event, TraceEvent


class FakeLLMBackend(TransformerLLMBackend):
    """Minimal :class:`LLMBackend` stub driving both engine-side detection hooks.

    Tracks ``chat_template_sample`` and ``generate`` invocations so tests can assert which stage of the
    three-stage detection cascade ran. Each construction kwarg models one branch of the engine's behaviour
    (raise on chat-template introspection, raise mid-generation, etc.).
    """

    _UNSET: t.ClassVar[t.Any] = object()

    def __init__(
        self,
        *,
        chunks: t.Sequence[str] = (),
        chat_template: str | None = "{{ messages }}",
        chat_template_sample: t.Any = _UNSET,
        raise_on_generate: BaseException | None = None,
        raise_on_chat_template_sample: BaseException | None = None,
    ) -> None:
        super().__init__(None)
        self._chat_template = chat_template
        self._chat_template_sample: str | None = (
            chat_template if chat_template_sample is self._UNSET else chat_template_sample
        )
        self._raise_on_chat_template_sample = raise_on_chat_template_sample
        self._chunks = list(chunks)
        self._raise = raise_on_generate
        self.generate_calls: list[tuple[list[int], dict[str, t.Any]]] = []
        self.chat_template_sample_calls: int = 0

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
        self.chat_template_sample_calls += 1
        if self._raise_on_chat_template_sample is not None:
            raise self._raise_on_chat_template_sample
        return self._chat_template_sample

    def _max_context(self) -> int | None:
        return 8192

    def encode(self, text: str, /, *, add_special_tokens: bool = True) -> list[int]:
        return [1, 2, 3]

    def apply_chat_template(
        self, messages: list[dict[str, t.Any]], /, *, add_generation_prompt: bool = True, **kwargs: t.Any
    ) -> list[int]:
        return [10, 20, 30]

    async def generate(self, inputs: EngineInput, /, **params: t.Any) -> t.AsyncIterator[EngineDelta]:
        self.generate_calls.append((list(inputs.tokens), params))
        if self._raise is not None:
            raise self._raise
        for chunk in self._chunks:
            yield EngineDelta(text=chunk)


class FakeModel:
    """Bare LLM-model facade exposing only ``backend`` so it satisfies :meth:`LLMCodec.detect`."""

    def __init__(self, backend: LLMBackend | None) -> None:
        self.backend = backend


async def aiter(items: t.Iterable[EngineDelta]) -> t.AsyncIterator[EngineDelta]:
    """Wrap *items* into an async iterator suitable for :meth:`LLMCodec.decode`."""
    for item in items:
        yield item


async def consume(stream: t.AsyncIterator[Event | TraceEvent]) -> list[Event | TraceEvent]:
    """Materialise the full content of *stream*."""
    return [item async for item in stream]


def make_engine(
    *,
    channel_scanner: Scanner | None = None,
    tool_scanner: Scanner | None = None,
    tool_parser: ToolParser | None = None,
    policy: ChannelPolicy | None = None,
) -> LLMCodec:
    """Build a :class:`LLMCodec` pre-resolved with the supplied (or passthrough) slots.

    Bypasses ``detect`` so tests focused on ``decode`` can avoid backend wiring.
    """
    decoder = Decoder(
        channel_scanner or PassthroughScanner(),
        tool_scanner or PassthroughScanner(),
        tool_parser or PassthroughParser(),
        policy=policy or ChannelPolicy(),
    )
    engine = LLMCodec(decoder)
    engine.decoder = decoder.resolve()
    return engine


@pytest.fixture(scope="function")
def fake_backend() -> FakeLLMBackend:
    """Default :class:`FakeLLMBackend` with no chunks and a generic chat template sample."""
    return FakeLLMBackend()


@pytest.fixture(scope="function")
def fake_model(fake_backend: FakeLLMBackend) -> FakeModel:
    return FakeModel(fake_backend)
