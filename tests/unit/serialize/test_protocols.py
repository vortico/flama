import datetime
import io
import pathlib
import struct
import uuid
from unittest.mock import MagicMock, patch

import pytest

from flama.serialize.data_structures import FrameworkInfo, Metadata, ModelArtifact, ModelDirectory, ModelInfo
from flama.serialize.protocols import v1
from flama.serialize.protocols.base import Protocol as ProtocolFactory


def _model_artifact(tmp_path: pathlib.Path, *, with_artifacts: bool) -> ModelArtifact:
    meta = Metadata(
        id=uuid.uuid4(),
        timestamp=datetime.datetime(2024, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc),
        framework=FrameworkInfo(lib="sklearn", version="1.0.0"),
        model=ModelInfo(obj="Obj", info={"x": 1}, params={"p": 1}, metrics=None),
        extra={"e": 2},
    )
    artifacts: dict[str, str | pathlib.Path] | None
    if with_artifacts:
        side = tmp_path / "extra.bin"
        side.write_bytes(b"extra-file")
        artifacts = {"extra.bin": side}
    else:
        artifacts = None
    return ModelArtifact(meta=meta, model="my-model", artifacts=artifacts)


def _serializer() -> MagicMock:
    ser = MagicMock()
    ser.dump.return_value = b"model-bytes"
    ser.load.return_value = "loaded-model"
    return ser


class TestCaseProtocolFactory:
    @pytest.mark.parametrize(
        ["version", "expected"],
        [pytest.param(1, v1.Protocol, id="v1")],
    )
    def test_from_version(self, version: int, expected: type) -> None:
        assert isinstance(ProtocolFactory.from_version(version), expected)


class TestCaseV1Artifact:
    def test_pack(self, compression_format: str, tmp_path: pathlib.Path) -> None:
        src = tmp_path / "sidecar.json"
        src.write_bytes(b"artifact-bytes" * 8)

        packed = v1._Artifact.pack("sidecar.json", src, compression=compression_format)

        name_size, content_size = struct.unpack(v1._Artifact._header_format, packed[: v1._Artifact._header_size])
        assert name_size == len("sidecar.json")
        assert len(packed) == v1._Artifact._header_size + name_size + content_size

    def test_unpack(self, compression_format: str, tmp_path: pathlib.Path) -> None:
        content = b"artifact-bytes" * 8
        src = tmp_path / "sidecar.json"
        src.write_bytes(content)
        packed = v1._Artifact.pack("sidecar.json", src, compression=compression_format)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        path, size = v1._Artifact.unpack(packed, compression=compression_format, directory=out_dir)

        assert path.read_bytes() == content
        assert size == len(packed)


class TestCaseV1Body:
    @pytest.mark.parametrize(
        ["with_artifacts"],
        [pytest.param(False, id="no_artifacts"), pytest.param(True, id="with_artifacts")],
    )
    def test_pack(self, tmp_path: pathlib.Path, compression_format: str, with_artifacts: bool) -> None:
        ma = _model_artifact(tmp_path, with_artifacts=with_artifacts)
        ser = _serializer()
        buf = io.BytesIO()

        with patch.object(v1, "ModelSerializer") as MS:
            MS.from_lib.return_value = ser
            written = v1._Body.pack(ma, buf, compression=compression_format)

        assert written == buf.tell()
        assert written > v1._Body._header_size

    @pytest.mark.parametrize(
        ["with_artifacts"],
        [pytest.param(False, id="no_artifacts"), pytest.param(True, id="with_artifacts")],
    )
    def test_unpack(self, tmp_path: pathlib.Path, compression_format: str, with_artifacts: bool) -> None:
        ma = _model_artifact(tmp_path, with_artifacts=with_artifacts)
        ser = _serializer()
        buf = io.BytesIO()
        with patch.object(v1, "ModelSerializer") as MS:
            MS.from_lib.return_value = ser
            v1._Body.pack(ma, buf, compression=compression_format)

        buf.seek(0)
        with patch.object(v1, "ModelSerializer") as MS:
            MS.from_lib.return_value = ser
            loaded = v1._Body.unpack(buf, compression=compression_format)

        assert loaded.model == "loaded-model"
        assert loaded.meta.id == ma.meta.id
        assert isinstance(loaded.directory, ModelDirectory)
        assert loaded.directory.exists()
        if with_artifacts:
            assert loaded.artifacts is not None
            assert "extra.bin" in loaded.artifacts
        else:
            assert loaded.artifacts == {}


class TestCaseV1Protocol:
    def test_dump(self, tmp_path: pathlib.Path, compression_format: str) -> None:
        ma = _model_artifact(tmp_path, with_artifacts=False)
        ser = _serializer()
        proto = v1.Protocol()
        buf = io.BytesIO()

        with patch.object(v1, "ModelSerializer") as MS:
            MS.from_lib.return_value = ser
            size = proto.dump(ma, buf, compression=compression_format)

        assert size == buf.tell()
        assert size > 0

    def test_load(self, tmp_path: pathlib.Path, compression_format: str) -> None:
        ma = _model_artifact(tmp_path, with_artifacts=False)
        ser = _serializer()
        proto = v1.Protocol()
        buf = io.BytesIO()
        with patch.object(v1, "ModelSerializer") as MS:
            MS.from_lib.return_value = ser
            proto.dump(ma, buf, compression=compression_format)

        buf.seek(0)
        with patch.object(v1, "ModelSerializer") as MS:
            MS.from_lib.return_value = ser
            out = proto.load(buf, compression=compression_format)

        assert out.meta.id == ma.meta.id
        assert out.model == "loaded-model"
        assert isinstance(out.directory, ModelDirectory)
        assert out.directory.exists()
