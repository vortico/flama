import pathlib
import typing as t
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from flama import exceptions
from flama.models.engine.backend.llm._base import TransformerLLMBackend
from flama.models.engine.backend.llm.vllm import VLLMBackend
from flama.models.engine.llm.input import EngineInput
from flama.serialize.data_structures import LLMModelCapabilities


class _FakeRequestOutputKind:
    DELTA = "DELTA"
    FINAL_ONLY = "FINAL_ONLY"


class TestCaseVLLMBackend:
    MAX_MODEL_LEN: t.ClassVar[int] = 8192

    @staticmethod
    def _cuda_output(text: str, *, finish_reason: str | None = None, token_ids: tuple[int, ...] = ()) -> Mock:
        out = Mock()
        completion = Mock(text=text, finish_reason=finish_reason, token_ids=token_ids)
        out.outputs = [completion]
        return out

    @staticmethod
    def _bad_cuda_output() -> Mock:
        bad = Mock()
        bad.outputs.__getitem__ = Mock(side_effect=IndexError("no outputs"))
        return bad

    @staticmethod
    async def _aiter(*items: t.Any) -> t.AsyncIterator[t.Any]:
        for item in items:
            yield item

    @staticmethod
    async def _failing_aiter(error: Exception) -> t.AsyncIterator[t.Any]:
        raise error
        yield  # pragma: no cover

    @classmethod
    def _make_backend(
        cls,
        *,
        engine: Mock | None = None,
        model_dir: pathlib.Path | None = None,
        capabilities: LLMModelCapabilities | None = None,
        **engine_params: t.Any,
    ) -> VLLMBackend:
        """Build a :class:`VLLMBackend` with the engine construction mocked out.

        The constructor calls :func:`vllm.AsyncLLMEngine.from_engine_args` internally; tests patch
        it to return *engine* (or a fresh ``Mock``) so neither vLLM nor a real model directory is
        required. Seeds ``engine.engine.model_config.max_model_len`` to :attr:`MAX_MODEL_LEN` so
        the :meth:`VLLMBackend._max_context` probe finds a usable int.
        """
        if engine is None:
            engine = Mock()
            del engine.processor
            engine.engine = Mock()
            engine.engine.model_config = Mock(model=None, max_model_len=cls.MAX_MODEL_LEN)

        fake_vllm = MagicMock()
        fake_vllm.AsyncLLMEngine.from_engine_args.return_value = engine
        fake_args = MagicMock(return_value="engine-args")

        with (
            patch("flama.models.engine.backend.llm.vllm.vllm", fake_vllm),
            patch("flama.models.engine.backend.llm.vllm.AsyncEngineArgs", fake_args),
        ):
            return VLLMBackend(model_dir or pathlib.Path("/tmp/model"), capabilities=capabilities, **engine_params)

    @pytest.fixture(scope="function")
    def engine(self):
        engine = Mock()
        del engine.processor
        engine.engine = Mock()
        engine.engine.model_config = Mock(model=None, max_model_len=self.MAX_MODEL_LEN)
        return engine

    @pytest.mark.parametrize(
        ["has_shutdown"],
        [
            pytest.param(True, id="with_shutdown"),
            pytest.param(False, id="without_shutdown"),
        ],
    )
    def test_init(self, engine, has_shutdown):
        if has_shutdown:
            engine.shutdown = Mock()
        else:
            del engine.shutdown

        fake_vllm = MagicMock()
        fake_vllm.AsyncLLMEngine.from_engine_args.return_value = engine
        fake_args = MagicMock(return_value="engine-args")

        with (
            patch("flama.models.engine.backend.llm.vllm.vllm", fake_vllm),
            patch("flama.models.engine.backend.llm.vllm.AsyncEngineArgs", fake_args),
            patch("flama.models.engine.backend.llm.vllm.weakref") as mock_weakref,
        ):
            backend = VLLMBackend(pathlib.Path("/tmp/model"), max_model_len=512)

        assert backend.model is engine
        assert fake_vllm.AsyncLLMEngine.from_engine_args.call_args == call("engine-args")
        assert fake_args.call_args == call(model="/tmp/model", disable_log_stats=True, max_model_len=512)
        if has_shutdown:
            assert mock_weakref.finalize.call_args_list == [call(backend, engine.shutdown)]
        else:
            assert not mock_weakref.finalize.called

    def test_init_raises_when_vllm_missing(self):
        with (
            patch("flama.models.engine.backend.llm.vllm.vllm", None),
            patch("flama.models.engine.backend.llm.vllm.AsyncEngineArgs", None),
            pytest.raises(exceptions.FrameworkNotInstalled),
        ):
            VLLMBackend(pathlib.Path("/tmp/model"))

    def test_tokenizer(self, engine):
        inner = Mock()
        engine.tokenizer = Mock(tokenizer=inner)

        backend = self._make_backend(engine=engine)

        assert backend._tokenizer is inner
        assert backend._tokenizer is inner

    def test_chat_template(self, engine):
        inner = Mock(chat_template="some_template")
        engine.tokenizer = Mock(tokenizer=inner)

        backend = self._make_backend(engine=engine)

        assert backend.chat_template == "some_template"

    @pytest.mark.parametrize(
        ["template", "render_result", "render_error", "expected", "expects_call"],
        [
            pytest.param("template", "rendered assistant turn", None, "rendered assistant turn", True, id="success"),
            pytest.param(None, None, None, None, False, id="no_template"),
            pytest.param("template", None, RuntimeError("bad template"), None, True, id="render_error"),
        ],
    )
    def test_chat_template_sample(
        self,
        engine,
        template: str | None,
        render_result: str | None,
        render_error: Exception | None,
        expected: str | None,
        expects_call: bool,
    ) -> None:
        inner = Mock(chat_template=template)
        inner.apply_chat_template = Mock(side_effect=render_error, return_value=render_result)
        engine.tokenizer = Mock(tokenizer=inner)

        backend = self._make_backend(engine=engine)

        assert backend.chat_template_sample() == expected
        if expects_call:
            expected_msgs = [TransformerLLMBackend._dump_message(m) for m in TransformerLLMBackend._SAMPLE_MESSAGES]
            expected_tools = [TransformerLLMBackend._dump_tool(tool) for tool in TransformerLLMBackend._SAMPLE_TOOLS]
            assert inner.apply_chat_template.call_args_list == [
                call(
                    expected_msgs,
                    tools=expected_tools,
                    tokenize=False,
                    add_generation_prompt=False,
                )
            ]
        else:
            assert not inner.apply_chat_template.called

    @pytest.mark.parametrize(
        ["tokenize", "chat_template", "rendered", "expected", "exception"],
        [
            pytest.param(True, "template", [1, 2, 3, 4], [1, 2, 3, 4], None, id="flat_list_of_ints"),
            pytest.param(
                True,
                "template",
                {"input_ids": [1, 2, 3, 4], "attention_mask": [1, 1, 1, 1]},
                [1, 2, 3, 4],
                None,
                id="batch_encoding_normalises_to_input_ids",
            ),
            pytest.param(
                False, "template", "rendered prompt", "rendered prompt", None, id="no_tokenize_returns_string"
            ),
            pytest.param(True, None, None, None, ValueError, id="missing_chat_template"),
        ],
        indirect=["exception"],
    )
    def test_apply_chat_template(
        self,
        engine,
        tokenize: bool,
        chat_template: str | None,
        rendered: t.Any,
        expected: t.Any,
        exception,
    ) -> None:
        """The wrapper normalises HF tokenizer / processor returns into ``list[int]`` regardless
        of the renderer family.

        - mlx-lm's :class:`TokenizerWrapper` and custom Jinja callables already return a flat
          ``list[int]`` (``flat_list_of_ints``).
        - Raw HF tokenizers in ``transformers`` >= 5.0 default to ``return_dict=True`` and hand
          back a :class:`BatchEncoding` whose iteration yields key strings; we detect that shape
          and extract ``input_ids`` so downstream consumers never see ``"input_ids"`` /
          ``"attention_mask"`` poisoning the token list (``batch_encoding_normalises_to_input_ids``).
        - ``tokenize=False`` short-circuits and returns the rendered string verbatim.
        - A missing template raises :class:`ValueError` before the renderer is touched.
        """
        inner = Mock(chat_template=chat_template)
        inner.apply_chat_template = Mock(return_value=rendered)
        engine.tokenizer = Mock(tokenizer=inner)
        backend = self._make_backend(engine=engine)
        messages = [{"role": "user", "content": "Hi"}]

        with exception:
            result = backend.apply_chat_template(messages, tokenize=tokenize)

        if exception:
            assert not inner.apply_chat_template.called
        else:
            assert result == expected
            assert inner.apply_chat_template.call_args_list == [
                call(messages, tokenize=tokenize, add_generation_prompt=True)
            ]

    @pytest.mark.parametrize(
        ["installed", "outputs", "expected", "exception"],
        [
            pytest.param(True, ["Hello", " ", "world"], ["Hello", " ", "world"], None, id="success"),
            pytest.param(True, [], [], None, id="empty"),
            pytest.param(True, ["Hello", "", "world"], ["Hello", "world"], None, id="skip_empty"),
            pytest.param(False, None, None, exceptions.FrameworkNotInstalled, id="not_installed"),
            pytest.param(True, "access-error", None, IndexError, id="access_error"),
            pytest.param(True, "engine-error", None, RuntimeError, id="engine_error"),
        ],
        indirect=["exception"],
    )
    async def test_generate(self, engine, installed, outputs, expected, exception):
        if outputs == "access-error":
            engine.generate.return_value = self._aiter(self._cuda_output("Hello"), self._bad_cuda_output())
        elif outputs == "engine-error":
            engine.generate.return_value = self._failing_aiter(RuntimeError("engine boom"))
        elif outputs is not None:
            engine.generate.return_value = self._aiter(*(self._cuda_output(text) for text in outputs))

        backend = self._make_backend(engine=engine)
        tokens = [1, 2, 3]
        inputs = EngineInput(tokens=tokens)

        with (
            patch("flama.models.engine.backend.llm.vllm.vllm", MagicMock() if installed else None),
            patch(
                "flama.models.engine.backend.llm.vllm.RequestOutputKind", _FakeRequestOutputKind if installed else None
            ),
            exception,
        ):
            deltas = [delta async for delta in backend.generate(inputs)]
            assert [d.text for d in deltas] == expected
            if installed and outputs not in ("engine-error",):
                call_args, _ = engine.generate.call_args
                assert call_args[0] == {"prompt_token_ids": tokens}

    async def test_generate_forwards_explicit_max_tokens_to_sampling_params(self, engine):
        engine.generate.return_value = self._aiter(self._cuda_output("ok"))
        backend = self._make_backend(engine=engine)
        fake_vllm = MagicMock()

        with (
            patch("flama.models.engine.backend.llm.vllm.vllm", fake_vllm),
            patch("flama.models.engine.backend.llm.vllm.RequestOutputKind", _FakeRequestOutputKind),
        ):
            [d async for d in backend.generate(EngineInput(tokens=[1, 2, 3]), max_tokens=128)]

        sampling_kwargs = fake_vllm.SamplingParams.call_args.kwargs
        assert sampling_kwargs["max_tokens"] == 128
        assert sampling_kwargs["output_kind"] == _FakeRequestOutputKind.DELTA

    async def test_generate_resolves_absent_max_tokens_to_max_context_minus_prompt(self, engine):
        engine.generate.return_value = self._aiter(self._cuda_output("ok"))
        backend = self._make_backend(engine=engine)
        fake_vllm = MagicMock()

        with (
            patch("flama.models.engine.backend.llm.vllm.vllm", fake_vllm),
            patch("flama.models.engine.backend.llm.vllm.RequestOutputKind", _FakeRequestOutputKind),
        ):
            [d async for d in backend.generate(EngineInput(tokens=[1, 2, 3]))]

        sampling_kwargs = fake_vllm.SamplingParams.call_args.kwargs
        assert sampling_kwargs["max_tokens"] == self.MAX_MODEL_LEN - 3

    @pytest.mark.parametrize("invalid", [0, -1])
    async def test_generate_raises_on_non_positive_max_tokens(self, engine, invalid: int) -> None:
        backend = self._make_backend(engine=engine)

        with (
            patch("flama.models.engine.backend.llm.vllm.vllm", MagicMock()),
            patch("flama.models.engine.backend.llm.vllm.RequestOutputKind", _FakeRequestOutputKind),
            pytest.raises(ValueError, match="max_tokens must be a positive integer"),
        ):
            [d async for d in backend.generate(EngineInput(tokens=[1]), max_tokens=invalid)]

    def test_max_context_probes_inner_engine_model_config(self, engine):
        engine.engine.model_config = Mock(max_model_len=4096)
        backend = self._make_backend(engine=engine)

        assert backend._max_context() == 4096

    def test_max_context_falls_back_to_outer_model_config(self, engine):
        del engine.engine
        engine.model_config = Mock(max_model_len=2048)
        backend = self._make_backend(engine=engine)

        assert backend._max_context() == 2048

    def test_max_context_returns_none_when_probe_paths_empty(self, engine):
        del engine.engine
        engine.model_config = Mock(spec=[])
        backend = self._make_backend(engine=engine)

        assert backend._max_context() is None

    async def test_generate_forwards_image_payload(self, engine):
        engine.generate.return_value = self._aiter(self._cuda_output("ok"))
        backend = self._make_backend(engine=engine)
        sentinel = "pil-image-sentinel"
        inputs = EngineInput(tokens=[1, 2], images=(t.cast(t.Any, sentinel),))

        with (
            patch("flama.models.engine.backend.llm.vllm.vllm", MagicMock()),
            patch("flama.models.engine.backend.llm.vllm.RequestOutputKind", _FakeRequestOutputKind),
        ):
            [d async for d in backend.generate(inputs)]

        call_args, _ = engine.generate.call_args
        assert call_args[0] == {"prompt_token_ids": [1, 2], "multi_modal_data": {"image": [sentinel]}}

    async def test_generate_forwards_audio_payload(self, engine):
        engine.generate.return_value = self._aiter(self._cuda_output("ok"))
        backend = self._make_backend(engine=engine)
        sentinel = ("waveform", 16000)
        inputs = EngineInput(tokens=[1, 2], audios=(t.cast(t.Any, sentinel),))

        with (
            patch("flama.models.engine.backend.llm.vllm.vllm", MagicMock()),
            patch("flama.models.engine.backend.llm.vllm.RequestOutputKind", _FakeRequestOutputKind),
        ):
            [d async for d in backend.generate(inputs)]

        call_args, _ = engine.generate.call_args
        assert call_args[0] == {"prompt_token_ids": [1, 2], "multi_modal_data": {"audio": [sentinel]}}

    async def test_generate_forwards_image_and_audio_payload(self, engine):
        engine.generate.return_value = self._aiter(self._cuda_output("ok"))
        backend = self._make_backend(engine=engine)
        image_sentinel = "pil-image-sentinel"
        audio_sentinel = ("waveform", 16000)
        inputs = EngineInput(
            tokens=[1, 2],
            images=(t.cast(t.Any, image_sentinel),),
            audios=(t.cast(t.Any, audio_sentinel),),
        )

        with (
            patch("flama.models.engine.backend.llm.vllm.vllm", MagicMock()),
            patch("flama.models.engine.backend.llm.vllm.RequestOutputKind", _FakeRequestOutputKind),
        ):
            [d async for d in backend.generate(inputs)]

        call_args, _ = engine.generate.call_args
        assert call_args[0] == {
            "prompt_token_ids": [1, 2],
            "multi_modal_data": {"image": [image_sentinel], "audio": [audio_sentinel]},
        }

    @pytest.mark.parametrize(
        ["attrs", "expected"],
        [
            pytest.param(
                ["image_processor"],
                LLMModelCapabilities(text=True, image=True),
                id="image_processor",
            ),
            pytest.param(
                ["feature_extractor"],
                LLMModelCapabilities(text=True, audio=True),
                id="feature_extractor",
            ),
            pytest.param(
                ["audio_processor"],
                LLMModelCapabilities(text=True, audio=True),
                id="audio_processor",
            ),
            pytest.param(
                ["image_processor", "audio_processor"],
                LLMModelCapabilities(text=True, image=True, audio=True),
                id="image_and_audio",
            ),
        ],
    )
    def test_detect_capabilities_probes_processor(
        self, engine, attrs: list[str], expected: LLMModelCapabilities
    ) -> None:
        processor = Mock(spec=attrs)
        for attr in attrs:
            setattr(processor, attr, Mock())
        engine.processor = processor

        backend = self._make_backend(engine=engine)

        assert backend.capabilities == expected

    def test_detect_capabilities_text_only_when_renderer_is_tokenizer(self, engine) -> None:
        engine.processor = Mock(spec=[])
        engine.tokenizer = Mock(tokenizer=Mock(spec=["chat_template", "encode", "apply_chat_template"]))

        backend = self._make_backend(engine=engine)

        assert backend.capabilities == LLMModelCapabilities(text=True)

    def test_capabilities_override_wins(self, engine):
        override = LLMModelCapabilities(text=True, image=True, audio=True)
        backend = self._make_backend(engine=engine, capabilities=override)

        assert backend.capabilities is override

    @pytest.mark.parametrize(
        "processor_attr",
        [
            pytest.param("image_processor", id="image_processor"),
            pytest.param("feature_extractor", id="feature_extractor"),
            pytest.param("audio_processor", id="audio_processor"),
        ],
    )
    def test_renderer_returns_engine_processor_when_present(self, engine, processor_attr: str) -> None:
        processor = Mock(spec=[processor_attr])
        setattr(processor, processor_attr, Mock())
        engine.processor = processor

        backend = self._make_backend(engine=engine)

        assert backend._renderer is processor
        assert backend._renderer is processor

    def test_renderer_falls_back_to_tokenizer_when_engine_processor_lacks_multimodal_attrs(self, engine) -> None:
        candidate = Mock(spec=[])
        engine.processor = candidate
        engine.tokenizer = Mock(tokenizer="tok-sentinel")

        backend = self._make_backend(engine=engine)

        assert backend._renderer == "tok-sentinel"

    @pytest.mark.parametrize(
        "processor_attr",
        [
            pytest.param("image_processor", id="image_processor"),
            pytest.param("feature_extractor", id="feature_extractor"),
            pytest.param("audio_processor", id="audio_processor"),
        ],
    )
    def test_renderer_falls_back_to_auto_processor(self, engine, processor_attr: str) -> None:
        loaded = Mock(spec=[processor_attr])
        setattr(loaded, processor_attr, Mock())
        auto_processor = Mock()
        auto_processor.from_pretrained = Mock(return_value=loaded)

        with patch("flama.models.engine.backend.llm.vllm.AutoProcessor", auto_processor):
            backend = self._make_backend(engine=engine, model_dir=pathlib.Path("/tmp/model"))
            assert backend._renderer is loaded

        assert auto_processor.from_pretrained.call_args == call("/tmp/model", trust_remote_code=True)

    def test_renderer_falls_back_to_tokenizer_when_loaded_lacks_multimodal_attrs(self, engine) -> None:
        loaded = Mock(spec=[])
        auto_processor = Mock()
        auto_processor.from_pretrained = Mock(return_value=loaded)
        engine.tokenizer = Mock(tokenizer="tok-sentinel")

        with patch("flama.models.engine.backend.llm.vllm.AutoProcessor", auto_processor):
            backend = self._make_backend(engine=engine, model_dir=pathlib.Path("/tmp/model"))
            assert backend._renderer == "tok-sentinel"
