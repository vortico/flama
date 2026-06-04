import logging
import pathlib
import typing as t
from unittest.mock import MagicMock, call, patch

import pytest

from flama import exceptions
from flama.models.base import BaseModel, LLMModel, MLModel
from flama.models.engine.backend.base import Backend
from flama.models.engine.backend.llm.base import TransformerLLMBackend
from flama.models.engine.backend.ml.base import MLBackend
from flama.models.engine.llm.codec import LLMCodec
from flama.models.engine.llm.decoder.decoder import _KNOWN_CHANNEL_SCANNERS, Decoder
from flama.models.engine.llm.decoder.markers import PassthroughScanner
from flama.models.engine.llm.delta import EngineDelta
from flama.models.engine.llm.input import EngineInput
from flama.models.transport.input.llm.message import AssistantMessage, TextContent, UserMessage
from flama.models.transport.output.llm.event import Event, TextEvent, ToolEvent


class _FakeMLBackend(MLBackend):
    """Configurable ML backend for unit tests."""

    def __init__(self, model: t.Any = None, /, *, side_effect: Exception | None = None) -> None:
        super().__init__(model)
        self._side_effect = side_effect

    def predict(self, x: t.Iterable[t.Iterable[t.Any]], /) -> t.Any:
        if self._side_effect is not None:
            raise self._side_effect
        return [list(item)[0] * 2 for item in x]


class _FakeLLMBackend(TransformerLLMBackend):
    """Configurable LLM backend for unit tests.

    Records ``apply_chat_template`` kwargs so tests can assert that ``chat_template_kwargs`` are forwarded.
    Generation is parameterised by *tokens* / *error*. ``chat_template_sample`` defaults to ``chat_template`` so
    pre-existing tests can omit it; pass ``chat_template_sample=`` (or use the dedicated sentinel handling) to
    decouple the two.
    """

    _UNSET: t.ClassVar[t.Any] = object()

    def __init__(
        self,
        model: t.Any = None,
        /,
        *,
        chat_template: str | None = "{{ messages }}",
        chat_template_sample: t.Any = _UNSET,
        tokens: list[str] | None = None,
        error: Exception | None = None,
    ) -> None:
        super().__init__(model)
        self._chat_template = chat_template
        self._chat_template_sample: str | None = (
            chat_template if chat_template_sample is self._UNSET else chat_template_sample
        )
        self._tokens_value = tokens or []
        self._error = error
        self.template_kwargs: list[dict[str, t.Any]] = []
        self.last_tokens: list[int] | None = None
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
        return self._chat_template_sample

    def _max_context(self) -> int | None:
        return 8192

    def encode(self, text: str, /, *, add_special_tokens: bool = True) -> list[int]:
        return [ord(c) for c in text]

    @t.overload
    def apply_chat_template(
        self,
        messages: list[dict[str, t.Any]],
        /,
        *,
        tokenize: t.Literal[False],
        add_generation_prompt: bool = True,
        **kwargs,
    ) -> str: ...
    @t.overload
    def apply_chat_template(
        self,
        messages: list[dict[str, t.Any]],
        /,
        *,
        tokenize: t.Literal[True] = True,
        add_generation_prompt: bool = True,
        **kwargs,
    ) -> list[int]: ...
    def apply_chat_template(
        self,
        messages: list[dict[str, t.Any]],
        /,
        *,
        tokenize: bool = True,
        add_generation_prompt: bool = True,
        **kwargs,
    ) -> list[int] | str:
        if not tokenize:
            return ""
        self.template_kwargs.append(kwargs)
        rendered = "|".join(f"{m['role']}:{m['content']}" for m in messages)
        return [ord(c) for c in rendered]

    async def generate(self, inputs: EngineInput, /, **params: t.Any) -> t.AsyncIterator[EngineDelta]:
        self.last_tokens = list(inputs.tokens)
        if self._error is not None:
            raise self._error
        for token in self._tokens_value:
            yield EngineDelta(text=token, token_count=1)


