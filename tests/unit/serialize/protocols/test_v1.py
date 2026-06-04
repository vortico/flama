import datetime
import io
import pathlib
import struct
import uuid
from unittest.mock import patch

import pytest

from flama._core.compression import compress
from flama._core.json_encoder import encode_json
from flama.serialize import data_structures
from flama.serialize.data_structures import FrameworkInfo, Metadata, ModelArtifact, ModelDirectory, ModelInfo
from flama.serialize.exceptions import UnsupportedProtocol
from flama.serialize.protocols import v1


class TestCaseV1Artifact:
    def test_pack_unpack_roundtrip(self, compression_format: str, tmp_path: pathlib.Path) -> None:
        content = b"artifact-bytes" * 8
        src = tmp_path / "sidecar.json"
        src.write_bytes(content)

        packed = v1._Artifact.pack("sidecar.json", src, compression=compression_format)
        name_size, content_size = struct.unpack(v1._Artifact._header_format, packed[: v1._Artifact._header_size])
        assert name_size == len("sidecar.json")
        assert len(packed) == v1._Artifact._header_size + name_size + content_size

        out_dir = tmp_path / "out"
        out_dir.mkdir()
        path, size = v1._Artifact.unpack(packed, compression=compression_format, directory=out_dir)

        assert path.read_bytes() == content
        assert size == len(packed)


class TestCaseV1Body:
    @pytest.mark.parametrize("with_artifacts", [False, True], indirect=True)
    def test_pack(
        self,
        compression_format: str,
        model_artifact: ModelArtifact,
        serializer_mock,
    ) -> None:
        buf = io.BytesIO()

        with patch.object(v1, "ModelSerializer") as MS:
            MS.from_lib.return_value = serializer_mock
            written = v1._Body.pack(model_artifact, buf, compression=compression_format)

        assert written == buf.tell()
        assert written > v1._Body._header_size

    @pytest.mark.parametrize("with_artifacts", [False, True], indirect=True)
    def test_unpack(
        self,
        compression_format: str,
        model_artifact: ModelArtifact,
        serializer_mock,
    ) -> None:
        buf = io.BytesIO()
        with patch.object(v1, "ModelSerializer") as MS:
            MS.from_lib.return_value = serializer_mock
            v1._Body.pack(model_artifact, buf, compression=compression_format)

        buf.seek(0)
        loaded = v1._Body.unpack(buf, compression=compression_format)

        assert loaded.meta.id == model_artifact.meta.id
        assert isinstance(loaded.source, bytes)
        assert loaded.source == b"model-bytes"
        assert isinstance(loaded.directory, ModelDirectory)
        assert loaded.directory.exists()
        if model_artifact.artifacts:
            assert loaded.artifacts is not None
            assert "extra.bin" in loaded.artifacts
        else:
            assert loaded.artifacts == {}

        with patch.object(data_structures, "ModelSerializer") as MS:
            MS.from_lib.return_value = serializer_mock
            assert loaded.model == "loaded-model"
            assert serializer_mock.load.call_count == 1
            args, kwargs = serializer_mock.load.call_args
            assert args == (b"model-bytes",)
            assert kwargs == {"capabilities": loaded.meta.capabilities}

    def test_pack_rejects_path_source(self, tmp_path: pathlib.Path, compression_format: str) -> None:
        """v1 dump refuses :class:`pathlib.Path` sources — bundles must round-trip through v2."""
        src = tmp_path / "model_src"
        src.mkdir()

        meta = Metadata(
            id=uuid.uuid4(),
            timestamp=datetime.datetime(2024, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc),
            framework=FrameworkInfo(family="ml", lib="sklearn", version="1.0.0"),
            model=ModelInfo(obj="Obj", info=None, params=None, metrics=None),
            extra=None,
        )
        ma = ModelArtifact(meta=meta, source=src, artifacts=None)

        buf = io.BytesIO()
        with pytest.raises(UnsupportedProtocol, match="bundle source") as excinfo:
            v1._Body.pack(ma, buf, compression=compression_format)
        assert excinfo.value.protocol == 1
        assert "directory path" in excinfo.value.reason


class TestCaseV1Protocol:
    def test_dump(self, compression_format: str, model_artifact: ModelArtifact, serializer_mock) -> None:
        proto = v1.Protocol()
        buf = io.BytesIO()

        with patch.object(v1, "ModelSerializer") as MS:
            MS.from_lib.return_value = serializer_mock
            size = proto.dump(model_artifact, buf, compression=compression_format)

        assert size == buf.tell()
        assert size > 0

    def test_load(self, compression_format: str, model_artifact: ModelArtifact, serializer_mock) -> None:
        proto = v1.Protocol()
        buf = io.BytesIO()
        with patch.object(v1, "ModelSerializer") as MS:
            MS.from_lib.return_value = serializer_mock
            proto.dump(model_artifact, buf, compression=compression_format)

        buf.seek(0)
        out = proto.load(buf, compression=compression_format)

        assert out.meta.id == model_artifact.meta.id
        assert out.source == b"model-bytes"
        assert isinstance(out.directory, ModelDirectory)
        assert out.directory.exists()


class TestCaseV1FamilyLessRegression:
    """The v1 reader must accept master-era ``.flm`` bodies whose framework dict lacks ``family``."""

    def test_v1_reader_loads_family_less_meta(self, compression_format: str) -> None:
        meta_dict = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc).isoformat(),
            "framework": {"lib": "sklearn", "version": "1.0.0"},
            "model": {"obj": "Obj", "info": None, "params": None, "metrics": None},
            "extra": None,
        }
        meta_bytes = compress(encode_json(meta_dict, compact=True), compression_format)
        model_payload = compress(b"binary-model", compression_format)

        buf = io.BytesIO()
        buf.write(struct.pack(v1._Body._header_format, len(meta_bytes), len(model_payload), 0, 0))
        buf.write(meta_bytes)
        buf.write(model_payload)
        buf.seek(0)

        loaded = v1._Body.unpack(buf, compression=compression_format)

        assert loaded.meta.framework.family == "ml"
        assert loaded.meta.framework.lib == "sklearn"
        assert loaded.source == b"binary-model"
