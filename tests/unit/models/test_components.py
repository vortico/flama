from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from flama.models._base import MLModel
from flama.models.components import ModelComponent, ModelComponentBuilder
from flama.models.engine.backend.ml.pytorch import PytorchBackend
from flama.models.engine.backend.ml.sklearn import SklearnBackend
from flama.models.engine.backend.ml.tensorflow import TensorflowBackend
from flama.models.engine.backend.ml.transformers import TransformersBackend


class TestCaseModelComponent:
    @pytest.fixture(scope="function")
    def stub_model(self) -> MagicMock:
        model = MagicMock()
        model.startup = AsyncMock()
        return model

    def test_resolve(self, stub_model: MagicMock) -> None:
        component = ModelComponent(stub_model)

        assert component.resolve() is stub_model

    def test_model_property(self, stub_model: MagicMock) -> None:
        component = ModelComponent(stub_model)

        assert component.model is stub_model

    def test_get_model_type(self, stub_model: MagicMock) -> None:
        component = ModelComponent(stub_model)

        assert component.get_model_type() is type(stub_model)

    def test_load_delegates_to_model(self, stub_model: MagicMock) -> None:
        component = ModelComponent(stub_model)

        component.load()

        assert stub_model.load.call_args_list == [call()]

    async def test_startup_delegates_to_model(self, stub_model: MagicMock) -> None:
        component = ModelComponent(stub_model)

        await component.startup()

        assert stub_model.startup.await_args_list == [call()]


class TestCaseModelComponentBuilder:
    @pytest.mark.parametrize(
        ["model_path", "model_cls", "backend_cls", "serialized_model_class"],
        [
            pytest.param("sklearn", MLModel, SklearnBackend, "sklearn", id="sklearn"),
            pytest.param("sklearn-pipeline", MLModel, SklearnBackend, "sklearn-pipeline", id="sklearn_pipeline"),
            pytest.param("tensorflow", MLModel, TensorflowBackend, "tensorflow", id="tensorflow"),
            pytest.param("torch", MLModel, PytorchBackend, "torch", id="torch"),
            pytest.param("transformers", MLModel, TransformersBackend, "transformers", id="transformers"),
        ],
        indirect=["model_path", "serialized_model_class"],
    )
    def test_build_supported_libs(self, model_path, model_cls, backend_cls, serialized_model_class) -> None:
        component = ModelComponentBuilder.build(model_path, autoload=True)

        assert isinstance(component.model, model_cls)
        assert isinstance(component.model.backend, backend_cls)
        assert isinstance(component.model.model, serialized_model_class)

    @pytest.mark.parametrize(
        ["family", "autoload", "decoder", "params", "exception", "expected_autoload"],
        [
            pytest.param("ml", False, None, None, None, False, id="propagates_autoload_off"),
            pytest.param("ml", True, None, None, None, True, id="propagates_autoload_on"),
            pytest.param("llm", True, None, None, None, True, id="builds_llm"),
            pytest.param(
                "ml",
                False,
                MagicMock(),
                None,
                (ValueError, "'decoder' is not supported by ML artifacts"),
                None,
                id="rejects_decoder_for_ml_artifact",
            ),
            pytest.param(
                "ml",
                False,
                None,
                {"temperature": 0.7},
                (ValueError, "'params' is not supported by ML artifacts"),
                None,
                id="rejects_params_for_ml_artifact",
            ),
        ],
        indirect=["exception"],
    )
    def test_build(
        self,
        family: str,
        autoload: bool,
        decoder,
        params,
        exception,
        expected_autoload: bool | None,
    ) -> None:
        meta = MagicMock()
        meta.framework.family = family
        meta.framework.lib = "sklearn" if family == "ml" else "transformers"
        kwargs = {"autoload": autoload}
        if decoder is not None:
            kwargs["decoder"] = decoder
        if params is not None:
            kwargs["params"] = params

        with exception, patch("flama.models.components.Serializer.meta", return_value=meta):
            component = ModelComponentBuilder.build("/fake.flm", **kwargs)

            if expected_autoload is not None:
                assert component.model._autoload is expected_autoload

    def test_build_configures_llm_with_params(self) -> None:
        params = {"temperature": 0.7, "max_tokens": 200}
        meta = MagicMock()
        meta.framework.family = "llm"
        meta.framework.lib = "transformers"

        with patch("flama.models.components.Serializer.meta", return_value=meta):
            component = ModelComponentBuilder.build("/fake.flm", autoload=False, params=params)

        assert component.model.params == params