class TestCaseBaseModel:
    @pytest.fixture(scope="function")
    def model(self) -> type[BaseModel]:
        class _Model(BaseModel[MLBackend]):
            _BACKEND_CLS = MLBackend

        return _Model

    def test_init(self, model) -> None:
        backend = MagicMock(spec=Backend)
        meta = MagicMock()
        artifacts = {"a.bin": "/tmp/a"}

        m = model(backend, meta, artifacts, name="puppy")

        assert m.backend is backend
        assert m.meta is meta
        assert m.artifacts == artifacts
        assert m.name == "puppy"

    def test_init_defaults_name_to_none(self, model) -> None:
        m = model(MagicMock(spec=Backend), MagicMock(), None)

        assert m.name is None

    def test_inspect(self, model) -> None:
        meta = MagicMock(to_dict=MagicMock(return_value={"id": "x"}))
        m = model(MagicMock(spec=Backend), meta, None)

        assert m.inspect() == {"meta": {"id": "x"}, "manifest": []}

    async def test_startup_idempotent_on_eager(self, model) -> None:
        m = model(MagicMock(spec=Backend), MagicMock(), None)

        with patch("flama.models.base.Serializer.load") as p_load:
            assert await m.startup() is None
            assert not p_load.called


class TestCaseLazyTiers:
    @pytest.fixture(scope="function")
    def model(self) -> type[BaseModel]:
        class _Model(BaseModel[MLBackend]):
            _BACKEND_CLS = MLBackend

        return _Model

    @pytest.mark.parametrize(
        ["eager_meta", "has_path", "exception"],
        [
            pytest.param(True, True, None, id="eager_short_circuits"),
            pytest.param(False, True, None, id="lazy_reads_via_serializer"),
            pytest.param(False, False, (exceptions.ApplicationError, "no metadata"), id="no_path_raises"),
        ],
        indirect=["exception"],
    )
    def test_meta(self, model, eager_meta: bool, has_path: bool, exception) -> None:
        path = pathlib.Path("/some/path.flm") if has_path else None
        eager = MagicMock() if eager_meta else None
        cheap = MagicMock()
        kwargs: dict[str, t.Any] = {}
        if eager is not None:
            kwargs["meta"] = eager
        if path is not None:
            kwargs["path"] = path
        m = model(**kwargs)

        with exception, patch("flama.models.base.Serializer.meta", return_value=cheap) as p_meta:
            assert m.meta is (eager if eager_meta else cheap)
            assert m.meta is (eager if eager_meta else cheap)
            if eager_meta:
                assert not p_meta.called
            else:
                assert p_meta.call_args_list == [call(path=path)]

    @pytest.mark.parametrize(
        ["eager_artifacts", "has_path", "expected"],
        [
            pytest.param(True, True, ("a.bin",), id="eager_short_circuits"),
            pytest.param(False, True, ("foo.json", "bar.bin"), id="lazy_reads_serializer"),
            pytest.param(False, False, (), id="no_path_returns_empty"),
        ],
    )
    def test_manifest(self, model, eager_artifacts: bool, has_path: bool, expected: tuple[str, ...]) -> None:
        path = pathlib.Path("/some/path.flm") if has_path else None
        kwargs: dict[str, t.Any] = {}
        if eager_artifacts:
            kwargs["artifacts"] = {"a.bin": pathlib.Path("/tmp/a")}
        if path is not None:
            kwargs["path"] = path
        m = model(**kwargs)

        with patch("flama.models.base.Serializer.manifest", return_value=expected) as p_manifest:
            assert m.manifest == expected
            assert m.manifest == expected
            if eager_artifacts or not has_path:
                assert not p_manifest.called
            else:
                assert p_manifest.call_args_list == [call(path=path)]

    @pytest.mark.parametrize(
        ["eager_artifacts"],
        [pytest.param(True, id="eager_passthrough"), pytest.param(False, id="pre_load_returns_none")],
    )
    def test_artifacts(self, model, eager_artifacts: bool) -> None:
        artifacts = {"a.bin": pathlib.Path("/tmp/a")} if eager_artifacts else None
        kwargs: dict[str, t.Any] = {"path": pathlib.Path("/some/path.flm")}
        if artifacts is not None:
            kwargs["artifacts"] = artifacts
        m = model(**kwargs)

        assert m.artifacts is artifacts

    def test_backend_eager_short_circuits(self, model) -> None:
        backend = MagicMock(spec=Backend)
        m = model(backend=backend, path=pathlib.Path("/some/path.flm"))

        with patch("flama.models.base.Serializer.load") as p_load:
            assert m.backend is backend
            assert not p_load.called

    def test_backend_no_autoload_raises(self, model) -> None:
        m = model(path=pathlib.Path("/some/path.flm"), autoload=False, name="puppy")

        with pytest.raises(exceptions.ApplicationError, match="not loaded"):
            m.backend

    def test_backend_autoload_loads_on_first_access(self, model) -> None:
        path = pathlib.Path("/some/path.flm")
        meta = MagicMock(id="lazy-id")
        artifact = MagicMock(model="engine", meta=meta, artifacts={"a": "b"})
        backend = MagicMock(spec=Backend)

        m = model(path=path, meta=meta, autoload=True, name="puppy")

        with (
            patch("flama.models.base.Serializer.load", return_value=artifact) as p_load,
            patch.object(MLBackend, "from_model_artifact", return_value=backend) as p_resolve,
        ):
            assert m.backend is backend
            assert m.backend is backend
            assert p_load.call_args_list == [call(path=path)]
            assert p_resolve.call_args_list == [call(artifact)]

    @pytest.mark.parametrize(
        ["path", "exception"],
        [
            pytest.param(pathlib.Path("/some/path.flm"), None, id="idempotent"),
            pytest.param(None, (exceptions.ApplicationError, "cannot be loaded"), id="no_path_raises"),
        ],
        indirect=["exception"],
    )
    def test_load(self, model, path: pathlib.Path | None, exception) -> None:
        meta = MagicMock(id="lazy-id")
        artifact = MagicMock(model="engine", meta=meta, artifacts=None)
        backend = MagicMock(spec=Backend)
        kwargs: dict[str, t.Any] = {"meta": meta, "name": "puppy"}
        if path is not None:
            kwargs["path"] = path

        m = model(**kwargs)

        with (
            exception,
            patch("flama.models.base.Serializer.load", return_value=artifact) as p_load,
            patch.object(MLBackend, "from_model_artifact", return_value=backend),
        ):
            m.load()
            m.load()
            assert p_load.call_count == 1
            assert p_load.call_args == call(path=path)


