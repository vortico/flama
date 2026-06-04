import asyncio
import contextlib
import pathlib
import threading
import time
import typing as t
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from flama import exceptions
from flama.models.engine.backend.llm.mlx import MLXBackend, MlxRuntime
from flama.models.engine.llm.delta import EngineDelta
from flama.models.engine.llm.input import EngineInput
from flama.serialize.data_structures import LLMModelCapabilities
from flama.serialize.exceptions import UnknownModelCapabilities
from flama.serialize.model_serializers.transformers import ModelSerializer as TransformersModelSerializer


class _FakeMlxResp:
    def __init__(
        self,
        text: str,
        *,
        generation_tokens: int | None = None,
        finish_reason: str | None = None,
    ) -> None:
        self.text = text
        if generation_tokens is not None:
            self.generation_tokens = generation_tokens
        if finish_reason is not None:
            self.finish_reason = finish_reason


class _TrackingIterator:
    """Synchronous iterator that records ``close()`` and (optionally) gates each ``__next__``.

    The optional events let cancellation tests assert the shield + ``threading.Lock`` invariants:
    in-flight ``next(iterator)`` calls run to completion before ``close()`` acquires the lock.
    """

    def __init__(
        self,
        chunks: list[str],
        *,
        step_started: threading.Event | None = None,
        step_can_finish: threading.Event | None = None,
        step_finished_log: list[float] | None = None,
    ) -> None:
        self._chunks = list(chunks)
        self._step_started = step_started
        self._step_can_finish = step_can_finish
        self._step_finished_log = [] if step_finished_log is None else step_finished_log
        self.close_called = threading.Event()

    def __iter__(self) -> "_TrackingIterator":
        return self

    def __next__(self) -> _FakeMlxResp:
        if self._step_started is not None:
            self._step_started.set()
        if self._step_can_finish is not None:
            self._step_can_finish.wait()
        self._step_finished_log.append(time.monotonic())
        if not self._chunks:
            raise StopIteration
        return _FakeMlxResp(self._chunks.pop(0))

    def close(self) -> None:
        self.close_called.set()


