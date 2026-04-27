import datetime
import gc
import shutil
import typing as t
import uuid
from unittest.mock import MagicMock, patch

import pytest

from flama.serialize.data_structures import (
    CompressionFormat,
    FrameworkInfo,
    Metadata,
    ModelArtifact,
    ModelDirectory,
    ModelInfo,
)


class TestCaseCompressionFormat:
    @pytest.mark.parametrize(
        ["name", "value"],
        [
            pytest.param("bz2", 1, id="bz2"),
            pytest.param("lzma", 2, id="lzma"),
            pytest.param("zlib", 3, id="zlib"),
            pytest.param("zstd", 4, id="zstd"),
        ],
    )
    def test_values_are_stable(self, name: str, value: int) -> None:
        assert CompressionFormat[name].value == value


class TestCaseFrameworkInfo:
    @pytest.mark.parametrize(
        ["data"],
        [
            pytest.param({"lib": "sklearn", "version": "1.0.0", "config": None}, id="without_config"),
            pytest.param(
                {"lib": "transformers", "version": "4.50.0", "config": {"task": "text-generation"}}, id="with_config"
            ),
        ],
    )
    def test_from_dict(self, data: dict[str, t.Any]) -> None:
        fi = FrameworkInfo.from_dict(data)

        assert fi.lib == data["lib"]
        assert fi.version == data["version"]
        assert fi.config == data["config"]

    def test_to_dict(self) -> None:
        fi = FrameworkInfo(lib="sklearn", version="1.0.0", config={"task": "x"})

        assert fi.to_dict() == {"lib": "sklearn", "version": "1.0.0", "config": {"task": "x"}}

    @pytest.mark.parametrize(
        ["lib", "version", "config"],
        [
            pytest.param("torch", "2.0.0", None, id="without_config"),
            pytest.param("transformers", "4.50.0", {"task": "text-generation"}, id="with_config"),
        ],
    )
    def test_from_model(self, lib: str, version: str, config: dict[str, t.Any] | None) -> None:
        mock_ser = MagicMock()
        mock_ser.lib = lib
        mock_ser.version = MagicMock(return_value=version)

        with patch("flama.serialize.data_structures.ModelSerializer.from_model", return_value=mock_ser):
            fi = FrameworkInfo.from_model(object(), config=config)

        assert fi.lib == lib
        assert fi.version == version
        assert fi.config == config
        assert len(mock_ser.version.call_args_list) == 1


class TestCaseModelInfo:
    @pytest.mark.parametrize(
        ["data", "expected_params", "expected_metrics"],
        [
            pytest.param(
                {"obj": "MyModel", "info": {"type": "object"}, "params": {"a": 1}, "metrics": {"m": 2}},
                {"a": 1},
                {"m": 2},
                id="full",
            ),
            pytest.param({"obj": "X", "info": None}, None, None, id="optional_fields"),
        ],
    )
    def test_from_dict(
        self,
        data: dict[str, t.Any],
        expected_params: dict[str, t.Any] | None,
        expected_metrics: dict[str, t.Any] | None,
    ) -> None:
        mi = ModelInfo.from_dict(data)

        assert mi.obj == data["obj"]
        assert mi.info == data["info"]
        assert mi.params == expected_params
        assert mi.metrics == expected_metrics

    def test_to_dict(self) -> None:
        mi = ModelInfo(obj="X", info={"type": "object"}, params={"a": 1}, metrics={"m": 2})

        assert mi.to_dict() == {"obj": "X", "info": {"type": "object"}, "params": {"a": 1}, "metrics": {"m": 2}}

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
    @pytest.mark.parametrize(
        ["timestamp"],
        [
            pytest.param(datetime.datetime(2024, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc).isoformat(), id="string"),
            pytest.param(datetime.datetime(2024, 6, 1, 12, 0, 0), id="datetime"),
        ],
    )
    def test_from_dict(self, timestamp: str | datetime.datetime) -> None:
        id_ = uuid.uuid4()
        data: dict[str, t.Any] = {
            "id": str(id_),
            "timestamp": timestamp,
            "framework": {"lib": "sklearn", "version": "1.2.3"},
            "model": {"obj": "M", "info": None},
            "extra": {"k": "v"},
        }

        meta = Metadata.from_dict(data)

        assert meta.id == id_
        if isinstance(timestamp, str):
            assert meta.timestamp == datetime.datetime.fromisoformat(timestamp)
        else:
            assert meta.timestamp is timestamp
        assert meta.framework.lib == "sklearn"
        assert meta.model.obj == "M"
        assert meta.extra == {"k": "v"}

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
        assert d["framework"] == {"lib": "sklearn", "version": "1.0", "config": None}

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


class TestCaseModelDirectory:
    @pytest.mark.parametrize(
        ["delete", "expect_finalizer"],
        [
            pytest.param(True, True, id="delete_true"),
            pytest.param(False, False, id="delete_false"),
        ],
    )
    def test_init(self, delete: bool, expect_finalizer: bool) -> None:
        md = ModelDirectory(delete=delete)

        assert md.directory.exists()
        assert md.directory.is_dir()
        assert (md._finalizer is not None) is expect_finalizer

        if not delete:
            shutil.rmtree(md.directory)

    def test_str(self) -> None:
        md = ModelDirectory()

        assert str(md) == str(md.directory)

        md.cleanup()

    def test_repr(self) -> None:
        md = ModelDirectory()

        assert repr(md) == f"ModelDirectory(directory={md.directory!r})"

        md.cleanup()

    def test_exists(self) -> None:
        md = ModelDirectory()
        assert md.exists() is True

        md.cleanup()
        assert md.exists() is False

    def test_cleanup(self) -> None:
        md = ModelDirectory()

        md.cleanup()
        md.cleanup()

        assert not md.directory.exists()

    def test_finalizer_skipped_when_delete_false(self) -> None:
        md = ModelDirectory(delete=False)
        directory = md.directory

        del md
        gc.collect()

        assert directory.exists()

        shutil.rmtree(directory)


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
        assert ma.directory is None

    def test_directory_field(self) -> None:
        meta = Metadata(
            id=uuid.uuid4(),
            timestamp=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
            framework=FrameworkInfo(lib="sklearn", version="1.0"),
            model=ModelInfo(obj="X", info=None),
            extra=None,
        )
        a = ModelArtifact(meta=meta, model="m", artifacts=None, directory=None)
        b = ModelArtifact(meta=meta, model="m", artifacts=None, directory=ModelDirectory())

        try:
            assert a == b
            assert repr(a) == repr(b)
        finally:
            if b.directory is not None:
                b.directory.cleanup()
