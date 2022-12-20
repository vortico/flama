import datetime
import uuid
from io import BytesIO

import pytest

import flama
from flama.serialize.types import Framework


class TestCaseSerialize:
    @pytest.mark.parametrize(
        ("lib", "model", "serialized_model_class"),
        (
            pytest.param(Framework.sklearn, "sklearn", "sklearn", id="sklearn"),
            pytest.param(Framework.tensorflow, "tensorflow", "tensorflow", id="tensorflow"),
            pytest.param(Framework.torch, "torch", "torch", id="torch"),
            # TODO: Add keras
        ),
        indirect=["model", "serialized_model_class"],
    )
    def test_serialize_bytes(self, lib, model, serialized_model_class):
        id_ = uuid.uuid4()
        timestamp = datetime.datetime.utcnow()
        params = {"param": "1"}
        metrics = {"metric": "1"}
        extra = {"foo": "bar"}

        model_binary = flama.dumps(
            model, model_id=id_, timestamp=timestamp, params=params, metrics=metrics, extra=extra
        )

        load_model = flama.loads(model_binary)

        assert isinstance(load_model.model, serialized_model_class)
        assert load_model.meta.id == id_
        assert load_model.meta.timestamp == timestamp
        assert load_model.meta.framework.lib == lib
        assert load_model.meta.model.params == params
        assert load_model.meta.model.metrics == metrics
        assert load_model.meta.extra == extra

    @pytest.mark.parametrize(
        ("lib", "model", "serialized_model_class"),
        (
            pytest.param(Framework.sklearn, "sklearn", "sklearn", id="sklearn"),
            pytest.param(Framework.tensorflow, "tensorflow", "tensorflow", id="tensorflow"),
            pytest.param(Framework.torch, "torch", "torch", id="torch"),
            # TODO: Add keras
        ),
        indirect=["model", "serialized_model_class"],
    )
    def test_serialize_stream(self, lib, model, serialized_model_class):
        id_ = uuid.uuid4()
        timestamp = datetime.datetime.utcnow()
        params = {"param": "1"}
        metrics = {"metric": "1"}
        extra = {"foo": "bar"}

        model_binary = BytesIO()
        flama.dump(model, model_binary, model_id=id_, timestamp=timestamp, params=params, metrics=metrics, extra=extra)

        model_binary.seek(0)

        load_model = flama.load(model_binary)

        assert isinstance(load_model.model, serialized_model_class)
        assert load_model.meta.id == id_
        assert load_model.meta.timestamp == timestamp
        assert load_model.meta.framework.lib == lib
        assert load_model.meta.model.params == params
        assert load_model.meta.model.metrics == metrics
        assert load_model.meta.extra == extra
