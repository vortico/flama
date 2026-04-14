import datetime
import typing as t
import uuid
from unittest.mock import MagicMock, patch

import pytest

from flama.serialize.data_structures import FrameworkInfo, Metadata, ModelArtifact, ModelInfo


class TestCaseFrameworkInfo:
    def test_from_dict_and_to_dict(self) -> None:
        data: dict[str, t.Any] = {"lib": "sklearn", "version": "1.0.0"}
        fi = FrameworkInfo.from_dict(data)

        assert fi.lib == "sklearn"
        assert fi.version == "1.0.0"
        assert fi.to_dict() == data

    def test_from_model(self) -> None:
        mock_ser = MagicMock()
        mock_ser.lib = "torch"
        mock_ser.version = MagicMock(return_value="2.0.0")

        with patch("flama.serialize.data_structures.ModelSerializer.from_model", return_value=mock_ser):
            fi = FrameworkInfo.from_model(object())

        assert fi.lib == "torch"
        assert fi.version == "2.0.0"
        mock_ser.version.assert_called_once()


class TestCaseModelInfo:
    def test_from_dict_and_to_dict(self) -> None:
        data: dict[str, t.Any] = {
            "obj": "MyModel",
            "info": {"type": "object"},
            "params": {"a": 1},
            "metrics": {"m": 2},
        }
        mi = ModelInfo.from_dict(data)

        assert mi.obj == "MyModel"
        assert mi.info == {"type": "object"}
        assert mi.params == {"a": 1}
        assert mi.metrics == {"m": 2}
        assert mi.to_dict() == data

    def test_from_dict_optional_fields(self) -> None:
        mi = ModelInfo.from_dict({"obj": "X", "info": None})

        assert mi.params is None
        assert mi.metrics is None

    @pytest.mark.parametrize(
        ["model", "expected_obj"],
        [
            pytest.param(type("Foo", (), {}), "Foo", id="class_model"),
            pytest.param(type("Bar", (), {})(), "Bar", id="instance_model"),
        ],
    )
    def test_from_model(self, model: t.Any, expected_obj: str) -> None:
        mock_ser = MagicMock()
        mock_ser.info = MagicMock(return_value={"title": "schema"})

        with patch("flama.serialize.data_structures.ModelSerializer.from_model", return_value=mock_ser):
            mi = ModelInfo.from_model(model, params={"p": 1}, metrics={"m": 2})

        assert mi.obj == expected_obj
        assert mi.info == {"title": "schema"}
        assert mi.params == {"p": 1}
        assert mi.metrics == {"m": 2}


class TestCaseMetadata:
    def test_from_dict_with_string_timestamp(self) -> None:
        id_ = uuid.uuid4()
        ts = datetime.datetime(2024, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc)
        data: dict[str, t.Any] = {
            "id": str(id_),
            "timestamp": ts.isoformat(),
            "framework": {"lib": "sklearn", "version": "1.2.3"},
            "model": {"obj": "M", "info": None},
            "extra": {"k": "v"},
        }
        meta = Metadata.from_dict(data)

        assert meta.id == id_
        assert meta.timestamp == ts
        assert meta.framework.lib == "sklearn"
        assert meta.model.obj == "M"
        assert meta.extra == {"k": "v"}

    def test_from_dict_with_datetime_timestamp(self) -> None:
        ts = datetime.datetime(2024, 6, 1, 12, 0, 0)
        data: dict[str, t.Any] = {
            "id": str(uuid.uuid4()),
            "timestamp": ts,
            "framework": {"lib": "tensorflow", "version": "2.0"},
            "model": {"obj": "M", "info": None},
        }
        meta = Metadata.from_dict(data)

        assert meta.timestamp is ts

    def test_to_dict(self) -> None:
        id_ = uuid.uuid4()
        ts = datetime.datetime(2024, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
        meta = Metadata(
            id=id_,
            timestamp=ts,
            framework=FrameworkInfo(lib="sklearn", version="1.0"),
            model=ModelInfo(obj="X", info=None),
            extra=None,
        )
        d = meta.to_dict()

        assert d["id"] == str(id_)
        assert d["timestamp"] == ts.isoformat()
        assert d["framework"] == {"lib": "sklearn", "version": "1.0"}

    def test_from_model(self) -> None:
        model = object()
        model_id = uuid.uuid4()
        ts = datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc)
        mock_ser = MagicMock()
        mock_ser.lib = "sklearn"
        mock_ser.version.return_value = "1.2.3"
        mock_ser.info.return_value = {"s": 1}

        with patch("flama.serialize.data_structures.ModelSerializer.from_model", return_value=mock_ser):
            meta = Metadata.from_model(
                model, model_id=model_id, timestamp=ts, params={"a": 1}, metrics={"b": 2}, extra={"x": 1}
            )

        assert meta.id is model_id
        assert meta.timestamp is ts
        assert meta.framework.lib == "sklearn"


class TestCaseModelArtifact:
    def test_from_model(self) -> None:
        model = object()
        mock_ser = MagicMock()
        mock_ser.lib = "sklearn"
        mock_ser.version.return_value = "1.0"
        mock_ser.info.return_value = None

        with patch("flama.serialize.data_structures.ModelSerializer.from_model", return_value=mock_ser):
            ma = ModelArtifact.from_model(model, model_id="mid", artifacts={"f": "/tmp/x"})

        assert ma.model is model
        assert ma.meta.id == "mid"
        assert ma.artifacts == {"f": "/tmp/x"}
