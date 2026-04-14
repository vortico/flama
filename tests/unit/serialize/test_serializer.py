import collections
import datetime
import io
import json
import pathlib
import re
import struct
import tempfile
import typing as t
import uuid
from unittest.mock import MagicMock, patch

import pytest

import flama
from flama.serialize.compression import Compression
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
        params=["sklearn", "sklearn-pipeline", "tensorflow", "torch"],
        ids=["sklearn", "sklearn_pipeline", "tensorflow", "torch"],
    )
    def model(self, request):
        try:
            return collections.namedtuple("Model", ("lib", "model", "model_cls"))(
                model_factory.lib(request.param),
                model_factory.model(request.param),
                model_factory.model_cls(request.param),
            )
        except NotInstalled as e:
            pytest.skip(f"Lib '{str(e)}' is not installed.")

    @pytest.mark.parametrize(
        ["stream", "path", "exception"],
        (
            pytest.param(
                True,
                False,
                None,
                id="stream",
            ),
            pytest.param(
                False,
                True,
                None,
                id="path",
            ),
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
        ),
        indirect=["exception"],
    )
    def test_serialize(self, artifact, model, compression_format, protocol_version, stream, path, exception):
        id_ = uuid.uuid4()
        timestamp = datetime.datetime.now(tz=datetime.timezone.utc)
        params = {"param": "1"}
        metrics = {"metric": "1"}
        extra = {"foo": "bar"}

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
                    artifacts={"foo.json": artifact},
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

    def test_serialize_path(self, artifact, model, compression_format, protocol_version):
        id_ = uuid.uuid4()
        timestamp = datetime.datetime.now(tz=datetime.timezone.utc)
        params = {"param": "1"}
        metrics = {"metric": "1"}
        extra = {"foo": "bar"}

        with tempfile.NamedTemporaryFile(suffix=".flm") as tmp:
            flama.dump(
                model.model,
                path=tmp.name,
                protocol=protocol_version,
                compression=compression_format,
                model_id=id_,
                timestamp=timestamp,
                params=params,
                metrics=metrics,
                extra=extra,
                artifacts={"foo.json": artifact},
            )

            load_model = flama.load(path=tmp.name)

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
        ["use_path", "stream", "path_arg"],
        [
            pytest.param(False, "auto", None, id="stream"),
            pytest.param(True, None, "auto", id="path"),
        ],
    )
    def test_dump(
        self,
        tmp_path: pathlib.Path,
        compression_format: str,
        protocol_version: int,
        use_path: bool,
        stream: str | None,
        path_arg: str | None,
    ) -> None:
        mock_artifact = MagicMock()
        mock_body = b"packed-body"
        mock_protocol = MagicMock()
        mock_protocol.dump.return_value = mock_body

        if use_path:
            target = tmp_path / "out.flm"
        else:
            target = None

        buf = io.BytesIO() if not use_path else None

        with (
            patch("flama.serialize.serializer.Protocol.from_version", return_value=mock_protocol),
            patch("flama.serialize.serializer.ModelArtifact.from_model", return_value=mock_artifact),
        ):
            Serializer.dump(
                object(),
                buf,
                path=target,
                protocol=protocol_version,
                compression=compression_format,
                model_id="mid" if not use_path else None,
            )

        c = Compression(compression_format)
        header = struct.pack(Serializer._header_format, protocol_version, c.format, len(mock_body))

        if use_path:
            assert target.read_bytes() == header + mock_body
        else:
            buf.seek(0)
            proto_id, fmt_val, body_len = struct.unpack(Serializer._header_format, buf.read(Serializer._header_size))
            assert proto_id == protocol_version
            assert fmt_val == c.format
            assert body_len == len(mock_body)
            assert buf.read() == mock_body

        mock_protocol.dump.assert_called_once()
        dump_kw = mock_protocol.dump.call_args[1]
        assert dump_kw["compression"].format == c.format

    @pytest.mark.parametrize(
        ["stream", "path", "message"],
        [
            pytest.param(
                None,
                None,
                "Either a 'stream' or a 'path' needs to be provided",
                id="neither",
            ),
            pytest.param(
                io.BytesIO(),
                pathlib.Path("unused"),
                "Parameters 'stream' and 'path' are mutually exclusive",
                id="both",
            ),
        ],
    )
    def test_dump_argument_errors(
        self,
        stream: io.BytesIO | None,
        path: pathlib.Path | None,
        message: str,
    ) -> None:
        with pytest.raises(ValueError, match=re.escape(message)):
            Serializer.dump(object(), stream, path=path)

    @pytest.mark.parametrize(
        ["use_path"],
        [
            pytest.param(False, id="stream"),
            pytest.param(True, id="path"),
        ],
    )
    def test_load(
        self,
        tmp_path: pathlib.Path,
        compression_format: str,
        protocol_version: int,
        use_path: bool,
    ) -> None:
        body = b"stored-body"
        c = Compression(compression_format)
        header = struct.pack(Serializer._header_format, protocol_version, c.format, len(body))

        mock_loaded = MagicMock()
        mock_loaded.meta.framework.lib = "sklearn"
        mock_loaded.meta.framework.version = "9.9.9"
        mock_protocol = MagicMock()
        mock_protocol.load.return_value = mock_loaded

        if use_path:
            path = tmp_path / "in.flm"
            path.write_bytes(header + body)
            stream = None
        else:
            path = None
            stream = io.BytesIO(header + body)

        with (
            patch("flama.serialize.serializer.Protocol.from_version", return_value=mock_protocol) as p_proto,
            patch("flama.serialize.serializer.ModelSerializer.from_lib") as p_ms,
        ):
            p_ms.return_value.version.return_value = "9.9.9"
            out = Serializer.load(stream, path=path)

        assert out is mock_loaded
        p_proto.assert_called_once_with(protocol_version)
        mock_protocol.load.assert_called_once()
        load_args, load_kw = mock_protocol.load.call_args
        assert load_args[0] == body
        assert load_kw["compression"].format == c.format
        p_ms.assert_called_once_with("sklearn")

    @pytest.mark.parametrize(
        ["stream", "path", "message"],
        [
            pytest.param(
                None,
                None,
                "Either a 'stream' or a 'path' needs to be provided",
                id="neither",
            ),
            pytest.param(
                io.BytesIO(),
                pathlib.Path("unused"),
                "Parameters 'stream' and 'path' are mutually exclusive",
                id="both",
            ),
        ],
    )
    def test_load_argument_errors(
        self,
        stream: io.BytesIO | None,
        path: pathlib.Path | None,
        message: str,
    ) -> None:
        with pytest.raises(ValueError, match=re.escape(message)):
            Serializer.load(stream, path=path)
