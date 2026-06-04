import datetime
import io
import json
import pathlib
import struct
import typing as t
import uuid
from unittest.mock import patch

import pytest

from flama._core.json_encoder import encode_json
from flama.serialize import data_structures
from flama.serialize.data_structures import (
    CompressionFormat,
    FrameworkInfo,
    Metadata,
    ModelArtifact,
    ModelDirectory,
    ModelInfo,
)
from flama.serialize.exceptions import UnknownCompression, UnknownModelKind, UnsupportedProtocol
from flama.serialize.protocols import v2

SECTION_COMPRESSIONS = [
    pytest.param("inherit", id="inherit"),
    pytest.param("bz2", id="bz2"),
    pytest.param("lzma", id="lzma"),
    pytest.param("zlib", id="zlib"),
    pytest.param("zstd", id="zstd"),
    pytest.param(None, id="none"),
]


class TestCaseWireBytes:
    """Wire-byte alignment pinned against :class:`CompressionFormat` and the kind table."""

    @pytest.mark.parametrize(
        ["subject", "key", "expected"],
        [
            pytest.param("compression", "inherit", 0x00, id="compression-inherit"),
            pytest.param("compression", None, 0xFF, id="compression-none"),
            pytest.param("compression", "bz2", int(CompressionFormat.bz2), id="compression-bz2"),
            pytest.param("compression", "lzma", int(CompressionFormat.lzma), id="compression-lzma"),
            pytest.param("compression", "zlib", int(CompressionFormat.zlib), id="compression-zlib"),
            pytest.param("compression", "zstd", int(CompressionFormat.zstd), id="compression-zstd"),
            pytest.param("kind", "binary", 0x00, id="kind-binary"),
            pytest.param("kind", "bundle", 0x01, id="kind-bundle"),
        ],
    )
    def test_wire_byte(self, subject: str, key: t.Any, expected: int) -> None:
        if subject == "compression":
            assert v2._Compression._NAME_TO_BYTE[key] == expected
        else:
            assert v2._Kind._NAME_TO_BYTE[key] == expected


class TestCaseCompression:
    @pytest.mark.parametrize(
        ["knob", "parent_algo", "expected_algo"],
        [
            pytest.param("inherit", "zstd", "zstd", id="inherit-resolves-to-parent"),
            pytest.param(None, "zstd", None, id="none-passthrough"),
            pytest.param("bz2", "zstd", "bz2", id="override-bz2"),
            pytest.param(0x00, "zstd", "zstd", id="wire-inherit-byte"),
            pytest.param(0xFF, "zstd", None, id="wire-none-byte"),
            pytest.param(0x01, "zstd", "bz2", id="wire-bz2-byte"),
        ],
    )
    def test_derive(self, knob: v2.SectionCompression | int, parent_algo: str, expected_algo: str | None) -> None:
        assert v2._Compression(parent_algo).derive(knob).algo == expected_algo

    @pytest.mark.parametrize(
        ["action", "exception"],
        [
            pytest.param("derive_unknown_byte", UnknownCompression, id="derive-unknown-byte"),
            pytest.param("byte_unknown_name", UnknownCompression, id="byte-unknown-name"),
        ],
        indirect=["exception"],
    )
    def test_rejects_unknown(self, action: str, exception) -> None:
        parent = v2._Compression("zstd")
        with exception:
            if action == "derive_unknown_byte":
                parent.derive(0x77)
            else:
                parent.byte("snappy")  # type: ignore[arg-type]

    def test_passthrough(self) -> None:
        c = v2._Compression(None)
        assert c.compress(b"raw") == b"raw"
        assert c.decompress(b"raw") == b"raw"


class TestCaseKind:
    @pytest.mark.parametrize(
        ["family", "lib", "expected_name", "expected_byte"],
        [
            pytest.param("ml", "sklearn", "binary", 0x00, id="ml-sklearn-binary"),
            pytest.param("ml", "transformers", "bundle", 0x01, id="ml-transformers-bundle"),
            pytest.param("llm", "transformers", "bundle", 0x01, id="llm-transformers-bundle"),
        ],
    )
    def test_from_meta(self, family: str, lib: str, expected_name: str, expected_byte: int) -> None:
        meta = Metadata(
            id=uuid.uuid4(),
            timestamp=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
            framework=FrameworkInfo(family=family, lib=lib, version="0.0.0"),  # type: ignore[arg-type]
            model=ModelInfo(obj="Obj", info=None, params=None, metrics=None),
        )
        kind = v2._Kind.from_meta(meta)
        assert kind.name == expected_name
        assert kind.byte == expected_byte

    @pytest.mark.parametrize(
        ["byte", "expected_name", "exception"],
        [
            pytest.param(0x00, "binary", None, id="binary"),
            pytest.param(0x01, "bundle", None, id="bundle"),
            pytest.param(0xEE, None, UnknownModelKind, id="unknown"),
        ],
        indirect=["exception"],
    )
    def test_from_byte(self, byte: int, expected_name: str | None, exception) -> None:
        with exception:
            kind = v2._Kind.from_byte(byte)
        if not exception:
            assert kind.name == expected_name


