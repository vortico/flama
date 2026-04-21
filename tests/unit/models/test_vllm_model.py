from unittest.mock import MagicMock, call, patch

import pytest

from flama import exceptions


class _FakeRequestOutputKind:
    FINAL_ONLY = "FINAL_ONLY"
    DELTA = "DELTA"


def _make_model(**extra_params):
    """Create a vLLM Model with mocked dependencies."""
    with (
        patch("flama.models.models.vllm.vllm") as mock_vllm,
        patch("flama.models.models.vllm.RequestOutputKind", _FakeRequestOutputKind),
    ):
        mock_vllm.SamplingParams = MagicMock()

        from flama.models.models.vllm import Model

        meta = MagicMock()
        meta.to_dict.return_value = {}
        engine = MagicMock()
        model = Model(engine, meta, None)
        if extra_params:
            model.configure(extra_params)
    return model, engine, mock_vllm


class TestCaseVLLMModelLifecycle:
    @pytest.mark.parametrize(
        ("has_shutdown", "expected_calls"),
        (
            pytest.param(True, [call()], id="with-shutdown"),
            pytest.param(False, [], id="without-shutdown"),
        ),
    )
    def test_shutdown_engine(self, has_shutdown, expected_calls):
        from flama.models.models.vllm import Model

        engine = MagicMock() if has_shutdown else MagicMock(spec=[])

        Model._shutdown_engine(engine)

        if has_shutdown:
            assert engine.shutdown.call_args_list == expected_calls
        else:
            assert not hasattr(engine, "shutdown")


async def _aiter_from(*items):
    for item in items:
        yield item


class TestCaseVLLMModelQuery:
    @pytest.mark.anyio
    async def test_query_success(self):
        model, engine, mock_vllm = _make_model()

        output = MagicMock()
        output.outputs = [MagicMock(text="Hello world")]
        engine.generate.return_value = _aiter_from(output)

        with (
            patch("flama.models.models.vllm.vllm", mock_vllm),
            patch("flama.models.models.vllm.RequestOutputKind", _FakeRequestOutputKind),
        ):
            result = await model.query("test prompt")

        assert result == "Hello world"

    @pytest.mark.anyio
    async def test_query_empty_output_raises_500(self):
        model, engine, mock_vllm = _make_model()

        engine.generate.return_value = _aiter_from()

        with (
            patch("flama.models.models.vllm.vllm", mock_vllm),
            patch("flama.models.models.vllm.RequestOutputKind", _FakeRequestOutputKind),
        ):
            with pytest.raises(exceptions.HTTPException) as exc_info:
                await model.query("test prompt")

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "vLLM engine produced no output"

    @pytest.mark.anyio
    async def test_query_engine_error_raises_400(self):
        model, engine, mock_vllm = _make_model()

        async def _failing_generate(*args, **kwargs):
            raise RuntimeError("Engine exploded")
            yield  # pragma: no cover

        engine.generate.return_value = _failing_generate()

        with (
            patch("flama.models.models.vllm.vllm", mock_vllm),
            patch("flama.models.models.vllm.RequestOutputKind", _FakeRequestOutputKind),
        ):
            with pytest.raises(exceptions.HTTPException) as exc_info:
                await model.query("test prompt")

        assert exc_info.value.status_code == 400
        assert "Engine exploded" in exc_info.value.detail


class TestCaseVLLMModelStream:
    @pytest.mark.anyio
    async def test_stream_success(self):
        model, engine, mock_vllm = _make_model()

        outputs = []
        for text in ["Hello", " ", "world"]:
            o = MagicMock()
            o.outputs = [MagicMock(text=text)]
            outputs.append(o)

        engine.generate.return_value = _aiter_from(*outputs)

        tokens = []
        with (
            patch("flama.models.models.vllm.vllm", mock_vllm),
            patch("flama.models.models.vllm.RequestOutputKind", _FakeRequestOutputKind),
        ):
            async for token in model.stream("test prompt"):
                tokens.append(token)

        assert tokens == ["Hello", " ", "world"]

    @pytest.mark.anyio
    async def test_stream_skips_empty_tokens(self):
        model, engine, mock_vllm = _make_model()

        outputs = []
        for text in ["Hello", "", "world"]:
            o = MagicMock()
            o.outputs = [MagicMock(text=text)]
            outputs.append(o)

        engine.generate.return_value = _aiter_from(*outputs)

        tokens = []
        with (
            patch("flama.models.models.vllm.vllm", mock_vllm),
            patch("flama.models.models.vllm.RequestOutputKind", _FakeRequestOutputKind),
        ):
            async for token in model.stream("test prompt"):
                tokens.append(token)

        assert tokens == ["Hello", "world"]

    @pytest.mark.anyio
    async def test_stream_output_access_error_terminates(self):
        """When accessing output.outputs[0].text raises, the stream terminates cleanly."""
        model, engine, mock_vllm = _make_model()

        good_output = MagicMock()
        good_output.outputs = [MagicMock(text="Hello")]

        bad_output = MagicMock()
        bad_output.outputs.__getitem__ = MagicMock(side_effect=IndexError("no outputs"))

        trailing_output = MagicMock()
        trailing_output.outputs = [MagicMock(text="should not appear")]

        engine.generate.return_value = _aiter_from(good_output, bad_output, trailing_output)

        tokens = []
        with (
            patch("flama.models.models.vllm.vllm", mock_vllm),
            patch("flama.models.models.vllm.RequestOutputKind", _FakeRequestOutputKind),
        ):
            async for token in model.stream("test prompt"):
                tokens.append(token)

        assert tokens == ["Hello"]
