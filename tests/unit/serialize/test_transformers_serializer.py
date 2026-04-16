import json
from unittest.mock import MagicMock, patch

import pytest

from flama.serialize.model_serializers.transformers import ModelSerializer


class TestCaseTransformersModelSerializer:
    @pytest.fixture
    def serializer(self):
        return ModelSerializer()

    def test_lib(self, serializer):
        assert serializer.lib == "transformers"

    def test_dump(self, serializer):
        pipeline = MagicMock()
        pipeline.task = "text-generation"

        result = serializer.dump(pipeline)

        descriptor = json.loads(result)
        assert descriptor == {"task": "text-generation"}

    def test_dump_no_task(self, serializer):
        pipeline = MagicMock(spec=[])

        result = serializer.dump(pipeline)

        descriptor = json.loads(result)
        assert descriptor == {"task": None}

    def test_load(self, serializer):
        data = json.dumps({"task": "text-generation"}).encode()

        result = serializer.load(data)

        assert result == {"task": "text-generation"}

    def test_dump_load_roundtrip(self, serializer):
        pipeline = MagicMock()
        pipeline.task = "text-generation"

        dumped = serializer.dump(pipeline)
        loaded = serializer.load(dumped)

        assert loaded == {"task": "text-generation"}

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
