import pathlib
import tempfile
from unittest.mock import MagicMock, patch

import pytest


class TestCaseTransformersModel:
    @pytest.fixture
    def artifacts_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = pathlib.Path(tmpdir) / "artifacts"
            p.mkdir()
            (p / "config.json").write_text('{"task": "text-generation"}')
            (p / "model.safetensors").write_bytes(b"\x00" * 16)
            yield {
                "config.json": p / "config.json",
                "model.safetensors": p / "model.safetensors",
            }

    @pytest.fixture
    def meta(self):
        meta = MagicMock()
        meta.framework.lib = "transformers"
        meta.framework.version = "4.50.0"
        return meta

    @pytest.fixture
    def mock_pipeline(self):
        pipeline = MagicMock()
        pipeline.return_value = [{"generated_text": "Hello world"}]
        pipeline.task = "text-generation"
        pipeline.model = MagicMock()
        pipeline.model.device = "cpu"
        pipeline.tokenizer = MagicMock()
        return pipeline

    def test_init(self, meta, artifacts_dir, mock_pipeline):
        with patch("flama.models.models.transformers.tf_hub") as mock_tf_hub:
            mock_tf_hub.pipeline.return_value = mock_pipeline
            from flama.models.models.transformers import Model

            model = Model({"task": "text-generation"}, meta, artifacts_dir)

        assert model.pipeline is mock_pipeline

    def test_init_no_artifacts_raises(self, meta):
        with patch("flama.models.models.transformers.tf_hub") as mock_tf_hub:
            mock_tf_hub.pipeline.return_value = MagicMock()
            from flama.models.models.transformers import Model

            with pytest.raises(ValueError, match="requires artifacts"):
                Model({"task": "text-generation"}, meta, None)

    def test_predict(self, meta, artifacts_dir, mock_pipeline):
        with patch("flama.models.models.transformers.tf_hub") as mock_tf_hub:
            mock_tf_hub.pipeline.return_value = mock_pipeline
            from flama.models.models.transformers import Model

            model = Model({"task": "text-generation"}, meta, artifacts_dir)
            result = model.predict(["Hello"])

        mock_pipeline.assert_called_once_with(["Hello"])
        assert result == [{"generated_text": "Hello world"}]

    def test_predict_error(self, meta, artifacts_dir, mock_pipeline):
        mock_pipeline.side_effect = ValueError("bad input")

        with patch("flama.models.models.transformers.tf_hub") as mock_tf_hub:
            mock_tf_hub.pipeline.return_value = mock_pipeline
            from flama.models.models.transformers import Model

            model = Model({"task": "text-generation"}, meta, artifacts_dir)

            from flama.exceptions import HTTPException

            with pytest.raises(HTTPException):
                model.predict(["bad"])

    @pytest.mark.parametrize(
        ["has_generate", "inputs", "expected"],
        [
            pytest.param(True, ["Hello"], ["Hello", " world"], id="generate-streaming"),
            pytest.param(False, ["Hello"], [[{"generated_text": "Hello world"}]], id="fallback-pipeline"),
        ],
    )
    async def test_stream(self, meta, artifacts_dir, mock_pipeline, has_generate, inputs, expected):
        if not has_generate:
            del mock_pipeline.model.generate

        with patch("flama.models.models.transformers.tf_hub") as mock_tf_hub:
            mock_tf_hub.pipeline.return_value = mock_pipeline
            mock_tf_hub.TextIteratorStreamer = MagicMock() if has_generate else None

            from flama.models.models.transformers import Model

            model = Model({"task": "text-generation"}, meta, artifacts_dir)

            if has_generate:
                model._generate_tokens = MagicMock(return_value=["Hello", " world"])

            async def _input():
                for item in inputs:
                    yield item

            results = [token async for token in model.stream(_input())]

        assert results == expected

    async def test_stream_empty_input(self, meta, artifacts_dir, mock_pipeline):
        with patch("flama.models.models.transformers.tf_hub") as mock_tf_hub:
            mock_tf_hub.pipeline.return_value = mock_pipeline
            from flama.models.models.transformers import Model

            model = Model({"task": "text-generation"}, meta, artifacts_dir)

            async def _empty():
                return
                yield

            results = [token async for token in model.stream(_empty())]

        assert results == []

    async def test_stream_error_stops(self, meta, artifacts_dir, mock_pipeline):
        mock_pipeline.side_effect = RuntimeError("boom")
        del mock_pipeline.model.generate

        with patch("flama.models.models.transformers.tf_hub") as mock_tf_hub:
            mock_tf_hub.pipeline.return_value = mock_pipeline
            from flama.models.models.transformers import Model

            model = Model({"task": "text-generation"}, meta, artifacts_dir)

            async def _input():
                yield "Hello"
                yield "World"

            results = [token async for token in model.stream(_input())]

        assert results == []
