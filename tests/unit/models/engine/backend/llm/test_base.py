import dataclasses
import typing as t
from unittest.mock import AsyncMock, MagicMock, call, patch

import numpy as np
import pytest

from flama import exceptions
from flama.models.engine.backend.llm._base import LLMBackend, TransformerLLMBackend
from flama.models.engine.llm.delta import EngineDelta
from flama.models.engine.llm.input import EngineInput
from flama.models.exceptions import LLMUnsupportedCapability
from flama.models.transport.input.llm.message import (
    AssistantMessage,
    AudioContent,
    AudioURI,
    ImageContent,
    ImageURI,
    Message,
    SourceURI,
    SystemMessage,
    TextContent,
    ToolCall,
    ToolMessage,
    UserMessage,
)
from flama.models.transport.input.llm.tool import Tool
from flama.serialize.data_structures import LLMModelCapabilities


class _FakeLLMBackend(TransformerLLMBackend):
    """Minimal concrete :class:`LLMBackend` exposing a configurable chat template and capabilities."""

    def __init__(self, *, chat_template: str | None, capabilities: LLMModelCapabilities | None = None) -> None:
        super().__init__(None)
        self._chat_template = chat_template
        self.capabilities = capabilities or LLMModelCapabilities()
        self.template_calls: list[tuple[list[dict[str, t.Any]], dict[str, t.Any]]] = []

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

    def encode(self, text: str, /, *, add_special_tokens: bool = True) -> list[int]:
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
        self.template_calls.append((messages, kwargs))
        return [len(messages)]

    def chat_template_sample(self) -> str | None:
        return None

    def _max_context(self) -> int | None:
        return 8192

    async def generate(  # pragma: no cover
        self, inputs: EngineInput, /, **params: t.Any
    ) -> t.AsyncIterator[EngineDelta]:
        yield EngineDelta()


def _stub_image() -> ImageURI:
    """Build an :class:`ImageURI` with a placeholder base64 payload (``"AAAA"`` = 3 null bytes)."""
    return ImageURI(source=SourceURI(data="AAAA"), format="png")


def _stub_audio() -> AudioURI:
    """Build an :class:`AudioURI` with a placeholder base64 payload (``"AAAA"`` = 3 null bytes)."""
    return AudioURI(source=SourceURI(data="AAAA"), format="wav")


_AUDIO_SENTINEL = (np.zeros(8, dtype=np.float32), 16000)


class TestCaseEngineDelta:
    """Cover the :class:`EngineDelta` data carrier."""

    @pytest.mark.parametrize(
        ["kwargs", "expected_text", "expected_token_count", "expected_finish_reason"],
        [
            pytest.param({}, "", None, None, id="defaults"),
            pytest.param({"text": "hello", "token_count": 1}, "hello", 1, None, id="text_and_token_count"),
            pytest.param({"text": "", "token_count": 5, "finish_reason": "stop"}, "", 5, "stop", id="terminal_trace"),
            pytest.param({"text": "partial"}, "partial", None, None, id="text_only"),
            pytest.param({"finish_reason": "length"}, "", None, "length", id="length_finish"),
            pytest.param({"finish_reason": "tool_calls"}, "", None, "tool_calls", id="tool_calls_finish"),
        ],
    )
    def test_init(
        self,
        kwargs: dict[str, t.Any],
        expected_text: str,
        expected_token_count: int | None,
        expected_finish_reason: str | None,
    ) -> None:
        delta = EngineDelta(**kwargs)

        assert delta.text == expected_text
        assert delta.token_count == expected_token_count
        assert delta.finish_reason == expected_finish_reason

    def test_is_frozen(self) -> None:
        delta = EngineDelta(text="hi")

        with pytest.raises(dataclasses.FrozenInstanceError):
            delta.text = "bye"  # type: ignore[misc]


