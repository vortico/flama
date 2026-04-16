import pathlib
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from flama.huggingface.module import HuggingFaceModule


class TestCaseHuggingFaceModule:
    def test_name(self):
        assert HuggingFaceModule.name == "huggingface"

    @pytest.mark.parametrize(
        ["task", "model_name"],
        [
            pytest.param("text-generation", "my-org/my-model", id="with-task"),
            pytest.param(None, "my-org/my-model", id="auto-task"),
        ],
    )
    def test_get(self, task, model_name):
        mock_pipe = MagicMock()
        mock_pipe.task = task or "text-generation"

        def fake_save_pretrained(tmpdir):
            p = pathlib.Path(tmpdir)
            (p / "config.json").write_text('{"task": "text-generation"}')
            (p / "model.safetensors").write_bytes(b"\x00" * 16)

        mock_pipe.save_pretrained = fake_save_pretrained

        with (
            patch("flama.huggingface.module.transformers") as mock_transformers,
            patch("flama.huggingface.module.Serializer") as mock_serializer,
            tempfile.TemporaryDirectory() as output_dir,
        ):
            mock_transformers.pipeline.return_value = mock_pipe
            output_path = pathlib.Path(output_dir) / "test.flm"

            result = HuggingFaceModule.get(model_name, output_path, task=task)

            mock_transformers.pipeline.assert_called_once_with(task=task, model=model_name)
            mock_serializer.dump.assert_called_once()

            call_kwargs = mock_serializer.dump.call_args
            assert call_kwargs.kwargs["path"] == output_path
            assert "config.json" in call_kwargs.kwargs["artifacts"]
            assert "model.safetensors" in call_kwargs.kwargs["artifacts"]
            assert call_kwargs.kwargs["extra"]["task"] == mock_pipe.task
            assert call_kwargs.kwargs["extra"]["model_name"] == model_name
            assert result == output_path

    def test_get_nested_files(self):
        mock_pipe = MagicMock()
        mock_pipe.task = "text-generation"

        def fake_save_pretrained(tmpdir):
            p = pathlib.Path(tmpdir)
            (p / "config.json").write_text("{}")
            subdir = p / "tokenizer"
            subdir.mkdir()
            (subdir / "vocab.txt").write_text("hello")

        mock_pipe.save_pretrained = fake_save_pretrained

        with (
            patch("flama.huggingface.module.transformers") as mock_transformers,
            patch("flama.huggingface.module.Serializer") as mock_serializer,
            tempfile.TemporaryDirectory() as output_dir,
        ):
            mock_transformers.pipeline.return_value = mock_pipe
            output_path = pathlib.Path(output_dir) / "test.flm"

            HuggingFaceModule.get("org/model", output_path)

            artifacts = mock_serializer.dump.call_args.kwargs["artifacts"]
            assert "config.json" in artifacts
            assert "tokenizer/vocab.txt" in artifacts
