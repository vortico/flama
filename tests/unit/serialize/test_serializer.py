import collections
import datetime
import io
import json
import pathlib
import struct
import tempfile
import typing as t
import uuid
from unittest.mock import MagicMock, call, patch

import pytest

import flama
from flama.serialize.data_structures import CompressionFormat
from flama.serialize.serializer import Serializer
from tests._utils import NotInstalled, model_factory


class TestCaseSerialize:
    @pytest.fixture(scope="function")
    def artifact(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as tmp:
            json.dump({"foo": "bar"}, tmp)
            yield tmp.name

    @pytest.fixture(
        scope="function",
        params=["sklearn", "sklearn-pipeline", "tensorflow", "torch", "transformers"],
        ids=["sklearn", "sklearn_pipeline", "tensorflow", "torch", "transformers"],
    )
    def model(self, request):
        try:
            return collections.namedtuple("Model", ("lib", "model", "model_cls", "artifacts", "config"))(
                model_factory.lib(request.param),
                model_factory.model(request.param),
                model_factory.model_cls(request.param),
                model_factory.artifacts(request.param),
                model_factory.config(request.param),
            )
        except NotInstalled as e:
            pytest.skip(f"Lib '{str(e)}' is not installed.")

    @pytest.mark.parametrize(
        ["stream", "path", "exception"],
        [
            pytest.param(True, False, None, id="stream"),
            pytest.param(False, True, None, id="path"),
            pytest.param(
                True,
                True,
                ValueError("Parameters 'stream' and 'path' are mutually exclusive"),
                id="stream_and_path",
            ),
            pytest.param(
                False,
                False,
                ValueError("Either a 'stream' or a 'path' needs to be provided"),
                id="error_no_stream_no_path",
            ),
        ],
        indirect=["exception"],
    )
    def test_serialize(self, artifact, model, compression_format, protocol_version, stream, path, exception):
        id_ = uuid.uuid4()
        timestamp = datetime.datetime.now(tz=datetime.timezone.utc)
        params = {"param": "1"}
        metrics = {"metric": "1"}
        extra = {"foo": "bar"}
        artifacts = {**(model.artifacts or {}), "foo.json": artifact}

        with tempfile.NamedTemporaryFile(suffix=".flm") as tmp:
            with exception:
                flama.dump(
                    model.model,
                    t.cast(t.BinaryIO, tmp.file if stream else None),
                    path=tmp.name if path else None,
                    protocol=protocol_version,
                    compression=compression_format,
                    model_id=id_,
                    timestamp=timestamp,
                    params=params,
                    metrics=metrics,
                    extra=extra,
                    config=model.config,
                    artifacts=artifacts,
                    lib=model.lib,
                )

            tmp.seek(0)

            with exception:
                load_model = flama.load(
                    t.cast(t.BinaryIO, tmp.file if stream else None),
                    path=tmp.name if path else None,
                )

                assert isinstance(load_model.model, model.model_cls)
                assert load_model.meta.id == id_
                assert load_model.meta.timestamp == timestamp
                assert load_model.meta.framework.lib == model.lib
                assert load_model.meta.model.params == params
                assert load_model.meta.model.metrics == metrics
                assert load_model.meta.extra == extra
                assert load_model.artifacts and "foo.json" in load_model.artifacts


class TestCaseSerializer:
    @pytest.mark.parametrize(
        ["m", "stream", "path", "compression", "lib", "exception"],
        [
            pytest.param("obj", True, False, None, None, None, id="stream"),
            pytest.param("obj", False, True, None, None, None, id="path"),
            pytest.param(
                "obj",
                False,
                False,
                None,
                None,
                ValueError("Either a 'stream' or a 'path' needs to be provided"),
                id="neither",
            ),
            pytest.param(
                "obj",
                True,
                True,
                None,
                None,
                ValueError("Parameters 'stream' and 'path' are mutually exclusive"),
                id="both",
            ),
            pytest.param(
                "directory",
                True,
                False,
                None,
                None,
                ValueError("Parameter 'lib' is required when 'm' is a directory path"),
                id="path-no-lib",
            ),
            pytest.param(
                "obj", True, False, "wrong", None, ValueError("Wrong format 'wrong'"), id="unknown-compression"
            ),
        ],
        indirect=["exception"],
    )
    def test_dump(
        self,
        tmp_path: pathlib.Path,
        compression_format: str,
        protocol_version: int,
        m: str,
        stream: bool,
        path: bool,
        compression: str | None,
        lib: str | None,
        exception,
    ) -> None:
        actual_compression = compression or compression_format
        m_value: t.Any = pathlib.Path("/some/model/dir") if m == "directory" else object()
        target = tmp_path / "out.flm" if path else None
        buf = io.BytesIO() if stream else None

        mock_artifact = MagicMock()
        mock_body = b"packed-body"
        mock_protocol = MagicMock()

        def fake_dump(_m, f, *, compression, **kwargs):
            f.write(mock_body)
            return len(mock_body)

        mock_protocol.dump.side_effect = fake_dump

        with (
            patch("flama.serialize.serializer.Protocol.from_version", return_value=mock_protocol),
            patch("flama.serialize.serializer.ModelArtifact.from_model", return_value=mock_artifact),
        ):
            with exception:
                Serializer.dump(
                    m_value,
                    buf,
                    path=target,
                    protocol=protocol_version,
                    compression=t.cast(t.Any, actual_compression),
                    lib=t.cast(t.Any, lib),
                )

        if not exception:
            fmt_value = CompressionFormat[actual_compression].value
            header = struct.pack(Serializer._header_format, protocol_version, fmt_value, len(mock_body))

            if path:
                assert target is not None
                assert target.read_bytes() == header + mock_body
            else:
                assert buf is not None
                buf.seek(0)
                proto_id, fmt_val, body_len = struct.unpack(
                    Serializer._header_format, buf.read(Serializer._header_size)
                )
                assert proto_id == protocol_version
                assert fmt_val == fmt_value
                assert body_len == len(mock_body)
                assert buf.read() == mock_body

            assert len(mock_protocol.dump.call_args_list) == 1
            assert mock_protocol.dump.call_args[1]["compression"] == actual_compression

    @pytest.mark.parametrize(
        ["stream", "path", "format_value", "exception"],
        [
            pytest.param(True, False, "valid", None, id="stream"),
            pytest.param(False, True, "valid", None, id="path"),
            pytest.param(
                False,
                False,
                "valid",
                ValueError("Either a 'stream' or a 'path' needs to be provided"),
                id="neither",
            ),
            pytest.param(
                True,
                True,
                "valid",
                ValueError("Parameters 'stream' and 'path' are mutually exclusive"),
                id="both",
            ),
            pytest.param(True, False, 99, ValueError("Wrong format '99'"), id="unknown-compression"),
        ],
        indirect=["exception"],
    )
    def test_load(
        self,
        tmp_path: pathlib.Path,
        compression_format: str,
        protocol_version: int,
        stream: bool,
        path: bool,
        format_value: str | int,
        exception,
    ) -> None:
        body = b"stored-body"
        fmt_value = CompressionFormat[compression_format].value if format_value == "valid" else format_value
        header = struct.pack(Serializer._header_format, protocol_version, t.cast(int, fmt_value), len(body))

        mock_loaded = MagicMock()
        mock_loaded.meta.framework.lib = "sklearn"
        mock_loaded.meta.framework.version = "9.9.9"
        mock_protocol = MagicMock()
        captured: dict[str, bytes] = {}

        def fake_load(f, *, compression, lib=None, **kwargs):
            captured["body"] = f.read()
            return mock_loaded

        mock_protocol.load.side_effect = fake_load

        if path:
            target = tmp_path / "in.flm"
            target.write_bytes(header + body)
        else:
            target = None
        buf = io.BytesIO(header + body) if stream else None

        with (
            patch("flama.serialize.serializer.Protocol.from_version", return_value=mock_protocol) as p_proto,
            patch("flama.serialize.serializer.ModelSerializer.from_lib") as p_ms,
        ):
            p_ms.return_value.version.return_value = "9.9.9"
            with exception:
                out = Serializer.load(buf, path=target)

        if not exception:
            assert out is mock_loaded
            assert p_proto.call_args_list == [call(protocol_version)]
            assert len(mock_protocol.load.call_args_list) == 1
            assert captured["body"] == body
            assert mock_protocol.load.call_args[1]["compression"] == compression_format
            assert p_ms.call_args_list == [call("sklearn")]
