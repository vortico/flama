import collections
import datetime
import json
import tempfile
import typing as t
import uuid

import pytest

import flama
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
