import pathlib
import tempfile
from unittest.mock import MagicMock, call, patch

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
        with tempfile.TemporaryDirectory() as snapshot_dir:
            mock_model_info = MagicMock()
            mock_model_info.pipeline_tag = "text-generation"

            with (
                patch("flama.huggingface.module.huggingface_hub") as mock_hub,
                patch("flama.huggingface.module.Serializer") as mock_serializer,
                tempfile.TemporaryDirectory() as output_dir,
            ):
                mock_hub.snapshot_download.return_value = snapshot_dir
                mock_hub.hf_model_info.return_value = mock_model_info
                output_path = pathlib.Path(output_dir) / "test.flm"

                result = HuggingFaceModule.get(model_name, output_path, task=task)

                assert mock_hub.snapshot_download.call_args_list == [call(repo_id=model_name)]
                if task is None:
                    assert mock_hub.hf_model_info.call_args_list == [call(model_name)]
                else:
                    assert mock_hub.hf_model_info.call_args_list == []

                assert len(mock_serializer.dump.call_args_list) == 1
                call_kwargs = mock_serializer.dump.call_args
                assert call_kwargs.args[0] == snapshot_dir
                assert call_kwargs.kwargs["path"] == output_path
                assert call_kwargs.kwargs["config"] == {"task": "text-generation"}
                assert call_kwargs.kwargs["extra"] == {"model_name": model_name}
                assert call_kwargs.kwargs["lib"] == "transformers"
                assert result == output_path

    def test_get_with_engine_vllm(self):
        with tempfile.TemporaryDirectory() as snapshot_dir:
            with (
                patch("flama.huggingface.module.huggingface_hub") as mock_hub,
                patch("flama.huggingface.module.Serializer") as mock_serializer,
                tempfile.TemporaryDirectory() as output_dir,
            ):
                mock_hub.snapshot_download.return_value = snapshot_dir
                mock_hub.hf_model_info.return_value = MagicMock(pipeline_tag="text-generation")
                output_path = pathlib.Path(output_dir) / "test.flm"

                HuggingFaceModule.get("org/model", output_path, engine="vllm")

                call_kwargs = mock_serializer.dump.call_args
                assert call_kwargs.kwargs["lib"] == "vllm"
