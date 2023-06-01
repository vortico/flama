import datetime
import json
import tempfile
import uuid

import pytest

import flama
from flama.serialize.data_structures import Compression
from flama.serialize.types import Framework


class TestCaseSerialize:
    @pytest.fixture(scope="function")
    def artifact(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as tmp:
            json.dump({"foo": "bar"}, tmp)
            yield tmp.name

    @pytest.mark.parametrize(
        ("lib", "model", "serialized_model_class"),
        (
            pytest.param(Framework.sklearn, "sklearn", "sklearn", id="sklearn"),
            pytest.param(Framework.sklearn, "sklearn-pipeline", "sklearn-pipeline", id="sklearn-pipeline"),
            pytest.param(Framework.tensorflow, "tensorflow", "tensorflow", id="tensorflow"),
            pytest.param(Framework.torch, "torch", "torch", id="torch"),
            # TODO: Add keras
        ),
        indirect=["model", "serialized_model_class"],
    )
    def test_serialize(self, lib, artifact, model, serialized_model_class):
        id_ = uuid.uuid4()
        timestamp = datetime.datetime.utcnow()
        params = {"param": "1"}
        metrics = {"metric": "1"}
        extra = {"foo": "bar"}

        with tempfile.NamedTemporaryFile(suffix=".flm") as tmp:
            flama.dump(
                model,
                tmp.name,
                compression=Compression.fast,
                model_id=id_,
                timestamp=timestamp,
                params=params,
                metrics=metrics,
                extra=extra,
                artifacts={"foo.json": artifact},
            )

            load_model = flama.load(tmp.name)

        assert isinstance(load_model.model, serialized_model_class)
        assert load_model.meta.id == id_
        assert load_model.meta.timestamp == timestamp
        assert load_model.meta.framework.lib == lib
        assert load_model.meta.model.params == params
        assert load_model.meta.model.metrics == metrics
        assert load_model.meta.extra == extra
        assert "foo.json" in load_model.artifacts