class TestCaseEngineInput:
    """Cover the :class:`EngineInput` data carrier."""

    @pytest.mark.parametrize(
        ["tokens", "images", "audios"],
        [
            pytest.param([1, 2, 3], (), (), id="defaults"),
            pytest.param([1], ("pil-sentinel",), ((None, 16000),), id="multimodal"),
        ],
    )
    def test_init(self, tokens: list[int], images: tuple, audios: tuple) -> None:
        inputs = EngineInput(tokens=tokens, images=t.cast(t.Any, images), audios=t.cast(t.Any, audios))

        assert inputs.tokens == tokens
        assert inputs.images == images
        assert inputs.audios == audios

    def test_is_frozen(self) -> None:
        inputs = EngineInput(tokens=[1])

        with pytest.raises(dataclasses.FrozenInstanceError):
            inputs.tokens = [2]  # type: ignore[misc]


class TestCaseLLMBackend:
    """Cover concrete behaviour exposed by :class:`LLMBackend` (default transport selection,
    context-window probing, ``max_tokens`` resolution, multimodal-aware ``prepare_input`` walk,
    backend-registry resolution, and the artifact-driven constructor)."""

    @pytest.fixture(scope="function")
    def backend(self) -> _FakeLLMBackend:
        """Backend with a deterministic 2048-token context window so ``_resolve_max_tokens``
        arithmetic is checkable from raw deltas without re-stubbing per case.
        """
        backend = _FakeLLMBackend(chat_template="{{ messages }}")
        backend._max_context = lambda: 2048  # type: ignore[method-assign]
        return backend

    @pytest.mark.parametrize(
        ["chat_template", "expected"],
        [
            pytest.param("{{ messages }}", "chat", id="instruction_tuned"),
            pytest.param("", "chat", id="empty_template_still_chat"),
            pytest.param(None, "raw", id="base_model"),
        ],
    )
    def test_default_transport(self, chat_template: str | None, expected: str) -> None:
        backend = _FakeLLMBackend(chat_template=chat_template)

        assert backend.default_transport == expected

    def test_chat_template_sample_default_is_none(self) -> None:
        backend = _FakeLLMBackend(chat_template=None)

        assert LLMBackend.chat_template_sample(backend) is None

    def test_default_capabilities_is_text_only(self) -> None:
        """The default :attr:`LLMBackend.capabilities` is the empty :class:`LLMModelCapabilities`,
        which behaves as text-only (every modality flag :data:`False`).
        """
        backend = _FakeLLMBackend(chat_template=None)

        assert backend.capabilities == LLMModelCapabilities()

    @pytest.mark.parametrize(
        ["probe_value", "expected_uses_default", "expects_warning"],
        [
            pytest.param(2048, False, False, id="positive_uses_probed_value"),
            pytest.param(None, True, True, id="none_falls_back_to_default"),
            pytest.param(0, True, True, id="zero_falls_back_to_default"),
            pytest.param(-1, True, True, id="negative_falls_back_to_default"),
        ],
    )
    def test_max_context(
        self,
        probe_value: int | None,
        expected_uses_default: bool,
        expects_warning: bool,
        caplog_flama,
    ) -> None:
        """Verify :attr:`LLMBackend.max_context` reads through ``_max_context``, replaces non-positive
        / :data:`None` probes with :attr:`DEFAULT_MAX_TOKENS` (with a warning log), and caches the
        resolved value so the probe runs at most once across repeated reads.
        """
        calls: list[None] = []

        def probe() -> int | None:
            calls.append(None)
            return probe_value

        backend = _FakeLLMBackend(chat_template="{{ messages }}")
        backend._max_context = probe  # type: ignore[method-assign]

        with caplog_flama.at_level("WARNING", logger="flama.models.engine.backend.llm._base"):
            first = backend.max_context
            second = backend.max_context

        expected_value = _FakeLLMBackend.DEFAULT_MAX_TOKENS if expected_uses_default else probe_value
        assert first == expected_value
        assert second == expected_value
        assert len(calls) == 1
        warned = any("Cannot determine model context window" in record.message for record in caplog_flama.records)
        assert warned is expects_warning

    @pytest.mark.parametrize(
        ["params", "prompt_tokens", "expected", "exception"],
        [
            pytest.param(
                {"temperature": 0.5},
                128,
                2048 - 128,
                None,
                id="absent_resolves_to_max_context_minus_prompt",
            ),
            pytest.param({"max_tokens": None}, 10, 2048 - 10, None, id="none_resolves_to_max_context_minus_prompt"),
            pytest.param({"max_tokens": 64}, 10, 64, None, id="explicit_positive_int_passes_through"),
            pytest.param({"max_new_tokens": 128}, 10, 128, None, id="max_new_tokens_alias_is_accepted"),
            # A prompt longer than the context should not produce 0 / negative max_tokens — the
            # engine would either reject it or generate garbage; clamping to 1 keeps the contract sane.
            pytest.param({}, 10_000, 1, None, id="floor_of_one_when_prompt_exceeds_context"),
            pytest.param(
                {"max_tokens": 0},
                10,
                None,
                ValueError("max_tokens must be a positive integer"),
                id="zero_raises",
            ),
            pytest.param(
                {"max_tokens": -1},
                10,
                None,
                ValueError("max_tokens must be a positive integer"),
                id="negative_raises",
            ),
            pytest.param(
                {"max_tokens": -100},
                10,
                None,
                ValueError("max_tokens must be a positive integer"),
                id="large_negative_raises",
            ),
            pytest.param(
                {"max_tokens": "256"},
                10,
                None,
                ValueError("max_tokens must be a positive integer"),
                id="str_raises",
            ),
            pytest.param(
                {"max_tokens": 256.0},
                10,
                None,
                ValueError("max_tokens must be a positive integer"),
                id="float_raises",
            ),
            pytest.param(
                {"max_tokens": [256]},
                10,
                None,
                ValueError("max_tokens must be a positive integer"),
                id="list_raises",
            ),
        ],
        indirect=["exception"],
    )
    def test_resolve_max_tokens(
        self,
        backend: _FakeLLMBackend,
        params: dict[str, t.Any],
        prompt_tokens: int,
        expected: int | None,
        exception,
    ) -> None:
        """Cover the full :meth:`LLMBackend._resolve_max_tokens` contract: missing key falls back to
        ``max_context - prompt_tokens``, the legacy ``max_new_tokens`` alias is honoured, prompts
        bigger than the context clamp to 1, and non-positive / non-int values raise.
        """
        with exception:
            resolved = backend._resolve_max_tokens(params, prompt_tokens)

        if not exception:
            assert resolved == expected
            assert "max_tokens" not in params and "max_new_tokens" not in params

    @pytest.mark.parametrize(
        [
            "capabilities",
            "messages",
            "extra_call_kwargs",
            "expected_template_messages",
            "expected_template_kwargs",
            "expected_images",
            "expected_audios",
            "exception",
        ],
        [
            pytest.param(
                LLMModelCapabilities(),
                [UserMessage(content=(TextContent(text="hi"),))],
                {},
                [{"role": "user", "content": "hi"}],
                {},
                (),
                (),
                None,
                id="text_only",
            ),
            pytest.param(
                LLMModelCapabilities(image=True),
                [
                    SystemMessage(content=(TextContent(text="ignored"),)),
                    UserMessage(content=(TextContent(text="what is this?"), _stub_image())),
                ],
                {},
                [
                    {"role": "system", "content": "ignored"},
                    {"role": "user", "content": [{"type": "text", "text": "what is this?"}, {"type": "image"}]},
                ],
                {},
                ("img-sentinel",),
                (),
                None,
                id="image_rewrite",
            ),
            pytest.param(
                LLMModelCapabilities(audio=True),
                [UserMessage(content=(TextContent(text="transcribe"), _stub_audio()))],
                {},
                [{"role": "user", "content": [{"type": "text", "text": "transcribe"}, {"type": "audio"}]}],
                {},
                (),
                (_AUDIO_SENTINEL,),
                None,
                id="audio_rewrite",
            ),
            pytest.param(
                LLMModelCapabilities(image=True, audio=True),
                [UserMessage(content=(TextContent(text="both"), _stub_image(), _stub_audio()))],
                {},
                [{"role": "user", "content": [{"type": "text", "text": "both"}, {"type": "image"}, {"type": "audio"}]}],
                {},
                ("img-sentinel",),
                (_AUDIO_SENTINEL,),
                None,
                id="mixed_image_and_audio",
            ),
            pytest.param(
                LLMModelCapabilities(image=True, audio=True),
                [UserMessage(content=(TextContent(text="hi"),))],
                {},
                [{"role": "user", "content": "hi"}],
                {},
                (),
                (),
                None,
                id="text_only_skips_multimodal_payload",
            ),
            pytest.param(
                LLMModelCapabilities(),
                [UserMessage(content=(TextContent(text="what is this?"), _stub_image()))],
                {},
                None,
                None,
                None,
                None,
                LLMUnsupportedCapability("image"),
                id="image_rejected_on_text_only_backend",
            ),
            pytest.param(
                LLMModelCapabilities(),
                [UserMessage(content=(TextContent(text="transcribe"), _stub_audio()))],
                {},
                None,
                None,
                None,
                None,
                LLMUnsupportedCapability("audio"),
                id="audio_rejected_on_text_only_backend",
            ),
            pytest.param(
                LLMModelCapabilities(image=True),
                [UserMessage(content=(_stub_audio(),))],
                {},
                None,
                None,
                None,
                None,
                LLMUnsupportedCapability("audio"),
                id="audio_rejected_on_image_only_backend",
            ),
            pytest.param(
                LLMModelCapabilities(audio=True),
                [UserMessage(content=(_stub_image(),))],
                {},
                None,
                None,
                None,
                None,
                LLMUnsupportedCapability("image"),
                id="image_rejected_on_audio_only_backend",
            ),
            pytest.param(
                LLMModelCapabilities(),
                [UserMessage(content=(TextContent(text="hi"),))],
                {
                    "tools": [Tool(name="f", parameters={})],
                    "chat_template_kwargs": {"enable_thinking": False},
                },
                [{"role": "user", "content": "hi"}],
                {
                    "enable_thinking": False,
                    "tools": [{"type": "function", "function": {"name": "f", "parameters": {}}}],
                },
                (),
                (),
                None,
                id="forwards_tools_and_kwargs",
            ),
        ],
        indirect=["exception"],
    )
    async def test_prepare_input(
        self,
        capabilities: LLMModelCapabilities,
        messages: list[Message],
        extra_call_kwargs: dict[str, t.Any],
        expected_template_messages: list[dict[str, t.Any]] | None,
        expected_template_kwargs: dict[str, t.Any],
        expected_images: tuple | None,
        expected_audios: tuple | None,
        exception,
    ) -> None:
        """Cover the multimodal-aware :meth:`LLMBackend.prepare_input` walk: capability gating,
        placeholder rewriting, per-modality tuple aggregation, and the ``tools`` /
        ``chat_template_kwargs`` forwarding to the tokenizer's ``apply_chat_template`` call.

        Image / audio decode steps are stubbed via :meth:`ImageContent.image` /
        :meth:`AudioContent.audio` so the assertions zero in on the routing logic rather than real
        PNG / WAV decoding (which lives in ``test_message.py``).
        """
        backend = _FakeLLMBackend(chat_template="{{ messages }}", capabilities=capabilities)

        with (
            patch.object(ImageContent, "image", new_callable=AsyncMock, return_value="img-sentinel"),
            patch.object(AudioContent, "audio", new_callable=AsyncMock, return_value=_AUDIO_SENTINEL),
            exception,
        ):
            inputs = await backend.prepare_input(messages, **extra_call_kwargs)

        if expected_template_messages is not None:
            assert isinstance(inputs, EngineInput)
            assert inputs.images == expected_images
            assert inputs.audios == expected_audios
            sent_messages, sent_kwargs = backend.template_calls[0]
            assert sent_messages == expected_template_messages
            assert sent_kwargs == expected_template_kwargs
        else:
            assert backend.template_calls == []

    @pytest.mark.parametrize(
        ["scenario", "registry_kinds", "expected_idx", "exception"],
        [
            pytest.param("dispatch", ["runnable", "runnable"], 0, None, id="first_runnable_wins"),
            pytest.param("dispatch", ["non_runnable", "runnable"], 1, None, id="skips_non_runnable"),
            pytest.param(
                "dispatch",
                ["non_runnable", "non_runnable"],
                None,
                exceptions.FrameworkNotInstalled("vllm or mlx-lm"),
                id="all_non_runnable_raises",
            ),
            pytest.param("populate", None, None, None, id="populates_registry_on_first_call"),
        ],
        indirect=["exception"],
    )
    def test_resolve(
        self,
        scenario: str,
        registry_kinds: list[str] | None,
        expected_idx: int | None,
        exception,
    ) -> None:
        """Cover :meth:`LLMBackend._resolve` end-to-end: lazy registry population on first call,
        first-runnable-wins probe order, non-runnable backends are skipped, and a :class:`FrameworkNotInstalled`
        is raised when no registered backend exposes a usable runtime.
        """
        if scenario == "populate":
            from flama.models.engine.backend.llm.mlx import MLXBackend
            from flama.models.engine.backend.llm.vllm import VLLMBackend

            snapshot = dict(LLMBackend._REGISTRY) if LLMBackend._REGISTRY is not None else None
            try:
                LLMBackend._REGISTRY = None
                try:
                    LLMBackend._resolve()
                except Exception:
                    pass
                assert LLMBackend._REGISTRY is not None
                assert LLMBackend._REGISTRY == {"vllm": VLLMBackend, "mlx": MLXBackend}
            finally:
                LLMBackend._REGISTRY = snapshot
            return

        names = ["vllm", "mlx"]
        registry: dict[str, t.Any] = {}
        backends: list[t.Any] = []
        for name, kind in zip(names, registry_kinds or []):
            cls = MagicMock()
            cls.runnable = MagicMock(return_value=(kind == "runnable"))
            registry[name] = cls
            backends.append(cls)

        with patch.object(LLMBackend, "_REGISTRY", registry), exception:
            result = LLMBackend._resolve()

        if not exception:
            assert result is backends[expected_idx]
            # Cases where the first backend is runnable must short-circuit before probing the
            # rest; assert later entries weren't queried so we don't accidentally regress to a
            # full scan.
            for cls in backends[: max(expected_idx, 0)]:
                assert cls.runnable.called

    @pytest.mark.parametrize(
        ["meta_capabilities", "framework_config", "resolve_side_effect", "expected_call", "exception"],
        [
            pytest.param(
                "caps-sentinel",
                {"max_model_len": 256},
                None,
                call("model-dir", capabilities="caps-sentinel", max_model_len=256),
                None,
                id="forwards_capabilities_and_config",
            ),
            pytest.param(
                None,
                None,
                None,
                call("model-dir", capabilities=None),
                None,
                id="handles_missing_config",
            ),
            pytest.param(
                None,
                None,
                exceptions.FrameworkNotInstalled("vllm or mlx-lm"),
                None,
                exceptions.FrameworkNotInstalled("vllm or mlx-lm"),
                id="propagates_resolve_failure",
            ),
        ],
        indirect=["exception"],
    )
    def test_from_model_artifact(
        self,
        meta_capabilities: t.Any,
        framework_config: dict[str, t.Any] | None,
        resolve_side_effect: BaseException | None,
        expected_call,
        exception,
    ) -> None:
        """Cover :meth:`LLMBackend.from_model_artifact` engine-param forwarding: the artifact's
        ``meta.capabilities`` and ``meta.framework.config`` are forwarded as kwargs, missing config
        is tolerated, and resolution failures bubble up unchanged.
        """
        artifact = MagicMock(model="model-dir")
        artifact.meta.capabilities = meta_capabilities
        artifact.meta.framework.config = framework_config
        backend_cls = MagicMock(return_value=MagicMock(model="model-dir"))

        with (
            patch.object(
                LLMBackend,
                "_resolve",
                return_value=backend_cls if resolve_side_effect is None else None,
                side_effect=resolve_side_effect,
            ),
            exception,
        ):
            result = LLMBackend.from_model_artifact(artifact)

        if not exception:
            assert backend_cls.call_args_list == [expected_call]
            assert result is backend_cls.return_value

    @pytest.mark.parametrize(
        ("module", "guards", "expected"),
        [
            pytest.param(
                "flama.models.engine.backend.llm.vllm",
                {"vllm": object(), "AsyncEngineArgs": object()},
                True,
                id="vllm_runnable_when_deps_imported",
            ),
            pytest.param(
                "flama.models.engine.backend.llm.vllm",
                {"vllm": None, "AsyncEngineArgs": None},
                False,
                id="vllm_not_runnable_when_deps_missing",
            ),
            pytest.param(
                "flama.models.engine.backend.llm.mlx",
                {"mx": object(), "mlx_lm_load": object()},
                True,
                id="mlx_runnable_when_deps_imported",
            ),
            pytest.param(
                "flama.models.engine.backend.llm.mlx",
                {"mx": None, "mlx_lm_load": None},
                False,
                id="mlx_not_runnable_when_deps_missing",
            ),
        ],
    )
    def test_runnable(self, module: str, guards: dict, expected: bool) -> None:
        """Verify :meth:`LLMBackend.runnable` reflects whether each backend's optional dependency
        block has been imported successfully (the module-level ``vllm``/``AsyncEngineArgs`` and
        ``mx``/``mlx_lm_load`` symbols are :data:`None` when the runtime is absent).
        """
        from importlib import import_module

        mod = import_module(module)
        backend_cls = mod.VLLMBackend if "vllm" in module else mod.MLXBackend
        with patch.multiple(mod, **guards):
            assert backend_cls.runnable() is expected


