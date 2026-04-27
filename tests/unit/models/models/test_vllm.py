import typing as t
from unittest.mock import MagicMock, Mock, patch

import pytest

from flama import exceptions
from flama.models.models.vllm import CudaModel, MetalModel


class _FakeRequestOutputKind:
    DELTA = "DELTA"
    FINAL_ONLY = "FINAL_ONLY"


class _FakeMlxResp:
    def __init__(self, text: str) -> None:
        self.text = text


def _cuda_output(text: str) -> Mock:
    out = Mock()
    out.outputs = [Mock(text=text)]
    return out


def _bad_cuda_output() -> Mock:
    bad = Mock()
    bad.outputs.__getitem__ = Mock(side_effect=IndexError("no outputs"))
    return bad


async def _aiter(*items: t.Any) -> t.AsyncIterator[t.Any]:
    for item in items:
        yield item


async def _failing_aiter(error: Exception) -> t.AsyncIterator[t.Any]:
    raise error
    yield  # pragma: no cover


class TestCaseCudaModel:
    @pytest.fixture(scope="function")
    def engine(self):
        return Mock()

    @pytest.mark.parametrize(
        ["has_shutdown"],
        [
            pytest.param(True, id="with-shutdown"),
            pytest.param(False, id="without-shutdown"),
        ],
    )
    def test_init(self, engine, has_shutdown):
        if has_shutdown:
            engine.shutdown = Mock()
        else:
            del engine.shutdown

        with patch("flama.models.models.vllm.weakref") as mock_weakref:
            model = CudaModel(engine, MagicMock(), None)

        assert model.model is engine
        if has_shutdown:
            mock_weakref.finalize.assert_called_once_with(model, engine.shutdown)
        else:
            mock_weakref.finalize.assert_not_called()

    @pytest.mark.parametrize(
        ["installed", "outputs", "expected", "exception"],
        [
            pytest.param(True, ["Hello", " ", "world"], ["Hello", " ", "world"], None, id="success"),
            pytest.param(True, [], [], None, id="empty"),
            pytest.param(True, ["Hello", "", "world"], ["Hello", "world"], None, id="skip-empty"),
            pytest.param(False, None, None, exceptions.FrameworkNotInstalled, id="not-installed"),
            pytest.param(True, "access-error", None, IndexError, id="access-error"),
            pytest.param(True, "engine-error", None, RuntimeError, id="engine-error"),
        ],
    )
    async def test_tokens(self, engine, installed, outputs, expected, exception):
        if outputs == "access-error":
            engine.generate.return_value = _aiter(_cuda_output("Hello"), _bad_cuda_output())
        elif outputs == "engine-error":
            engine.generate.return_value = _failing_aiter(RuntimeError("engine boom"))
        elif outputs is not None:
            engine.generate.return_value = _aiter(*(_cuda_output(text) for text in outputs))

        model = CudaModel(engine, MagicMock(), None)

        with (
            patch("flama.models.models.vllm.vllm", MagicMock() if installed else None),
            patch("flama.models.models.vllm.RequestOutputKind", _FakeRequestOutputKind if installed else None),
        ):
            if exception is not None:
                with pytest.raises(exception):
                    async for _ in model._tokens("prompt"):
                        pass
            else:
                tokens = [token async for token in model._tokens("prompt")]
                assert tokens == expected


class TestCaseMetalModel:
    @pytest.fixture(scope="function")
    def runner(self):
        runner = Mock()
        runner.model = Mock()
        runner.tokenizer = Mock()
        return runner

    @pytest.mark.parametrize(
        ["installed", "chunks", "expected", "exception"],
        [
            pytest.param(True, ["Hello", " ", "world"], ["Hello", " ", "world"], None, id="success"),
            pytest.param(True, [], [], None, id="empty"),
            pytest.param(True, ["Hello", "", "world"], ["Hello", "world"], None, id="skip-empty"),
            pytest.param(False, None, None, exceptions.FrameworkNotInstalled, id="not-installed"),
        ],
    )
    async def test_tokens(self, runner, installed, chunks, expected, exception):
        mock_stream_generate = Mock()
        mock_make_sampler = Mock(return_value="sampler_obj")

        if chunks is not None:
            mock_stream_generate.return_value = iter([_FakeMlxResp(text) for text in chunks])

        model = MetalModel(runner, MagicMock(), None)

        with (
            patch("flama.models.models.vllm.stream_generate", mock_stream_generate if installed else None),
            patch("flama.models.models.vllm.make_sampler", mock_make_sampler if installed else None),
        ):
            if exception is not None:
                with pytest.raises(exception):
                    async for _ in model._tokens("prompt"):
                        pass
            else:
                tokens = [token async for token in model._tokens("prompt")]
                assert tokens == expected
                mock_make_sampler.assert_called_once_with(temp=0.0)
                mock_stream_generate.assert_called_once()
                _, call_kwargs = mock_stream_generate.call_args
                assert call_kwargs["prompt"] == "prompt"
                assert call_kwargs["sampler"] == "sampler_obj"
                assert call_kwargs["max_tokens"] == 256

    async def test_tokens_param_overrides(self, runner):
        mock_stream_generate = Mock(return_value=iter([_FakeMlxResp("ok")]))
        mock_make_sampler = Mock(return_value="sampler_obj")

        model = MetalModel(runner, MagicMock(), None)
        model.params = {"temperature": 0.7, "max_tokens": 128}

        with (
            patch("flama.models.models.vllm.stream_generate", mock_stream_generate),
            patch("flama.models.models.vllm.make_sampler", mock_make_sampler),
        ):
            tokens = [token async for token in model._tokens("prompt", max_new_tokens=64)]

        assert tokens == ["ok"]
        mock_make_sampler.assert_called_once_with(temp=0.7)
        _, call_kwargs = mock_stream_generate.call_args
        assert call_kwargs["max_tokens"] == 128