class TestCaseArtifact:
    @pytest.mark.parametrize(
        ["algo"],
        [pytest.param("zstd", id="zstd"), pytest.param(None, id="passthrough")],
    )
    def test_pack_unpack_roundtrip(self, tmp_path: pathlib.Path, algo: str | None) -> None:
        content = b"artifact-bytes" * 8
        src = tmp_path / "sidecar.json"
        src.write_bytes(content)
        builder = v2._Artifact(v2._Compression(algo))

        packed = builder.pack("sidecar.json", src)
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        path, size = builder.unpack(packed, directory=out_dir)

        assert path.read_bytes() == content
        assert size == len(packed)


class TestCaseBody:
    @pytest.mark.parametrize(["section"], SECTION_COMPRESSIONS)
    @pytest.mark.parametrize("with_artifacts", [False, True], indirect=True)
    def test_roundtrip_binary_kind(
        self,
        compression_format: str,
        section: v2.SectionCompression,
        model_artifact: ModelArtifact,
        serializer_mock,
    ) -> None:
        buf = io.BytesIO()

        with patch.object(v2, "ModelSerializer") as MS:
            MS.from_lib.return_value = serializer_mock
            written = v2._Body(compression_format).pack(
                model_artifact,
                buf,
                meta_compression=section,
                artifact_compression=section,
                model_compression=section,
            )

        assert written == buf.tell()

        buf.seek(0)
        loaded = v2._Body(compression_format).unpack(buf)

        assert loaded.meta.id == model_artifact.meta.id
        assert isinstance(loaded.source, bytes)
        assert loaded.source == b"model-bytes"
        assert isinstance(loaded.directory, ModelDirectory)
        if model_artifact.artifacts:
            assert loaded.artifacts is not None
            assert "extra.bin" in loaded.artifacts
        else:
            assert loaded.artifacts == {}

    @pytest.mark.parametrize(["section"], SECTION_COMPRESSIONS)
    @pytest.mark.parametrize(
        ["family", "lib"],
        [
            pytest.param("ml", "transformers", id="ml-transformers"),
            pytest.param("llm", "transformers", id="llm-transformers"),
        ],
    )
    def test_roundtrip_bundle_kind(
        self,
        tmp_path: pathlib.Path,
        compression_format: str,
        section: v2.SectionCompression,
        family: str,
        lib: str,
    ) -> None:
        src = tmp_path / "model_src"
        src.mkdir()
        (src / "config.json").write_text('{"hello": "world"}')
        (src / "weights.bin").write_bytes(b"fake-weights" * 16)

        meta = Metadata(
            id=uuid.uuid4(),
            timestamp=datetime.datetime(2024, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc),
            framework=FrameworkInfo(family=family, lib=lib, version="0.0.0"),  # type: ignore[arg-type]
            model=ModelInfo(obj="Obj", info=None, params=None, metrics=None),
            extra=None,
        )
        ma = ModelArtifact(meta=meta, source=src, artifacts=None)

        buf = io.BytesIO()
        v2._Body(compression_format).pack(
            ma,
            buf,
            meta_compression=section,
            artifact_compression=section,
            model_compression=section,
        )

        buf.seek(0)
        loaded = v2._Body(compression_format).unpack(buf)

        assert isinstance(loaded.source, pathlib.Path)
        assert loaded.source.is_dir()
        assert (loaded.source / "config.json").read_text() == '{"hello": "world"}'
        assert (loaded.source / "weights.bin").read_bytes() == b"fake-weights" * 16

    @pytest.mark.parametrize(
        ["exception"],
        [
            pytest.param(
                (UnsupportedProtocol, "binary-kind 'sklearn' model from a directory source"),
                id="binary-kind-directory-source",
            ),
        ],
        indirect=["exception"],
    )
    def test_pack_rejects_binary_kind_with_directory_source(
        self,
        tmp_path: pathlib.Path,
        compression_format: str,
        exception,
    ) -> None:
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

        with exception:
            v2._Body(compression_format).pack(ma, io.BytesIO())

    def test_lazy_model_materialises_from_source(
        self, compression_format: str, model_artifact: ModelArtifact, serializer_mock
    ) -> None:
        buf = io.BytesIO()
        with patch.object(v2, "ModelSerializer") as MS:
            MS.from_lib.return_value = serializer_mock
            v2._Body(compression_format).pack(model_artifact, buf)

        buf.seek(0)
        loaded = v2._Body(compression_format).unpack(buf)

        with patch.object(data_structures, "ModelSerializer") as MS:
            MS.from_lib.return_value = serializer_mock
            assert loaded.model == "loaded-model"
            assert serializer_mock.load.call_count == 1
            args, kwargs = serializer_mock.load.call_args
            assert args == (b"model-bytes",)
            assert kwargs == {"capabilities": loaded.meta.capabilities}

    @pytest.mark.parametrize("with_artifacts", [True], indirect=True)
    def test_unpack_meta(self, compression_format: str, model_artifact: ModelArtifact, serializer_mock) -> None:
        buf = io.BytesIO()
        with patch.object(v2, "ModelSerializer") as MS:
            MS.from_lib.return_value = serializer_mock
            v2._Body(compression_format).pack(model_artifact, buf)

        buf.seek(0)
        meta = v2._Body(compression_format).unpack_meta(buf)
        assert meta.id == model_artifact.meta.id

    @pytest.mark.parametrize("with_artifacts", [True], indirect=True)
    def test_unpack_manifest(self, compression_format: str, model_artifact: ModelArtifact, serializer_mock) -> None:
        buf = io.BytesIO()
        with patch.object(v2, "ModelSerializer") as MS:
            MS.from_lib.return_value = serializer_mock
            v2._Body(compression_format).pack(model_artifact, buf)

        buf.seek(0)
        names = v2._Body(compression_format).unpack_manifest(buf)
        assert names == ("extra.bin",)

    @pytest.mark.parametrize(
        ["exception"],
        [pytest.param(UnknownModelKind, id="unknown-model-kind")],
        indirect=["exception"],
    )
    def test_unknown_model_kind_rejected(self, compression_format: str, exception) -> None:
        meta = Metadata(
            id=uuid.uuid4(),
            timestamp=datetime.datetime(2024, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc),
            framework=FrameworkInfo(family="ml", lib="sklearn", version="1.0.0"),
            model=ModelInfo(obj="Obj", info=None, params=None, metrics=None),
            extra=None,
        )
        passthrough_byte = v2._Compression._NAME_TO_BYTE[None]
        meta_bytes = struct.pack(v2._Body._meta_header_format, passthrough_byte) + encode_json(
            meta.to_dict(), compact=True
        )
        artifacts_bytes = struct.pack(v2._Body._artifacts_header_format, passthrough_byte, 0)
        model_bytes = struct.pack(v2._Body._model_header_format, passthrough_byte, 0xEE) + b""

        buf = io.BytesIO()
        buf.write(struct.pack(v2._Body._header_format, len(meta_bytes), len(artifacts_bytes), len(model_bytes)))
        buf.write(meta_bytes)
        buf.write(artifacts_bytes)
        buf.write(model_bytes)
        buf.seek(0)

        with exception:
            v2._Body(compression_format).unpack(buf)

    @pytest.mark.parametrize(
        ["exception"],
        [pytest.param(UnknownCompression, id="unknown-section-compression")],
        indirect=["exception"],
    )
    def test_unknown_section_compression_rejected(self, compression_format: str, exception) -> None:
        meta_bytes = struct.pack(v2._Body._meta_header_format, 0x55) + b"junk"
        passthrough_byte = v2._Compression._NAME_TO_BYTE[None]
        artifacts_bytes = struct.pack(v2._Body._artifacts_header_format, passthrough_byte, 0)
        model_bytes = b""

        buf = io.BytesIO()
        buf.write(struct.pack(v2._Body._header_format, len(meta_bytes), len(artifacts_bytes), len(model_bytes)))
        buf.write(meta_bytes)
        buf.write(artifacts_bytes)
        buf.write(model_bytes)
        buf.seek(0)

        with exception:
            v2._Body(compression_format).unpack_meta(buf)

    def test_meta_section_independent_codec(
        self, compression_format: str, model_artifact: ModelArtifact, serializer_mock
    ) -> None:
        """A meta section can run uncompressed while the file-level codec stays unchanged."""
        buf = io.BytesIO()
        with patch.object(v2, "ModelSerializer") as MS:
            MS.from_lib.return_value = serializer_mock
            v2._Body(compression_format).pack(model_artifact, buf, meta_compression=None)

        buf.seek(0)
        meta_size, _arts_size, _model_size = struct.unpack(v2._Body._header_format, buf.read(v2._Body._header_size))
        meta_frame = buf.read(meta_size)
        (section_byte,) = struct.unpack(v2._Body._meta_header_format, meta_frame[: v2._Body._meta_header_size])
        assert section_byte == v2._Compression._NAME_TO_BYTE[None]
        json.loads(meta_frame[v2._Body._meta_header_size :].decode())

        buf.seek(0)
        meta = v2._Body(compression_format).unpack_meta(buf)
        assert meta.id == model_artifact.meta.id


class TestCaseProtocol:
    def test_dump(self, compression_format: str, model_artifact: ModelArtifact, serializer_mock) -> None:
        proto = v2.Protocol()
        buf = io.BytesIO()

        with patch.object(v2, "ModelSerializer") as MS:
            MS.from_lib.return_value = serializer_mock
            size = proto.dump(model_artifact, buf, compression=compression_format)

        assert size == buf.tell()
        assert size > 0

    def test_load(self, compression_format: str, model_artifact: ModelArtifact, serializer_mock) -> None:
        proto = v2.Protocol()
        buf = io.BytesIO()
        with patch.object(v2, "ModelSerializer") as MS:
            MS.from_lib.return_value = serializer_mock
            proto.dump(model_artifact, buf, compression=compression_format)

        buf.seek(0)
        out = proto.load(buf, compression=compression_format)

        assert out.meta.id == model_artifact.meta.id
        assert out.source == b"model-bytes"
        assert isinstance(out.directory, ModelDirectory)
        assert out.directory.exists()
