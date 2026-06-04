import collections
import contextlib
import datetime
import io
import json
import logging
import pathlib
import struct
import tempfile
import typing as t
import uuid
from unittest.mock import MagicMock, call, patch

import pytest

import flama
from flama.serialize.data_structures import CompressionFormat, LLMModelCapabilities
from flama.serialize.exceptions import UnknownCompression
from flama.serialize.serializer import Serializer
from tests._utils import NotInstalled, model_factory


class TestCaseSerializer:
    """Cover :class:`Serializer` end-to-end: high-level :func:`flama.dump` / :func:`flama.load`
    round-trips against real models, plus the lower-level :meth:`Serializer.dump`,
    :meth:`Serializer.load`, :meth:`Serializer.meta`, :meth:`Serializer.manifest`, and the
    progress-logging emitted during :meth:`Serializer.load`.
    """

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
            return collections.namedtuple("Model", ("family", "lib", "model", "model_cls", "artifacts", "config"))(
                model_factory.family(request.param),
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
    def test_round_trip_real_models(
        self, artifact, model, compression_format, protocol_version, stream, path, exception
    ):
        if protocol_version == 1 and (model.family == "llm" or model.lib == "transformers"):
            pytest.skip("Protocol v1 is binary-only; bundle artifacts require protocol >= 2")

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
                    family=model.family,
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
                assert load_model.meta.framework.family == model.family
                assert load_model.meta.framework.lib == model.lib
                assert load_model.meta.model.params == params
                assert load_model.meta.model.metrics == metrics
                assert load_model.meta.extra == extra
                assert load_model.artifacts and "foo.json" in load_model.artifacts

    @pytest.mark.parametrize(
        ["m", "stream", "path", "compression", "lib", "family", "capabilities", "exception"],
        [
            pytest.param("obj", True, False, None, None, "ml", None, None, id="stream"),
            pytest.param("obj", False, True, None, None, "ml", None, None, id="path"),
            pytest.param(
                "obj",
                False,
                False,
                None,
                None,
                "ml",
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
                "ml",
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
                "ml",
                None,
                ValueError("Parameter 'lib' is required when 'm' is a directory path"),
                id="path_no_lib",
            ),
            pytest.param(
                "obj",
                True,
                False,
                "wrong",
                None,
                "ml",
                None,
                UnknownCompression("wrong"),
                id="unknown_compression",
            ),
            pytest.param(
                "obj",
                False,
                True,
                None,
                None,
                "llm",
                LLMModelCapabilities(image=True, audio=True),
                None,
                id="forwards_capabilities_override",
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
        family: t.Literal["ml", "llm"],
        capabilities: LLMModelCapabilities | None,
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
            patch("flama.serialize.serializer.ModelArtifact.from_model", return_value=mock_artifact) as p_art,
        ):
            with exception:
                Serializer.dump(
                    m_value,
                    buf,
                    path=target,
                    family=family,
                    protocol=protocol_version,
                    compression=t.cast(t.Any, actual_compression),
                    lib=t.cast(t.Any, lib),
                    capabilities=capabilities,
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
            assert p_art.call_args.kwargs["family"] == family
            if capabilities is not None:
                assert p_art.call_args.kwargs["capabilities"] is capabilities

    @pytest.mark.parametrize(
        ["stream", "path", "format_value", "expect_logs", "exception"],
        [
            pytest.param(True, False, "valid", False, None, id="stream"),
            pytest.param(False, True, "valid", False, None, id="path"),
            pytest.param(
                False,
                False,
                "valid",
                False,
                ValueError("Either a 'stream' or a 'path' needs to be provided"),
                id="neither",
            ),
            pytest.param(
                True,
                True,
                "valid",
                False,
                ValueError("Parameters 'stream' and 'path' are mutually exclusive"),
                id="both",
            ),
            pytest.param(True, False, 99, False, UnknownCompression(99), id="unknown_compression"),
            pytest.param(False, True, "valid", True, None, id="logs_progress"),
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
        expect_logs: bool,
        exception,
        caplog_flama: pytest.LogCaptureFixture,
    ) -> None:
        body = b"stored-body"
        fmt_value = CompressionFormat[compression_format].value if format_value == "valid" else format_value
        header = struct.pack(Serializer._header_format, protocol_version, t.cast(int, fmt_value), len(body))

        mock_loaded = MagicMock()
        mock_loaded.meta.framework.lib = "sklearn"
        mock_loaded.meta.framework.version = "9.9.9"
        mock_protocol = MagicMock()
        captured: dict[str, bytes] = {}

        def fake_load(f, *, compression, **kwargs):
            captured["body"] = f.read()
            return mock_loaded

        mock_protocol.load.side_effect = fake_load

        if path:
            target = tmp_path / "in.flm"
            target.write_bytes(header + body)
        else:
            target = None
        buf = io.BytesIO(header + body) if stream else None

        log_cm: t.ContextManager[t.Any] = (
            caplog_flama.at_level(logging.INFO, logger="flama.serialize.serializer")
            if expect_logs
            else contextlib.nullcontext()
        )
        with (
            patch("flama.serialize.serializer.Protocol.from_version", return_value=mock_protocol) as p_proto,
            patch("flama.serialize.serializer.ModelSerializer.from_lib") as p_ms,
            log_cm,
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

        if expect_logs:
            messages = [
                record.getMessage()
                for record in caplog_flama.records
                if record.name == "flama.serialize.serializer"
            ]
            assert any(f"Loading model from {target}" in m for m in messages)
            assert any(
                f"Loaded model from {target}" in m and "MB compressed" in m and "in " in m for m in messages
            )


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
            pytest.param(True, False, 99, UnknownCompression(99), id="unknown_compression"),
        ],
        indirect=["exception"],
    )
    def test_meta(
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

        mock_meta = MagicMock()
        mock_protocol = MagicMock()
        mock_protocol.meta.return_value = mock_meta

        if path:
            target = tmp_path / "in.flm"
            target.write_bytes(header + body)
        else:
            target = None
        buf = io.BytesIO(header + body) if stream else None

        with patch("flama.serialize.serializer.Protocol.from_version", return_value=mock_protocol) as p_proto:
            with exception:
                out = Serializer.meta(buf, path=target)

        if not exception:
            assert out is mock_meta
            assert p_proto.call_args_list == [call(protocol_version)]
            assert len(mock_protocol.meta.call_args_list) == 1
            assert mock_protocol.meta.call_args[1]["compression"] == compression_format

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
            pytest.param(True, False, 99, UnknownCompression(99), id="unknown_compression"),
        ],
        indirect=["exception"],
    )
    def test_manifest(
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

        mock_names = ("foo.json", "bar.bin")
        mock_protocol = MagicMock()
        mock_protocol.manifest.return_value = mock_names

        if path:
            target = tmp_path / "in.flm"
            target.write_bytes(header + body)
        else:
            target = None
        buf = io.BytesIO(header + body) if stream else None

        with patch("flama.serialize.serializer.Protocol.from_version", return_value=mock_protocol) as p_proto:
            with exception:
                out = Serializer.manifest(buf, path=target)

        if not exception:
            assert out == mock_names
            assert p_proto.call_args_list == [call(protocol_version)]
            assert len(mock_protocol.manifest.call_args_list) == 1
            assert mock_protocol.manifest.call_args[1]["compression"] == compression_format