class TestCaseTransformerLLMBackend:
    """Cover :class:`TransformerLLMBackend` — the L2 to chat-template-input projection helpers
    that anchor the HuggingFace ``apply_chat_template`` input dialect (every string key
    ``"text"`` / ``"image"`` / ``"audio"`` / ``"function"`` / ``"role"`` / ... lives here and
    nowhere else).
    """

    @pytest.mark.parametrize(
        ["content", "expected", "exception"],
        [
            pytest.param(TextContent(text="hi"), {"type": "text", "text": "hi"}, None, id="text"),
            pytest.param(TextContent(text=""), {"type": "text", "text": ""}, None, id="text_empty"),
            pytest.param(_stub_image(), {"type": "image"}, None, id="image"),
            pytest.param(_stub_audio(), {"type": "audio"}, None, id="audio"),
            pytest.param(
                MagicMock(spec=[]),
                None,
                ValueError("Unsupported content type"),
                id="unsupported",
            ),
        ],
        indirect=["exception"],
    )
    def test_dump_content_part(self, content: t.Any, expected: dict[str, t.Any] | None, exception) -> None:
        with exception:
            assert TransformerLLMBackend._dump_content_part(content) == expected

    @pytest.mark.parametrize(
        ["tool_call", "expected"],
        [
            pytest.param(
                ToolCall(function={"name": "fn", "arguments": {}}),
                {"type": "function", "function": {"name": "fn", "arguments": {}}},
                id="without_id",
            ),
            pytest.param(
                ToolCall(function={"name": "fn", "arguments": {}}, id="c1"),
                {"type": "function", "function": {"name": "fn", "arguments": {}}, "id": "c1"},
                id="with_id",
            ),
            pytest.param(
                ToolCall(function={"name": "fn", "arguments": '{"x":1}'}),
                {"type": "function", "function": {"name": "fn", "arguments": '{"x":1}'}},
                id="string_encoded_arguments",
            ),
        ],
    )
    def test_dump_tool_call(self, tool_call: ToolCall, expected: dict[str, t.Any]) -> None:
        assert TransformerLLMBackend._dump_tool_call(tool_call) == expected

    @pytest.mark.parametrize(
        ["tool", "expected"],
        [
            pytest.param(
                Tool(name="fn"),
                {"type": "function", "function": {"name": "fn", "parameters": {}}},
                id="bare",
            ),
            pytest.param(
                Tool(name="fn", description="do thing"),
                {"type": "function", "function": {"name": "fn", "description": "do thing", "parameters": {}}},
                id="with_description",
            ),
            pytest.param(
                Tool(name="fn", parameters={"type": "object", "properties": {"x": {"type": "string"}}}),
                {
                    "type": "function",
                    "function": {
                        "name": "fn",
                        "parameters": {"type": "object", "properties": {"x": {"type": "string"}}},
                    },
                },
                id="with_parameters",
            ),
        ],
    )
    def test_dump_tool(self, tool: Tool, expected: dict[str, t.Any]) -> None:
        assert TransformerLLMBackend._dump_tool(tool) == expected

    @pytest.mark.parametrize(
        ["message", "expected"],
        [
            pytest.param(
                UserMessage(content=(TextContent(text="hi"),)),
                {"role": "user", "content": "hi"},
                id="single_text_collapses_to_str",
            ),
            pytest.param(
                UserMessage(content=(TextContent(text="a"), TextContent(text="b"))),
                {"role": "user", "content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]},
                id="multiple_text_parts_keep_list_shape",
            ),
            pytest.param(
                UserMessage(content=(TextContent(text="hi"), _stub_image())),
                {"role": "user", "content": [{"type": "text", "text": "hi"}, {"type": "image"}]},
                id="text_plus_image",
            ),
            pytest.param(
                AssistantMessage(
                    content=(TextContent(text="ok"),),
                    reasoning_content="thinking…",
                ),
                {"role": "assistant", "content": "ok", "reasoning_content": "thinking…"},
                id="assistant_with_reasoning_content",
            ),
            pytest.param(
                AssistantMessage(
                    tool_calls=(ToolCall(function={"name": "fn", "arguments": {}}),),
                ),
                {
                    "role": "assistant",
                    "tool_calls": [{"type": "function", "function": {"name": "fn", "arguments": {}}}],
                },
                id="assistant_with_tool_calls_only",
            ),
            pytest.param(
                ToolMessage(tool_call_id="c1", content=(TextContent(text="result"),)),
                {"role": "tool", "tool_call_id": "c1", "content": "result"},
                id="tool_response",
            ),
        ],
    )
    def test_dump_message(self, message: Message, expected: dict[str, t.Any]) -> None:
        assert TransformerLLMBackend._dump_message(message) == expected

    def test_encode_delegates_to_tokenizer(self) -> None:
        tokenizer = MagicMock()
        tokenizer.encode.return_value = [1, 2, 3]

        class _Backend(_FakeLLMBackend):
            @property
            def _tokenizer(self) -> t.Any:
                return tokenizer

        backend = _Backend(chat_template=None)

        assert TransformerLLMBackend.encode(backend, "hi", add_special_tokens=False) == [1, 2, 3]
        assert tokenizer.encode.call_args == call("hi", add_special_tokens=False)
