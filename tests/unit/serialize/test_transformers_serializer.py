import io
import pathlib
import tarfile
from unittest.mock import MagicMock, call, patch

import pytest

from flama.serialize.model_serializers.transformers import ModelSerializer


class TestCaseTransformersModelSerializer:
    @pytest.fixture(scope="function")
    def serializer(self):
        return ModelSerializer()

    def test_lib(self, serializer):
        assert serializer.lib == "transformers"

    def test_dump_path(self, serializer, tmp_path):
        model_dir = tmp_path / "model"
        model_dir.mkdir()
        (model_dir / "config.json").write_text("{}")
        (model_dir / ".hidden").write_text("skip")

        result = serializer.dump(model_dir)

        assert tarfile.is_tarfile(io.BytesIO(result))
        with tarfile.open(fileobj=io.BytesIO(result)) as tf:
            names = tf.getnames()
            assert any("config.json" in n for n in names)
            assert not any(".hidden" in n for n in names)

    def test_dump_path_string(self, serializer, tmp_path):
        model_dir = tmp_path / "model"
        model_dir.mkdir()
        (model_dir / "weights.bin").write_bytes(b"\x00")

        result = serializer.dump(str(model_dir))

        assert tarfile.is_tarfile(io.BytesIO(result))

    def test_dump_pipeline(self, serializer):
        pipeline = MagicMock(spec=["save_pretrained"])

        def _save(d):
            (pathlib.Path(d) / "config.json").write_text("{}")

        pipeline.save_pretrained.side_effect = _save

        with patch("flama.serialize.model_serializers.transformers.transformers"):
            result = serializer.dump(pipeline)

        assert tarfile.is_tarfile(io.BytesIO(result))
        with tarfile.open(fileobj=io.BytesIO(result)) as tf:
            names = tf.getnames()
            assert any("config.json" in n for n in names)

    def test_load_creates_pipeline(self, serializer):
        model_dir = pathlib.Path("/tmp/model")
        mock_pipeline = MagicMock()

        with patch("flama.serialize.model_serializers.transformers.transformers") as mock_tf:
            mock_tf.pipeline.return_value = mock_pipeline
            result = serializer.load(b"", model_dir=model_dir, task="text-generation")

        assert mock_tf.pipeline.call_args_list == [call(task="text-generation", model=str(model_dir))]
        assert result is mock_pipeline

    def test_load_no_task(self, serializer):
        model_dir = pathlib.Path("/tmp/model")

        with patch("flama.serialize.model_serializers.transformers.transformers") as mock_tf:
            serializer.load(b"", model_dir=model_dir)

        assert mock_tf.pipeline.call_args_list == [call(task=None, model=str(model_dir))]

    def test_load_no_model_dir_raises(self, serializer):
        with (
            patch("flama.serialize.model_serializers.transformers.transformers"),
            pytest.raises(ValueError, match="model directory"),
        ):
            serializer.load(b"")

    @pytest.mark.parametrize(
        ["has_config", "has_task", "has_name", "expected_keys"],
        [
            pytest.param(True, True, True, {"config", "task", "model_name"}, id="full"),
            pytest.param(True, False, False, {"config"}, id="config-only"),
            pytest.param(False, True, False, {"task"}, id="task-only"),
            pytest.param(False, False, False, None, id="empty"),
        ],
    )
    def test_info(self, serializer, has_config, has_task, has_name, expected_keys):
        pipeline = MagicMock(spec=[])
        if has_task:
            pipeline.task = "text-generation"
        if has_config or has_name:
            pipeline.model = MagicMock(spec=[])
        if has_config:
            pipeline.model.config = MagicMock()
            pipeline.model.config.to_dict.return_value = {"hidden_size": 768}
        if has_name:
            pipeline.model.name_or_path = "google/gemma-2-2b"

        result = serializer.info(pipeline)

        if expected_keys is None:
            assert result is None
        else:
            assert set(result.keys()) == expected_keys

    def test_info_exception_returns_none(self, serializer):
        pipeline = MagicMock()
        pipeline.model.config.to_dict.side_effect = RuntimeError("boom")

        result = serializer.info(pipeline)
        assert result is None

    def test_version(self, serializer):
        with patch("flama.serialize.model_serializers.transformers.importlib.metadata.version", return_value="4.50.0"):
            assert serializer.version() == "4.50.0"

    def test_version_not_installed(self, serializer):
        with patch(
            "flama.serialize.model_serializers.transformers.importlib.metadata.version",
            side_effect=Exception("not found"),
        ):
            with pytest.raises(Exception):
                serializer.version()