class TestCaseMLModel:
    @pytest.mark.parametrize(
        ["side_effect", "expected", "exception"],
        [
            pytest.param(None, [0, 2], None, id="success"),
            pytest.param(RuntimeError("boom"), None, RuntimeError, id="error_propagates"),
            pytest.param(
                exceptions.FrameworkNotInstalled("torch"),
                None,
                exceptions.FrameworkNotInstalled,
                id="not-installed",
            ),
        ],
        indirect=["exception"],
    )
    def test_predict(self, side_effect: Exception | None, expected: t.Any, exception) -> None:
        backend = _FakeMLBackend(side_effect=side_effect)
        m = MLModel(backend, MagicMock(), None)

        with exception:
            assert m.predict([[0], [1]]) == expected

    @pytest.mark.parametrize(
        ["side_effect", "expected", "exception"],
        [
            pytest.param(None, [[0], [2]], None, id="success"),
            pytest.param(RuntimeError("boom"), [], None, id="error-terminates"),
            pytest.param(
                exceptions.FrameworkNotInstalled("torch"), None, exceptions.FrameworkNotInstalled, id="not-installed"
            ),
        ],
        indirect=["exception"],
    )
    async def test_stream(self, side_effect: Exception | None, expected: t.Any, exception) -> None:
        backend = _FakeMLBackend(side_effect=side_effect)
        m = MLModel(backend, MagicMock(), None)

        async def _input() -> t.AsyncIterator[t.Any]:
            yield [0]
            yield [1]

        with exception:
            assert [item async for item in m.stream(_input())] == expected

    async def test_startup_idempotent_on_eager(self) -> None:
        m = MLModel(_FakeMLBackend(), MagicMock(), None)

        with patch("flama.models.base.Serializer.load") as p_load:
            assert await m.startup() is None
            assert not p_load.called


