import datetime
import gc
import pathlib
import shutil
import typing as t
import uuid
from unittest.mock import MagicMock, patch

import pytest

from flama.serialize.data_structures import (
    CompressionFormat,
    FrameworkInfo,
    LLMModelCapabilities,
    Metadata,
    MLModelCapabilities,
    ModelArtifact,
    ModelCapabilities,
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
            pytest.param({"family": "ml", "lib": "sklearn", "version": "1.0.0", "config": None}, id="without_config"),
            pytest.param(
                {"family": "ml", "lib": "transformers", "version": "4.50.0", "config": {"task": "text-generation"}},
                id="with_config",
            ),
            pytest.param(
                {"family": "llm", "lib": "transformers", "version": "4.50.0"},
                id="llm_without_optional_config",
            ),
        ],
    )
    def test_from_dict(self, data: dict[str, t.Any]) -> None:
        fi = FrameworkInfo.from_dict(data)

        assert fi.family == data["family"]
        assert fi.lib == data["lib"]
        assert fi.version == data["version"]
        assert fi.config == data.get("config")

    def test_from_dict_missing_family_defaults_to_ml(self) -> None:
        """Master-era manifests (without ``family``) decode as ``family == "ml"`` for v1 backward compat."""
        fi = FrameworkInfo.from_dict({"lib": "sklearn", "version": "1.0.0"})

        assert fi.family == "ml"
        assert fi.lib == "sklearn"
        assert fi.version == "1.0.0"

    def test_to_dict(self) -> None:
        fi = FrameworkInfo(family="ml", lib="sklearn", version="1.0.0", config={"task": "x"})

        assert fi.to_dict() == {"family": "ml", "lib": "sklearn", "version": "1.0.0", "config": {"task": "x"}}

    def test_round_trip(self) -> None:
        original = FrameworkInfo(family="llm", lib="transformers", version="4.50.0", config={"task": "gen"})

        assert FrameworkInfo.from_dict(original.to_dict()) == original

    @pytest.mark.parametrize(
        ["family", "lib", "version", "config"],
        [
            pytest.param("ml", "torch", "2.0.0", None, id="ml_without_config"),
            pytest.param("llm", "transformers", "4.50.0", {"task": "text-generation"}, id="llm_with_config"),
        ],
    )
    def test_from_model(self, family: str, lib: str, version: str, config: dict[str, t.Any] | None) -> None:
        mock_ser = MagicMock()
        mock_ser.lib = lib
        mock_ser.version = MagicMock(return_value=version)

        with patch("flama.serialize.data_structures.ModelSerializer.from_model", return_value=mock_ser):
            fi = FrameworkInfo.from_model(object(), family=t.cast(t.Any, family), config=config)

        assert fi.family == family
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


class TestCaseLLMModelCapabilities:
    def test_default(self) -> None:
        cap = LLMModelCapabilities()

        assert cap.kind == "llm"
        assert cap.text is True
        assert cap.image is False
        assert cap.audio is False
        assert cap.video is False
        assert cap.tools is False
        assert cap.reasoning is False

    def test_frozen(self) -> None:
        cap = LLMModelCapabilities()

        with pytest.raises(AttributeError):
            cap.image = True  # type: ignore[misc]

    @pytest.mark.parametrize(
        ["kwargs", "expected"],
        [
            pytest.param({}, False, id="text_only"),
            pytest.param({"image": True}, True, id="image"),
            pytest.param({"audio": True}, True, id="audio"),
            pytest.param({"video": True}, True, id="video"),
            pytest.param({"image": True, "audio": True}, True, id="image_audio"),
            pytest.param({"tools": True}, False, id="tools_only"),
            pytest.param({"reasoning": True}, False, id="reasoning_only"),
        ],
    )
    def test_is_multimodal(self, kwargs: dict, expected: bool) -> None:
        assert LLMModelCapabilities(**kwargs).is_multimodal is expected

    @pytest.mark.parametrize(
        ["kwargs", "expected"],
        [
            pytest.param({}, ("text",), id="text_only"),
            pytest.param({"image": True}, ("text", "image"), id="text_image"),
            pytest.param({"audio": True}, ("text", "audio"), id="text_audio"),
            pytest.param({"video": True}, ("text", "video"), id="text_video"),
            pytest.param(
                {"image": True, "audio": True, "video": True},
                ("text", "image", "audio", "video"),
                id="all_modalities",
            ),
            pytest.param({"text": False, "image": True}, ("image",), id="image_only"),
        ],
    )
    def test_modalities(self, kwargs: dict, expected: tuple[str, ...]) -> None:
        assert LLMModelCapabilities(**kwargs).modalities == expected

    def test_to_dict(self) -> None:
        cap = LLMModelCapabilities(image=True, audio=True, tools=True)

        assert cap.to_dict() == {
            "kind": "llm",
            "text": True,
            "image": True,
            "audio": True,
            "video": False,
            "tools": True,
            "reasoning": False,
        }

    def test_round_trip(self) -> None:
        original = LLMModelCapabilities(image=True, audio=True, tools=True, reasoning=True)

        round_trip = ModelCapabilities.from_dict(original.to_dict())

        assert round_trip == original
        assert isinstance(round_trip, LLMModelCapabilities)


