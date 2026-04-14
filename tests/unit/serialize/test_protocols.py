import datetime
import pathlib
import uuid
from unittest.mock import MagicMock, patch

import pytest

from flama.serialize.compression import Compression
from flama.serialize.data_structures import FrameworkInfo, Metadata, ModelArtifact, ModelInfo
from flama.serialize.protocols import v1 as v1_protocol
from flama.serialize.protocols.base import Protocol as ProtocolFactory


class TestCaseProtocolFactory:
    def test_from_version_v1(self) -> None:
        proto = ProtocolFactory.from_version(1)

        assert isinstance(proto, v1_protocol.Protocol)


class TestCaseV1Artifact:
    def test_pack_and_unpack_roundtrip(self, compression_format: str, tmp_path: pathlib.Path) -> None:
        compression = Compression(compression_format)
        content = b"artifact-bytes" * 8

        src = tmp_path / "sidecar.json"
        src.write_bytes(content)

        packed = v1_protocol._Artifact.pack("sidecar.json", src, compression=compression)
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        path, size = v1_protocol._Artifact.unpack(packed, compression=compression, directory=out_dir)

        assert path.read_bytes() == content
        assert size == len(packed)


class TestCaseV1Body:
    def _make_artifact(self, tmp_path: pathlib.Path, *, with_artifacts: bool) -> ModelArtifact:
        meta = Metadata(
            id=uuid.uuid4(),
            timestamp=datetime.datetime(2024, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc),
            framework=FrameworkInfo(lib="sklearn", version="1.0.0"),
            model=ModelInfo(obj="Obj", info={"x": 1}, params={"p": 1}, metrics=None),
            extra={"e": 2},
        )
        if with_artifacts:
            side = tmp_path / "extra.bin"
            side.write_bytes(b"extra-file")
            artifacts: dict[str, str | pathlib.Path] | None = {"extra.bin": side}
        else:
            artifacts = None

        return ModelArtifact(meta=meta, model="my-model", artifacts=artifacts)

    @pytest.mark.parametrize(
        "with_artifacts",
        [
            pytest.param(False, id="no_artifacts"),
            pytest.param(True, id="with_artifacts"),
        ],
    )
    def test_pack_and_unpack_roundtrip(
        self, tmp_path: pathlib.Path, compression_format: str, with_artifacts: bool
    ) -> None:
        compression = Compression(compression_format)
        ma = self._make_artifact(tmp_path, with_artifacts=with_artifacts)
        ser = MagicMock()
        ser.dump.return_value = b"model-bytes"
        ser.load.return_value = "loaded-model"

        with patch.object(v1_protocol, "ModelSerializer") as MS:
            MS.from_lib.return_value = ser
            raw = v1_protocol._Body.pack(ma, compression=compression)

        unpack_root = tmp_path / "unpack"
        unpack_root.mkdir()

        with patch.object(v1_protocol, "ModelSerializer") as MS:
            MS.from_lib.return_value = ser
            loaded = v1_protocol._Body.unpack(raw, compression=compression, directory=unpack_root)

        assert loaded.model == "loaded-model"
        assert loaded.meta.id == ma.meta.id
        if with_artifacts:
            assert loaded.artifacts is not None
            assert "extra.bin" in loaded.artifacts
        else:
            assert loaded.artifacts == {}


class TestCaseV1Protocol:
    def test_dump_and_load(self, compression_format: str) -> None:
        compression = Compression(compression_format)
        ma = ModelArtifact(
            meta=Metadata(
                id=uuid.uuid4(),
                timestamp=datetime.datetime(2020, 5, 5, tzinfo=datetime.timezone.utc),
                framework=FrameworkInfo(lib="sklearn", version="1.0.0"),
                model=ModelInfo(obj="O", info=None),
                extra=None,
            ),
            model="m",
            artifacts=None,
        )
        ser = MagicMock()
        ser.dump.return_value = b"blob"
        ser.load.return_value = "roundtrip-model"

        proto = v1_protocol.Protocol()

        with patch.object(v1_protocol, "ModelSerializer") as MS:
            MS.from_lib.return_value = ser
            blob = proto.dump(ma, compression=compression)

        with patch.object(v1_protocol, "ModelSerializer") as MS:
            MS.from_lib.return_value = ser
            out = proto.load(blob, compression=compression)

        assert out.meta.id == ma.meta.id
        assert out.model == "roundtrip-model"