class TestCaseLLMModel:
    def test_init(self) -> None:
        backend = _FakeLLMBackend()
        m = LLMModel(backend, MagicMock(), None, name="puppy")

        assert m.params == {}
        assert m.backend is backend
        assert m.model is backend.model
        assert m.name == "puppy"

    @pytest.mark.parametrize(
        ["config", "exception"],
        [
            pytest.param({}, None, id="empty"),
            pytest.param({"temperature": 0.7}, None, id="ordinary_params"),
            pytest.param({"reasoning": True}, None, id="reasoning_true"),
            pytest.param({"reasoning": False}, None, id="reasoning_false"),
            pytest.param({"reasoning_effort": "low"}, None, id="reasoning_effort_low"),
            pytest.param({"reasoning_effort": "max"}, None, id="reasoning_effort_unconventional_passes_through"),
            pytest.param({"reasoning": "tagged"}, (ValueError, "must be a bool"), id="reasoning_string_rejected"),
            pytest.param({"reasoning": 1}, (ValueError, "must be a bool"), id="reasoning_int_rejected"),
        ],
        indirect=["exception"],
    )
    def test_validate_config(self, config: dict[str, t.Any], exception) -> None:
        with exception:
            assert LLMModel.validate_config(config) is config

    def test_configure(self) -> None:
        m = LLMModel(_FakeLLMBackend(), MagicMock(), None)

        m.configure({"temperature": 0.7, "max_tokens": 100})
        assert m.params == {"temperature": 0.7, "max_tokens": 100}

        m.configure({"temperature": 0.9, "reasoning_effort": "medium"})
        assert m.params == {"temperature": 0.9, "max_tokens": 100, "reasoning_effort": "medium"}

    @pytest.mark.parametrize(
        ["prompt", "call_kwargs", "tokens", "error", "result", "exception"],
        [
            pytest.param(
                "hello world",
                {},
                ["a", "b"],
                None,
                [TextEvent(channel="output", text="a"), TextEvent(channel="output", text="b")],
                None,
                id="prompt_default_chat",
            ),
            pytest.param(
                "hello world",
                {"transport": "raw"},
                ["a", "b"],
                None,
                [TextEvent(channel="output", text="a"), TextEvent(channel="output", text="b")],
                None,
                id="prompt_raw",
            ),
            pytest.param(
                "hi",
                {"system": "be brief", "transport": "chat"},
                ["a", "b"],
                None,
                [TextEvent(channel="output", text="a"), TextEvent(channel="output", text="b")],
                None,
                id="chat_with_system",
            ),
            pytest.param(
                None,
                {
                    "messages": [
                        UserMessage(content=(TextContent(text="hi"),)),
                        AssistantMessage(content=(TextContent(text="hello"),)),
                    ],
                    "transport": "conversation",
                },
                ["a", "b"],
                None,
                [TextEvent(channel="output", text="a"), TextEvent(channel="output", text="b")],
                None,
                id="conversation",
            ),
            pytest.param(
                "hello",
                {},
                [],
                None,
                None,
                (RuntimeError, "no output"),
                id="empty_output_raises_runtime_error",
            ),
            pytest.param(
                "hello",
                {},
                None,
                RuntimeError("engine boom"),
                None,
                (RuntimeError, "engine boom"),
                id="engine_error_propagates",
            ),
            pytest.param(
                None,
                {},
                None,
                None,
                None,
                (ValueError, "'prompt' is required"),
                id="missing_prompt_raises_value_error",
            ),
        ],
        indirect=["exception"],
    )
    async def test_query(
        self,
        prompt: str | None,
        call_kwargs: dict[str, t.Any],
        tokens: list[str] | None,
        error: Exception | None,
        result: list[Event] | None,
        exception,
    ) -> None:
        backend = _FakeLLMBackend(tokens=tokens, error=error)
        m = LLMModel(backend, MagicMock(), None, decoder=Decoder("passthrough", "passthrough", "passthrough"))
        await m.startup()

        with exception:
            blocks = await m.query(prompt, **call_kwargs)
            assert [b for b in blocks if isinstance(b, (TextEvent, ToolEvent))] == result

    @pytest.mark.parametrize(
        ["prompt", "call_kwargs", "tokens", "expected"],
        [
            pytest.param(
                "hello",
                {},
                ["a", "b"],
                [TextEvent(channel="output", text="a"), TextEvent(channel="output", text="b")],
                id="prompt_success",
            ),
            pytest.param(
                "hi",
                {"system": "be brief"},
                ["a", "b"],
                [TextEvent(channel="output", text="a"), TextEvent(channel="output", text="b")],
                id="chat_with_system",
            ),
        ],
    )
    async def test_stream(
        self,
        prompt: str | None,
        call_kwargs: dict[str, t.Any],
        tokens: list[str],
        expected: list[Event],
    ) -> None:
        backend = _FakeLLMBackend(tokens=tokens)
        m = LLMModel(backend, MagicMock(), None, decoder=Decoder("passthrough", "passthrough", "passthrough"))
        await m.startup()

        items = [item async for item in await m.stream(prompt, **call_kwargs)]
        blocks = [item for item in items if isinstance(item, (TextEvent, ToolEvent))]
        assert blocks == expected

    async def test_stream_validation_error_propagates_synchronously(self) -> None:
        m = LLMModel(
            _FakeLLMBackend(tokens=["x"]),
            MagicMock(),
            None,
            decoder=Decoder("passthrough", "passthrough", "passthrough"),
        )

        with pytest.raises(ValueError, match="'prompt' is required"):
            await m.stream()

    async def test_stream_mid_iteration_error_propagates(self) -> None:
        backend = _FakeLLMBackend(error=RuntimeError("boom"))
        m = LLMModel(backend, MagicMock(), None, decoder=Decoder("passthrough", "passthrough", "passthrough"))
        await m.startup()

        with pytest.raises(RuntimeError, match="boom"):
            [block async for block in await m.stream("hello")]

    @pytest.mark.parametrize(
        ["api", "chat_template_kwargs"],
        [
            pytest.param("query", {"enable_thinking": False}, id="query"),
            pytest.param("stream", {"enable_thinking": True}, id="stream"),
        ],
    )
    async def test_forwards_chat_template_kwargs(self, api: str, chat_template_kwargs: dict[str, t.Any]) -> None:
        backend = _FakeLLMBackend(tokens=["x"])
        m = LLMModel(backend, MagicMock(), None, decoder=Decoder("passthrough", "passthrough", "passthrough"))
        await m.startup()

        if api == "query":
            await m.query("hi", chat_template_kwargs=chat_template_kwargs)
        else:
            async for _ in await m.stream("hi", chat_template_kwargs=chat_template_kwargs):
                pass

        assert backend.template_kwargs == [chat_template_kwargs]

    def test_codec_default_starts_undetected(self) -> None:
        m = LLMModel(_FakeLLMBackend(), MagicMock(), None)

        assert isinstance(m._codec, LLMCodec)
        with pytest.raises(exceptions.ApplicationError, match="not detected"):
            m._codec.decoder

    async def test_fully_pinned_decoder_resolved_at_startup(self) -> None:
        decoder = Decoder("passthrough", "passthrough", "passthrough")
        backend = _FakeLLMBackend(chat_template_sample=None)
        m = LLMModel(backend, MagicMock(), None, decoder=decoder)

        with pytest.raises(exceptions.ApplicationError):
            m._codec.decoder

        await m.startup()

        assert isinstance(m._codec.decoder.channel_scanner, PassthroughScanner)
        assert backend.chat_template_sample_calls == 0
        assert backend.last_tokens is None

    async def test_partial_decoder_completes_at_startup(self) -> None:
        backend = _FakeLLMBackend(tokens=["plain output"])
        m = LLMModel(backend, MagicMock(), None, decoder=Decoder("think"))

        await m.startup()

        assert m._codec.decoder.channel_scanner is _KNOWN_CHANNEL_SCANNERS["think"]

    def test_default_transport_from_backend(self) -> None:
        m_chat = LLMModel(_FakeLLMBackend(chat_template="{{ messages }}"), MagicMock(), None)
        m_raw = LLMModel(_FakeLLMBackend(chat_template=None), MagicMock(), None)

        assert m_chat.default_transport == "chat"
        assert m_raw.default_transport == "raw"

    @pytest.mark.parametrize(
        ["tokens", "decoder", "expected_channel"],
        [
            pytest.param(["<think>r</think>answer"], None, _KNOWN_CHANNEL_SCANNERS["think"], id="detects_think"),
            pytest.param(["plain output"], None, PassthroughScanner, id="falls_back_to_passthrough"),
            pytest.param(
                ["<think>r</think>answer"],
                Decoder("passthrough"),
                PassthroughScanner,
                id="pinned_short_circuits_detection",
            ),
        ],
    )
    async def test_startup(
        self,
        tokens: list[str],
        decoder: Decoder | None,
        expected_channel: t.Any,
    ) -> None:
        m = LLMModel(_FakeLLMBackend(tokens=tokens), MagicMock(), None, decoder=decoder)

        await m.startup()

        if isinstance(expected_channel, type):
            assert isinstance(m._codec.decoder.channel_scanner, expected_channel)
        else:
            assert m._codec.decoder.channel_scanner is expected_channel

    async def test_startup_logs_progress(self, caplog_flama: pytest.LogCaptureFixture) -> None:
        meta = MagicMock()
        meta.id = "startup-test-id"
        m = LLMModel(_FakeLLMBackend(tokens=["plain output"]), meta, None, name="puppy", decoder=Decoder("passthrough"))

        with caplog_flama.at_level(logging.INFO, logger="flama.models.base"):
            await m.startup()

        messages = [record.getMessage() for record in caplog_flama.records if record.name == "flama.models.base"]
        assert any("Decoder detection starting" in m and "puppy" in m and "startup-test-id" in m for m in messages)
        assert any(
            "Decoder detection complete" in m and "puppy" in m and "startup-test-id" in m and "s" in m for m in messages
        )
        assert any("Model ready" in m and "puppy" in m and "startup-test-id" in m for m in messages)