class TestCaseMLXBackend:
    MAX_CONTEXT: t.ClassVar[int] = 8192

    @classmethod
    def _make_backend(
        cls,
        *,
        model: Mock | None = None,
        tokenizer: Mock | None = None,
        processor: Mock | None = None,
        capabilities: LLMModelCapabilities | None = None,
        model_dir: pathlib.Path | None = None,
        **engine_params: t.Any,
    ) -> MLXBackend:
        """Build an :class:`MLXBackend` with ``mlx_lm.load`` / ``mlx_vlm.load`` mocked out.

        Dispatch keys off the resolved capabilities: when *capabilities* is multimodal (or
        *processor* is given), the constructor goes through ``mlx_vlm.load``; otherwise it goes
        through ``mlx_lm.load``.
        """
        if model is None:
            model = Mock()
        if tokenizer is None:
            tokenizer = Mock()

        multimodal = (capabilities is not None and capabilities.is_multimodal) or processor is not None
        resolved = capabilities or (
            LLMModelCapabilities(text=True, image=True) if multimodal else LLMModelCapabilities(text=True)
        )

        target_dir = model_dir or pathlib.Path("/tmp/model")

        patches: list[t.Any] = [
            patch.object(TransformersModelSerializer, "detect_capabilities", return_value=resolved),
        ]
        if multimodal:
            proc = processor if processor is not None else Mock(tokenizer=tokenizer)
            patches.append(patch("flama.models.engine.backend.llm.mlx.mlx_vlm_load", Mock(return_value=(model, proc))))
        else:
            patches.append(
                patch("flama.models.engine.backend.llm.mlx.mlx_lm_load", Mock(return_value=(model, tokenizer)))
            )

        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            return MLXBackend(target_dir, capabilities=capabilities, **engine_params)

    @pytest.fixture(scope="function")
    def text_runtime_args(self) -> dict[str, t.Any]:
        # Seed the candidate the text probe walks first (``model.args``) so :meth:`MLXBackend._max_context` finds a
        # usable int — without it every text-runtime test would log a warning and silently fall back to
        # :attr:`LLMBackend.DEFAULT_MAX_TOKENS`. Probe-specific tests reset ``model`` to a fresh Mock to bypass this.
        model = Mock()
        model.args = Mock(max_position_embeddings=self.MAX_CONTEXT)
        model.config = Mock(spec=[])
        return {"model": model, "tokenizer": Mock()}

    @pytest.fixture(scope="function")
    def vlm_runtime_args(self) -> dict[str, t.Any]:
        processor = Mock()
        # Encode returns a fixed two-element list so the multimodal generate fallback path that
        # calls ``processor.tokenizer.encode(text, add_special_tokens=False)`` to recover a per-step
        # ``token_count`` (when ``generation_tokens`` is missing) gets a length it can ``len()``.
        processor.tokenizer = Mock(encode=Mock(return_value=[0, 0]))
        processor.image_processor = Mock()
        # mlx-vlm exposes ``max_position_embeddings`` on ``model.config`` (sometimes nested under ``text_config``);
        # seed both candidates so any probe path returns the same sentinel.
        model = Mock()
        model.args = Mock(spec=[])
        model.config = Mock(max_position_embeddings=self.MAX_CONTEXT, text_config=None)
        return {
            "model": model,
            "processor": processor,
            "tokenizer": processor.tokenizer,
            "capabilities": LLMModelCapabilities(text=True, image=True),
        }

    def test_init_text_runtime_uses_mlx_lm(self):
        model = Mock()
        tokenizer = Mock()
        mlx_lm_load = Mock(return_value=(model, tokenizer))

        text_cap = LLMModelCapabilities(text=True)
        with (
            patch("flama.models.engine.backend.llm.mlx.mlx_lm_load", mlx_lm_load),
            patch.object(TransformersModelSerializer, "detect_capabilities", return_value=text_cap),
        ):
            backend = MLXBackend(pathlib.Path("/tmp/model"))

        assert backend.model.model is model
        assert backend.model.tokenizer is tokenizer
        assert backend.model.processor is None
        assert backend.capabilities == LLMModelCapabilities(text=True)
        assert mlx_lm_load.call_args == call("/tmp/model")

    def test_init_multimodal_runtime_uses_mlx_vlm(self):
        model = Mock()
        processor = Mock()
        processor.tokenizer = Mock()
        mlx_vlm_load = Mock(return_value=(model, processor))
        override = LLMModelCapabilities(text=True, image=True)

        with patch("flama.models.engine.backend.llm.mlx.mlx_vlm_load", mlx_vlm_load):
            backend = MLXBackend(pathlib.Path("/tmp/model"), capabilities=override)

        assert backend.model.model is model
        assert backend.model.processor is processor
        assert backend.model.tokenizer is processor.tokenizer
        assert backend.capabilities is override
        assert mlx_vlm_load.call_args == call("/tmp/model")

    def test_init_raises_on_unknown_capabilities(self):
        with (
            patch("flama.models.engine.backend.llm.mlx.mlx_lm_load", Mock()),
            patch("flama.models.engine.backend.llm.mlx.mlx_vlm_load", Mock()),
            patch.object(TransformersModelSerializer, "detect_capabilities", return_value=None),
            pytest.raises(UnknownModelCapabilities),
        ):
            MLXBackend(pathlib.Path("/tmp/model"))

    def test_init_text_raises_when_mlx_lm_missing(self):
        text_cap = LLMModelCapabilities(text=True)
        with (
            patch("flama.models.engine.backend.llm.mlx.mlx_lm_load", None),
            patch.object(TransformersModelSerializer, "detect_capabilities", return_value=text_cap),
            pytest.raises(exceptions.FrameworkNotInstalled),
        ):
            MLXBackend(pathlib.Path("/tmp/model"))

    def test_init_multimodal_raises_when_mlx_vlm_missing(self):
        with (
            patch("flama.models.engine.backend.llm.mlx.mlx_vlm_load", None),
            pytest.raises(exceptions.FrameworkNotInstalled),
        ):
            MLXBackend(pathlib.Path("/tmp/model"), capabilities=LLMModelCapabilities(text=True, image=True))

    def test_tokenizer(self, text_runtime_args):
        backend = self._make_backend(**text_runtime_args)

        assert backend._tokenizer is text_runtime_args["tokenizer"]

    @pytest.mark.parametrize(
        "capabilities",
        [
            pytest.param(LLMModelCapabilities(text=True), id="text_only"),
            pytest.param(LLMModelCapabilities(text=True, image=True), id="image"),
            pytest.param(LLMModelCapabilities(text=True, audio=True), id="audio"),
            pytest.param(LLMModelCapabilities(text=True, image=True, audio=True), id="image_and_audio"),
        ],
    )
    def test_detect_capabilities_lifts_from_runtime(self, capabilities: LLMModelCapabilities) -> None:
        backend = self._make_backend(capabilities=capabilities)

        assert backend.capabilities == capabilities

    def test_text_runtime_renderer_is_tokenizer(self, text_runtime_args) -> None:
        backend = self._make_backend(**text_runtime_args)

        assert backend.capabilities.is_multimodal is False
        assert backend._renderer is text_runtime_args["tokenizer"]

    def test_multimodal_runtime_dispatches_to_processor(self, vlm_runtime_args) -> None:
        backend = self._make_backend(**vlm_runtime_args)

        assert backend.capabilities.is_multimodal is True
        assert backend._tokenizer is vlm_runtime_args["processor"].tokenizer
        assert backend._renderer is vlm_runtime_args["processor"]

    @pytest.mark.parametrize(
        [
            "images",
            "audios",
            "expected_processor_kwargs",
            "expected_extras",
            "chunks",
            "expected_text",
            "expected_token_count",
            "expected_finish_reason",
        ],
        [
            pytest.param(
                (),
                (),
                None,
                {},
                [_FakeMlxResp("hello")],
                ["hello"],
                # Encode-fallback path: chunk has no ``generation_tokens``, so ``token_count``
                # equals the length of the seeded ``processor.tokenizer.encode`` return value.
                [2],
                [None],
                id="text_only",
            ),
            pytest.param(
                ("pil-image-sentinel",),
                (),
                {
                    "text": "",
                    "return_tensors": "mlx",
                    "add_special_tokens": False,
                    "images": ["pil-image-sentinel"],
                },
                {"pixel_values": "pixel-values-sentinel"},
                [_FakeMlxResp("hello")],
                ["hello"],
                [2],
                [None],
                id="image_only",
            ),
            pytest.param(
                (),
                (("waveform", 16000),),
                {
                    "text": "",
                    "return_tensors": "mlx",
                    "add_special_tokens": False,
                    "audio": [("waveform", 16000)],
                },
                {"input_features": "audio-features-sentinel", "input_features_mask": "audio-mask-sentinel"},
                [_FakeMlxResp("hello")],
                ["hello"],
                [2],
                [None],
                id="audio_only",
            ),
            pytest.param(
                ("pil-image-sentinel",),
                (("waveform", 16000),),
                {
                    "text": "",
                    "return_tensors": "mlx",
                    "add_special_tokens": False,
                    "images": ["pil-image-sentinel"],
                    "audio": [("waveform", 16000)],
                },
                {
                    "pixel_values": "pixel-values-sentinel",
                    "input_features": "audio-features-sentinel",
                    "input_features_mask": "audio-mask-sentinel",
                },
                [_FakeMlxResp("hello")],
                ["hello"],
                [2],
                [None],
                id="image_and_audio",
            ),
            pytest.param(
                (),
                (),
                None,
                {},
                [
                    _FakeMlxResp("Hello", generation_tokens=3),
                    _FakeMlxResp(" world", generation_tokens=5),
                    _FakeMlxResp("!", generation_tokens=8, finish_reason="stop"),
                ],
                ["Hello", " world", "!"],
                [3, 2, 3],
                [None, None, "stop"],
                id="generation_tokens_diff",
            ),
            pytest.param(
                (),
                (),
                None,
                {},
                [_FakeMlxResp("Hi"), _FakeMlxResp(" there", finish_reason="length")],
                ["Hi", " there"],
                [2, 2],
                [None, "length"],
                id="encode_fallback_with_finish_reason",
            ),
            pytest.param(
                (),
                (),
                None,
                {},
                [_FakeMlxResp("", finish_reason="stop")],
                [""],
                [None],
                ["stop"],
                id="empty_text_terminal_chunk",
            ),
        ],
    )
    async def test_generate_dispatches_to_mlx_vlm(
        self,
        vlm_runtime_args,
        images: tuple[t.Any, ...],
        audios: tuple[t.Any, ...],
        expected_processor_kwargs: dict[str, t.Any] | None,
        expected_extras: dict[str, t.Any],
        chunks: list[_FakeMlxResp],
        expected_text: list[str],
        expected_token_count: list[int | None],
        expected_finish_reason: list[str | None],
    ) -> None:
        """Multimodal path uses ``input_ids`` bypass and surfaces per-step metadata.

        Dispatch: pre-tokenised ``list[int]`` is forwarded as ``input_ids`` (never as
        ``prompt`` — that path corrupts the KV cache by inflating the batch dimension), and
        the bound :class:`~transformers.AutoProcessor` is invoked only when decoded images /
        audios need rendering.

        Per-step metadata: ``token_count`` comes from ``generation_tokens`` diffs when the
        runtime exposes them and falls back to encoding the chunk text through
        :attr:`MlxRuntime.tokenizer` otherwise. ``finish_reason`` is propagated verbatim so
        the codec's stop-reason mapping sees the engine signal, including for terminal chunks
        with empty text.
        """
        mock_vlm_stream_generate = Mock(return_value=iter(chunks))
        mock_make_sampler = Mock(return_value="sampler")
        mock_mx = Mock()
        mock_mx.array = Mock(side_effect=lambda value: ("mx-array", value))
        backend = self._make_backend(**vlm_runtime_args)
        backend.model.processor.return_value = {
            "input_ids": "ignored-ids",
            "attention_mask": "ignored-mask",
            **{k: v for k, v in expected_extras.items()},
        }
        inputs = EngineInput(tokens=[1, 2, 3], images=images, audios=audios)

        with (
            patch("flama.models.engine.backend.llm.mlx.mlx_vlm_stream_generate", mock_vlm_stream_generate),
            patch("flama.models.engine.backend.llm.mlx.make_sampler", mock_make_sampler),
            patch("flama.models.engine.backend.llm.mlx.mx", mock_mx),
        ):
            deltas = [d async for d in backend.generate(inputs)]

        assert [d.text for d in deltas] == expected_text
        assert [d.token_count for d in deltas] == expected_token_count
        assert [d.finish_reason for d in deltas] == expected_finish_reason
        _, call_kwargs = mock_vlm_stream_generate.call_args
        assert call_kwargs["prompt"] == ""
        assert call_kwargs["input_ids"] == ("mx-array", [[1, 2, 3]])
        assert "image" not in call_kwargs
        assert "audio" not in call_kwargs
        assert call_kwargs["sampler"] == "sampler"
        assert call_kwargs["max_tokens"] == self.MAX_CONTEXT - len(inputs.tokens)
        for key, value in expected_extras.items():
            assert call_kwargs[key] == value
        if expected_processor_kwargs is None:
            assert not backend.model.processor.called
        else:
            _, processor_call_kwargs = backend.model.processor.call_args
            assert processor_call_kwargs == expected_processor_kwargs

    @pytest.mark.parametrize(
        ["mlx_vlm_installed", "mx_installed"],
        [
            pytest.param(False, True, id="mlx_vlm_missing"),
            pytest.param(True, False, id="mx_core_missing"),
        ],
    )
    async def test_generate_vision_raises_when_dependencies_missing(
        self, vlm_runtime_args, mlx_vlm_installed: bool, mx_installed: bool
    ) -> None:
        backend = self._make_backend(**vlm_runtime_args)
        with (
            patch(
                "flama.models.engine.backend.llm.mlx.mlx_vlm_stream_generate",
                Mock() if mlx_vlm_installed else None,
            ),
            patch("flama.models.engine.backend.llm.mlx.make_sampler", Mock()),
            patch("flama.models.engine.backend.llm.mlx.mx", Mock() if mx_installed else None),
            pytest.raises(exceptions.FrameworkNotInstalled),
        ):
            [d async for d in backend.generate(EngineInput(tokens=[1]))]

    @pytest.mark.parametrize(
        ["installed", "chunks", "expected_text", "expected_token_count", "expected_finish_reason", "exception"],
        [
            pytest.param(
                True,
                [_FakeMlxResp("Hello"), _FakeMlxResp(" "), _FakeMlxResp("world")],
                ["Hello", " ", "world"],
                [1, 1, 1],
                [None, None, None],
                None,
                id="success",
            ),
            pytest.param(True, [], [], [], [], None, id="empty"),
            pytest.param(
                True,
                [_FakeMlxResp("Hello"), _FakeMlxResp(""), _FakeMlxResp("world")],
                ["Hello", "world"],
                [1, 1],
                [None, None],
                None,
                id="skip_empty",
            ),
            pytest.param(
                True,
                [
                    _FakeMlxResp("Hello"),
                    _FakeMlxResp(" world", finish_reason="length"),
                ],
                ["Hello", " world"],
                [1, 1],
                [None, "length"],
                None,
                id="propagates_finish_reason",
            ),
            pytest.param(
                True,
                [_FakeMlxResp("", finish_reason="stop")],
                [""],
                [None],
                ["stop"],
                None,
                id="empty_text_terminal_chunk",
            ),
            pytest.param(False, None, None, None, None, exceptions.FrameworkNotInstalled, id="not_installed"),
        ],
        indirect=["exception"],
    )
    async def test_generate(
        self,
        text_runtime_args,
        installed,
        chunks,
        expected_text,
        expected_token_count,
        expected_finish_reason,
        exception,
    ):
        mock_stream_generate = Mock()
        mock_make_sampler = Mock(return_value="sampler_obj")

        if chunks is not None:
            mock_stream_generate.return_value = iter(chunks)

        backend = self._make_backend(**text_runtime_args)
        tokens = [10, 20, 30]
        inputs = EngineInput(tokens=tokens)

        with (
            patch("flama.models.engine.backend.llm.mlx.stream_generate", mock_stream_generate if installed else None),
            patch("flama.models.engine.backend.llm.mlx.make_sampler", mock_make_sampler if installed else None),
            exception,
        ):
            deltas = [delta async for delta in backend.generate(inputs)]
            assert [d.text for d in deltas] == expected_text
            assert [d.token_count for d in deltas] == expected_token_count
            assert [d.finish_reason for d in deltas] == expected_finish_reason
            if installed:
                assert mock_make_sampler.call_args_list == [call(temp=0.0)]
                assert mock_stream_generate.call_count == 1
                _, call_kwargs = mock_stream_generate.call_args
                assert call_kwargs["prompt"] == tokens
                assert call_kwargs["sampler"] == "sampler_obj"
                assert call_kwargs["max_tokens"] == self.MAX_CONTEXT - len(tokens)

    async def test_generate_param_overrides(self, text_runtime_args):
        mock_stream_generate = Mock(return_value=iter([_FakeMlxResp("ok")]))
        mock_make_sampler = Mock(return_value="sampler_obj")

        backend = self._make_backend(**text_runtime_args)

        with (
            patch("flama.models.engine.backend.llm.mlx.stream_generate", mock_stream_generate),
            patch("flama.models.engine.backend.llm.mlx.make_sampler", mock_make_sampler),
        ):
            inputs = EngineInput(tokens=[1, 2])
            deltas = [delta async for delta in backend.generate(inputs, temperature=0.7, max_new_tokens=64)]

        assert [d.text for d in deltas] == ["ok"]
        assert mock_make_sampler.call_args_list == [call(temp=0.7)]
        _, call_kwargs = mock_stream_generate.call_args
        assert call_kwargs["max_tokens"] == 64
        assert call_kwargs["prompt"] == [1, 2]

    def test_max_context_probes_text_runtime(self, text_runtime_args):
        text_runtime_args["model"] = Mock()
        text_runtime_args["model"].args = Mock(max_position_embeddings=2048)
        # Force the other candidate paths to look unset so we exercise the ``args`` branch in isolation.
        text_runtime_args["model"].config = Mock(spec=[])
        backend = self._make_backend(**text_runtime_args)

        assert backend._max_context() == 2048

    def test_max_context_probes_multimodal_text_config(self, vlm_runtime_args):
        vlm_runtime_args["model"] = Mock(spec=["config"])
        vlm_runtime_args["model"].config = Mock(text_config=Mock(max_position_embeddings=4096))
        backend = self._make_backend(**vlm_runtime_args)

        assert backend._max_context() == 4096

    def test_max_context_probes_multimodal_top_level_config(self, vlm_runtime_args):
        vlm_runtime_args["model"] = Mock(spec=["config"])
        vlm_runtime_args["model"].config = Mock(spec=["max_position_embeddings", "text_config"])
        vlm_runtime_args["model"].config.max_position_embeddings = 1024
        vlm_runtime_args["model"].config.text_config = None
        backend = self._make_backend(**vlm_runtime_args)

        assert backend._max_context() == 1024

    def test_max_context_falls_back_to_tokenizer_model_max_length(self, text_runtime_args):
        text_runtime_args["model"] = Mock(spec=[])
        text_runtime_args["tokenizer"] = Mock(model_max_length=512)
        backend = self._make_backend(**text_runtime_args)

        assert backend._max_context() == 512

    def test_max_context_returns_none_when_probe_paths_empty(self, text_runtime_args):
        text_runtime_args["model"] = Mock(spec=[])
        # Tokenizer ``model_max_length`` carries an ``int(1e30)`` sentinel for "not configured" — discarded.
        text_runtime_args["tokenizer"] = Mock(model_max_length=int(1e30))
        backend = self._make_backend(**text_runtime_args)

        assert backend._max_context() is None

    def test_max_context_logs_warning_and_uses_default_when_probe_fails(self, text_runtime_args, caplog):
        text_runtime_args["model"] = Mock(spec=[])
        text_runtime_args["tokenizer"] = Mock(model_max_length=int(1e30))
        backend = self._make_backend(**text_runtime_args)

        with caplog.at_level("WARNING", logger="flama.models.engine.backend.llm.base"):
            assert backend.max_context == MLXBackend.DEFAULT_MAX_TOKENS

        assert any("Cannot determine model context window" in record.message for record in caplog.records)

    @pytest.mark.parametrize("invalid", [0, -1, -100])
    async def test_generate_raises_on_non_positive_max_tokens(self, text_runtime_args, invalid: int) -> None:
        backend = self._make_backend(**text_runtime_args)

        with (
            patch("flama.models.engine.backend.llm.mlx.stream_generate", Mock()),
            patch("flama.models.engine.backend.llm.mlx.make_sampler", Mock(return_value="sampler")),
            pytest.raises(ValueError, match="max_tokens must be a positive integer"),
        ):
            [d async for d in backend.generate(EngineInput(tokens=[1]), max_tokens=invalid)]

    def test_init_per_instance_executor(self, text_runtime_args) -> None:
        """Each backend owns its own single-thread executor; sharing one would serialise unrelated models."""
        a, b = self._make_backend(**text_runtime_args), self._make_backend(**text_runtime_args)

        assert a._executor is not b._executor
        assert a._executor._max_workers == 1
        assert b._executor._max_workers == 1

    async def test_generate_closes_iterator_on_normal_exit(self, text_runtime_args) -> None:
        """Reaching the natural end of the MLX iterator runs ``_close`` and releases iterator resources."""
        tracker = _TrackingIterator(["a", "b"])
        backend = self._make_backend(**text_runtime_args)

        with (
            patch("flama.models.engine.backend.llm.mlx.stream_generate", Mock(return_value=tracker)),
            patch("flama.models.engine.backend.llm.mlx.make_sampler", Mock(return_value="sampler")),
        ):
            deltas = [d async for d in backend.generate(EngineInput(tokens=[1]))]

        assert [d.text for d in deltas] == ["a", "b"]
        assert tracker.close_called.is_set()

    async def test_generate_closes_iterator_on_cancellation(self, text_runtime_args) -> None:
        """Cancellation still runs ``_close`` via the detached shielded inner task in ``finally``."""
        step_started = threading.Event()
        step_can_finish = threading.Event()
        step_can_finish.set()
        tracker = _TrackingIterator(
            ["chunk"],
            step_started=step_started,
            step_can_finish=step_can_finish,
        )
        backend = self._make_backend(**text_runtime_args)

        with (
            patch("flama.models.engine.backend.llm.mlx.stream_generate", Mock(return_value=tracker)),
            patch("flama.models.engine.backend.llm.mlx.make_sampler", Mock(return_value="sampler")),
        ):

            async def _consume() -> None:
                async for _ in backend.generate(EngineInput(tokens=[1])):
                    await asyncio.sleep(60)

            task = asyncio.create_task(_consume())
            await asyncio.to_thread(step_started.wait, 5.0)

            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

            await asyncio.to_thread(tracker.close_called.wait, 5.0)

        assert tracker.close_called.is_set()

    async def test_generate_closes_iterator_on_aclose(self, text_runtime_args) -> None:
        """``aclose()`` (the deterministic equivalent of consumer cancellation) runs ``_close`` via the
        ``finally`` block - covering the path ``async for`` cleanup takes when its body raises."""
        tracker = _TrackingIterator(["a", "b", "c"])
        backend = self._make_backend(**text_runtime_args)

        with (
            patch("flama.models.engine.backend.llm.mlx.stream_generate", Mock(return_value=tracker)),
            patch("flama.models.engine.backend.llm.mlx.make_sampler", Mock(return_value="sampler")),
        ):
            gen = t.cast(t.AsyncGenerator[EngineDelta, None], backend.generate(EngineInput(tokens=[1])))
            first = await anext(gen)
            await gen.aclose()

        assert first.text == "a"
        assert tracker.close_called.is_set()

    async def test_generate_serialises_steps_via_single_thread_executor(self, text_runtime_args) -> None:
        """The dedicated single-worker executor serialises every ``next(iterator)`` and ``close()`` for
        the backend, taking the place the previous per-instance ``threading.Lock`` held: MLX's
        Metal/CUDA stream is bound to whichever thread first allocates the model, so subsequent
        steps must come from that same worker. The check below exercises the invariant indirectly
        - a multi-step generation completes against the executor without leaking workers - and
        cross-references the executor's worker count to confirm it stays pinned at one."""
        step_started = threading.Event()
        step_can_finish = threading.Event()
        step_can_finish.set()
        tracker = _TrackingIterator(
            ["a", "b"],
            step_started=step_started,
            step_can_finish=step_can_finish,
        )
        backend = self._make_backend(**text_runtime_args)

        with (
            patch("flama.models.engine.backend.llm.mlx.stream_generate", Mock(return_value=tracker)),
            patch("flama.models.engine.backend.llm.mlx.make_sampler", Mock(return_value="sampler")),
        ):
            deltas = [d async for d in backend.generate(EngineInput(tokens=[1]))]

        assert [d.text for d in deltas] == ["a", "b"]
        assert backend._executor._max_workers == 1
        assert tracker.close_called.is_set()

    def test_tqdm_disable_default_baked_at_import(self) -> None:
        """The HACK at the top of ``flama/models/engine/backend/llm/mlx.py`` sets ``TQDM_DISABLE=1``
        around the ``mlx_lm`` / ``mlx_vlm`` imports so :func:`mlx_vlm.stream_generate`'s chunked-prefill
        ``tqdm`` bar is silenced. ``tqdm`` reads ``TQDM_*`` env vars once at decoration time via
        ``@envwrap`` and stores them on ``tqdm.std.tqdm.__init__``'s :class:`functools.partialmethod`
        keyword defaults; this test asserts that snapshot landed (i.e. ``mlx_lm`` / ``mlx_vlm`` were
        the first transitive importers of ``tqdm`` in the test process). If it fails, an earlier
        importer captured ``TQDM_DISABLE=None`` and the silencing is no longer in effect — fix the
        import order so ``mlx.py`` (or another module that snapshots the env var) lands first.
        """
        import functools

        from tqdm.std import tqdm as _Tqdm

        init = _Tqdm.__dict__["__init__"]
        assert isinstance(init, functools.partialmethod)
        assert init.keywords.get("disable") is True


class TestCaseMlxRuntime:
    def test_default_values(self):
        runtime = MlxRuntime(model=Mock(), tokenizer=Mock())

        assert runtime.processor is None
        assert runtime.capabilities == LLMModelCapabilities()

    def test_attaches_processor_and_capabilities(self):
        processor = Mock()
        capabilities = LLMModelCapabilities(text=True, image=True)

        runtime = MlxRuntime(
            model=MagicMock(),
            tokenizer=MagicMock(),
            processor=processor,
            capabilities=capabilities,
        )

        assert runtime.processor is processor
        assert runtime.capabilities is capabilities