class TestCaseMLModelCapabilities:
    def test_default(self) -> None:
        cap = MLModelCapabilities()

        assert cap.kind == "ml"

    def test_frozen(self) -> None:
        cap = MLModelCapabilities()

        with pytest.raises(AttributeError):
            cap.kind = "llm"  # type: ignore[misc]

    def test_to_dict(self) -> None:
        assert MLModelCapabilities().to_dict() == {"kind": "ml"}

    def test_round_trip(self) -> None:
        original = MLModelCapabilities()

        round_trip = ModelCapabilities.from_dict(original.to_dict())

        assert round_trip == original
        assert isinstance(round_trip, MLModelCapabilities)


class TestCaseModelCapabilitiesFromDict:
    @pytest.mark.parametrize(
        ["data", "expected_cls", "expected"],
        [
            pytest.param(
                {"kind": "llm"},
                LLMModelCapabilities,
                LLMModelCapabilities(),
                id="llm_minimal",
            ),
            pytest.param(
                {"kind": "llm", "text": True, "image": True},
                LLMModelCapabilities,
                LLMModelCapabilities(text=True, image=True),
                id="llm_partial",
            ),
            pytest.param(
                {"kind": "llm", "image": True, "unknown_future_key": True},
                LLMModelCapabilities,
                LLMModelCapabilities(image=True),
                id="llm_unknown_keys_ignored",
            ),
            pytest.param(
                {"kind": "llm", "image": 1, "audio": 0},
                LLMModelCapabilities,
                LLMModelCapabilities(image=True, audio=False),
                id="llm_truthy_values_coerced",
            ),
            pytest.param({"kind": "ml"}, MLModelCapabilities, MLModelCapabilities(), id="ml_minimal"),
        ],
    )
    def test_from_dict(self, data: dict, expected_cls: type, expected: ModelCapabilities) -> None:
        result = ModelCapabilities.from_dict(data)

        assert isinstance(result, expected_cls)
        assert result == expected

    def test_missing_kind_raises(self) -> None:
        with pytest.raises(KeyError):
            ModelCapabilities.from_dict({"text": True, "image": True})

    def test_unknown_kind_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown ModelCapabilities kind"):
            ModelCapabilities.from_dict({"kind": "unknown"})


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
            "framework": {"family": "ml", "lib": "sklearn", "version": "1.2.3"},
            "model": {"obj": "M", "info": None},
            "extra": {"k": "v"},
        }

        meta = Metadata.from_dict(data)

        assert meta.id == id_
        if isinstance(timestamp, str):
            assert meta.timestamp == datetime.datetime.fromisoformat(timestamp)
        else:
            assert meta.timestamp is timestamp
        assert meta.framework.family == "ml"
        assert meta.framework.lib == "sklearn"
        assert meta.model.obj == "M"
        assert meta.extra == {"k": "v"}
        assert meta.capabilities is None

    @pytest.mark.parametrize(
        ["payload", "expected"],
        [
            pytest.param(None, None, id="missing_key"),
            pytest.param(
                {"kind": "llm", "text": True, "image": True, "audio": False},
                LLMModelCapabilities(text=True, image=True, audio=False),
                id="image_only",
            ),
        ],
    )
    def test_from_dict_capabilities(self, payload: dict[str, t.Any] | None, expected: ModelCapabilities | None) -> None:
        data: dict[str, t.Any] = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.datetime(2024, 1, 1).isoformat(),
            "framework": {"family": "llm", "lib": "transformers", "version": "4.50.0"},
            "model": {"obj": "M", "info": None},
            "extra": None,
        }
        if payload is not None:
            data["capabilities"] = payload

        meta = Metadata.from_dict(data)

        assert meta.capabilities == expected

    def test_to_dict(self) -> None:
        id_ = uuid.uuid4()
        ts = datetime.datetime(2024, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
        meta = Metadata(
            id=id_,
            timestamp=ts,
            framework=FrameworkInfo(family="ml", lib="sklearn", version="1.0"),
            model=ModelInfo(obj="X", info=None),
            extra=None,
        )

        d = meta.to_dict()

        assert d["id"] == str(id_)
        assert d["timestamp"] == ts.isoformat()
        assert d["framework"] == {"family": "ml", "lib": "sklearn", "version": "1.0", "config": None}
        assert "capabilities" not in d

    def test_to_dict_with_capabilities(self) -> None:
        cap = LLMModelCapabilities(image=True, audio=True)
        meta = Metadata(
            id=uuid.uuid4(),
            timestamp=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
            framework=FrameworkInfo(family="llm", lib="transformers", version="4.50.0"),
            model=ModelInfo(obj="X", info=None),
            capabilities=cap,
            extra=None,
        )

        d = meta.to_dict()

        assert d["capabilities"] == cap.to_dict()

    def test_from_model(self) -> None:
        model = object()
        model_id = uuid.uuid4()
        ts = datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc)
        mock_ser = MagicMock()
        mock_ser.lib = "sklearn"
        mock_ser.version.return_value = "1.2.3"
        mock_ser.info.return_value = {"s": 1}
        mock_ser.detect_capabilities.return_value = None

        with patch("flama.serialize.data_structures.ModelSerializer.from_model", return_value=mock_ser):
            meta = Metadata.from_model(
                model,
                family="ml",
                model_id=model_id,
                timestamp=ts,
                params={"a": 1},
                metrics={"b": 2},
                extra={"x": 1},
            )

        assert meta.id is model_id
        assert meta.timestamp is ts
        assert meta.framework.family == "ml"
        assert meta.framework.lib == "sklearn"
        assert meta.capabilities is None

    def test_from_model_auto_detects_capabilities(self) -> None:
        model = object()
        cap = LLMModelCapabilities(image=True)
        mock_ser = MagicMock()
        mock_ser.lib = "transformers"
        mock_ser.version.return_value = "4.50.0"
        mock_ser.info.return_value = None
        mock_ser.detect_capabilities.return_value = cap

        with patch("flama.serialize.data_structures.ModelSerializer.from_model", return_value=mock_ser):
            meta = Metadata.from_model(
                model, family="llm", model_id=None, timestamp=None, params=None, metrics=None, extra=None
            )

        assert meta.capabilities == cap

    def test_from_model_user_override_wins(self) -> None:
        model = object()
        detected = LLMModelCapabilities(image=True)
        override = LLMModelCapabilities(audio=True)
        mock_ser = MagicMock()
        mock_ser.lib = "transformers"
        mock_ser.version.return_value = "4.50.0"
        mock_ser.info.return_value = None
        mock_ser.detect_capabilities.return_value = detected

        with patch("flama.serialize.data_structures.ModelSerializer.from_model", return_value=mock_ser):
            meta = Metadata.from_model(
                model,
                family="llm",
                model_id=None,
                timestamp=None,
                params=None,
                metrics=None,
                extra=None,
                capabilities=override,
            )

        assert meta.capabilities == override
        assert mock_ser.detect_capabilities.call_count == 0


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
    def test_from_model_in_memory_preseeds_cache(self) -> None:
        model = object()
        mock_ser = MagicMock()
        mock_ser.lib = "sklearn"
        mock_ser.version.return_value = "1.0"
        mock_ser.info.return_value = None

        with patch("flama.serialize.data_structures.ModelSerializer.from_model", return_value=mock_ser):
            ma = ModelArtifact.from_model(model, family="ml", model_id="mid", artifacts={"f": "/tmp/x"})

        assert ma.source is None
        assert ma.__dict__["model"] is model
        assert ma.model is model
        assert ma.meta.id == "mid"
        assert ma.meta.framework.family == "ml"
        assert ma.artifacts == {"f": "/tmp/x"}
        assert ma.directory is None

    def test_from_model_path_input_stores_source(self, tmp_path: pathlib.Path) -> None:
        mock_ser = MagicMock()
        mock_ser.lib = "transformers"
        mock_ser.version.return_value = "4.50"
        mock_ser.info.return_value = None

        with patch("flama.serialize.data_structures.ModelSerializer.from_model", return_value=mock_ser):
            ma = ModelArtifact.from_model(tmp_path, family="ml", model_id="mid")

        assert ma.source == tmp_path
        assert "model" not in ma.__dict__

    def test_model_property_raises_when_unbound(self) -> None:
        meta = Metadata(
            id=uuid.uuid4(),
            timestamp=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
            framework=FrameworkInfo(family="ml", lib="sklearn", version="1.0"),
            model=ModelInfo(obj="X", info=None),
            extra=None,
        )
        ma = ModelArtifact(meta=meta)

        with pytest.raises(Exception, match="Artifact has no source bound"):
            _ = ma.model

    def test_model_property_llm_returns_source_verbatim(self, tmp_path: pathlib.Path) -> None:
        meta = Metadata(
            id=uuid.uuid4(),
            timestamp=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
            framework=FrameworkInfo(family="llm", lib="transformers", version="4.50"),
            model=ModelInfo(obj="X", info=None),
            extra=None,
        )
        ma = ModelArtifact(meta=meta, source=tmp_path)

        with patch("flama.serialize.data_structures.ModelSerializer.from_lib") as from_lib:
            assert ma.model is tmp_path
            assert from_lib.call_count == 0

    def test_model_property_ml_materialises_once(self) -> None:
        meta = Metadata(
            id=uuid.uuid4(),
            timestamp=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
            framework=FrameworkInfo(family="ml", lib="sklearn", version="1.0", config={"task": "tg"}),
            model=ModelInfo(obj="X", info=None),
            extra=None,
        )
        ma = ModelArtifact(meta=meta, source=b"raw-bytes")

        ser = MagicMock()
        ser.load.return_value = object()

        with patch("flama.serialize.data_structures.ModelSerializer.from_lib", return_value=ser) as from_lib:
            first = ma.model
            second = ma.model

        assert first is second
        assert ser.load.call_count == 1
        args, kwargs = ser.load.call_args
        assert args == (b"raw-bytes",)
        assert kwargs == {"capabilities": ma.meta.capabilities, "task": "tg"}
        assert from_lib.call_count == 1

    def test_directory_field(self) -> None:
        meta = Metadata(
            id=uuid.uuid4(),
            timestamp=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
            framework=FrameworkInfo(family="ml", lib="sklearn", version="1.0"),
            model=ModelInfo(obj="X", info=None),
            extra=None,
        )
        a = ModelArtifact(meta=meta, artifacts=None, directory=None)
        b = ModelArtifact(meta=meta, artifacts=None, directory=ModelDirectory())

        try:
            assert a == b
            assert repr(a) == repr(b)
        finally:
            if b.directory is not None:
                b.directory.cleanup()
