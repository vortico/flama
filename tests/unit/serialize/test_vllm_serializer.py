import io
import pathlib
import tarfile
from unittest.mock import MagicMock, call, patch

import pytest

from flama.serialize.model_serializers.vllm import ModelSerializer


class TestCaseVLLMModelSerializer:
    @pytest.fixture(scope="function")
    def serializer(self):
        return ModelSerializer()

    def test_lib(self, serializer):
        assert serializer.lib == "vllm"

    def test_dump_path(self, serializer, tmp_path):
        model_dir = tmp_path / "model"
        model_dir.mkdir()
        (model_dir / "config.json").write_text('{"model_type": "mock"}')

        result = serializer.dump(model_dir)

        assert tarfile.is_tarfile(io.BytesIO(result))
        with tarfile.open(fileobj=io.BytesIO(result)) as tf:
            names = tf.getnames()
            assert any("config.json" in n for n in names)

    def test_dump_non_path_raises(self, serializer):
        with pytest.raises(NotImplementedError, match="cannot be serialized"):
            serializer.dump(42)

    def test_load_creates_engine(self, serializer):
        model_dir = pathlib.Path("/tmp/model")
        mock_engine = MagicMock()

        with (
            patch("flama.serialize.model_serializers.vllm.vllm") as mock_vllm,
            patch("flama.serialize.model_serializers.vllm.AsyncEngineArgs") as mock_args_cls,
        ):
            mock_vllm.AsyncLLMEngine.from_engine_args.return_value = mock_engine
            result = serializer.load(b"", model_dir=model_dir, engine_params={"max_model_len": 4096})

        assert mock_args_cls.call_args_list == [call(model=str(model_dir), disable_log_stats=True, max_model_len=4096)]
        assert mock_vllm.AsyncLLMEngine.from_engine_args.call_args_list == [call(mock_args_cls.return_value)]
        assert result is mock_engine

    def test_load_no_engine_params(self, serializer):
        model_dir = pathlib.Path("/tmp/model")

        with (
            patch("flama.serialize.model_serializers.vllm.vllm"),
            patch("flama.serialize.model_serializers.vllm.AsyncEngineArgs") as mock_args_cls,
        ):
            serializer.load(b"", model_dir=model_dir)

        assert mock_args_cls.call_args_list == [call(model=str(model_dir), disable_log_stats=True)]

    def test_load_no_model_dir_raises(self, serializer):
        with (
            patch("flama.serialize.model_serializers.vllm.vllm"),
            patch("flama.serialize.model_serializers.vllm.AsyncEngineArgs"),
            pytest.raises(ValueError, match="model directory"),
        ):
            serializer.load(b"")

    @pytest.mark.parametrize(
        ["model_attr", "expected"],
        [
            pytest.param("google/gemma-2-2b", {"model_name": "google/gemma-2-2b"}, id="with-model"),
            pytest.param(None, None, id="no-model-attr"),
        ],
    )
    def test_info(self, serializer, model_attr, expected):
        if model_attr is not None:
            obj = MagicMock()
            obj.model = model_attr
        else:
            obj = MagicMock(spec=[])

        result = serializer.info(obj)
        assert result == expected

    def test_info_exception_returns_none(self, serializer):
        model = MagicMock()
        type(model).model = property(lambda self: (_ for _ in ()).throw(RuntimeError("boom")))

        result = serializer.info(model)
        assert result is None

    def test_version(self, serializer):
        with patch("flama.serialize.model_serializers.vllm.importlib.metadata.version", return_value="0.8.0"):
            assert serializer.version() == "0.8.0"

    def test_version_not_installed(self, serializer):
        with patch(
            "flama.serialize.model_serializers.vllm.importlib.metadata.version",
            side_effect=Exception("not found"),
        ):
            with pytest.raises(Exception):
                serializer.version()
