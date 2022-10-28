from io import BytesIO

import pytest

import flama


class TestCaseSerialize:
    @pytest.mark.parametrize(
        ("lib", "model", "serialized_model_class"),
        (
            pytest.param(
                flama.ModelFormat.sklearn,
                "sklearn",
                "sklearn",
                id="sklearn",
            ),
            pytest.param(
                flama.ModelFormat.tensorflow,
                "tensorflow",
                "tensorflow",
                id="tensorflow",
            ),
            pytest.param(
                flama.ModelFormat.pytorch,
                "torch",
                "torch",
                id="torch",
            ),
        ),
        indirect=["model", "serialized_model_class"],
    )
    def test_serialize_bytes(self, lib, model, serialized_model_class):
        model_binary = flama.dumps(lib, model)

        load_model = flama.loads(model_binary)

        assert load_model.lib == flama.ModelFormat(lib)
        assert isinstance(load_model.model, serialized_model_class)

    @pytest.mark.parametrize(
        ("lib", "model", "serialized_model_class"),
        (
            pytest.param(
                flama.ModelFormat.sklearn,
                "sklearn",
                "sklearn",
                id="sklearn",
            ),
            pytest.param(
                flama.ModelFormat.tensorflow,
                "tensorflow",
                "tensorflow",
                id="tensorflow",
            ),
            pytest.param(
                flama.ModelFormat.pytorch,
                "torch",
                "torch",
                id="torch",
            ),
        ),
        indirect=["model", "serialized_model_class"],
    )
    def test_serialize_stream(self, lib, model, serialized_model_class):
        model_binary = BytesIO()
        flama.dump(lib, model, model_binary)

        model_binary.seek(0)

        load_model = flama.load(model_binary)

        assert load_model.lib == flama.ModelFormat(lib)
        assert isinstance(load_model.model, serialized_model_class)
