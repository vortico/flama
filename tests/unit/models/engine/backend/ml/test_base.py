import typing as t
from unittest.mock import MagicMock, call, patch

import pytest

from flama.models.engine.backend.ml.base import MLBackend
from flama.models.engine.backend.ml.sklearn import SklearnBackend


class TestCaseMLBackend:
    """Cover the abstract :class:`~flama.models.engine.backend.ml.base.MLBackend` contract."""

    def test_predict_is_abstract(self) -> None:
        with pytest.raises(TypeError, match="abstract"):
            MLBackend(object())  # type: ignore[abstract]

    def test_subclass_without_predict_cannot_be_instantiated(self) -> None:
        class _Incomplete(MLBackend): ...

        with pytest.raises(TypeError, match="abstract"):
            _Incomplete(object())  # type: ignore[abstract]

    def test_subclass_with_predict_can_be_instantiated_and_inherits_model_binding(self) -> None:
        class _Complete(MLBackend):
            def predict(self, x: t.Iterable[t.Iterable[t.Any]], /) -> t.Any:
                return list(x)

        backend = _Complete("model-handle")

        assert backend.model == "model-handle"
        assert backend.predict([[1, 2]]) == [[1, 2]]

    @pytest.mark.parametrize(
        "lib",
        [
            pytest.param("sklearn", id="sklearn"),
            pytest.param("tensorflow", id="tensorflow"),
            pytest.param("torch", id="torch"),
            pytest.param("transformers", id="transformers"),
            pytest.param("keras", id="keras"),
        ],
    )
    def test_from_model_artifact_resolves_by_framework_lib(self, lib: str) -> None:
        artifact = MagicMock(model="engine")
        artifact.meta.framework.lib = lib
        backend_cls = MagicMock(return_value=MagicMock(model="engine"))

        with patch.object(MLBackend, "_resolve", return_value=backend_cls):
            result = MLBackend.from_model_artifact(artifact)

        assert backend_cls.call_args_list == [call("engine")]
        assert result is backend_cls.return_value

    def test_from_model_artifact_raises_on_unknown_lib(self) -> None:
        artifact = MagicMock(model="engine")
        artifact.meta.framework.lib = "unknown"

        with pytest.raises(ValueError, match="Wrong backend key"):
            MLBackend.from_model_artifact(artifact)

    def test_resolve_returns_concrete_backend_for_every_known_lib(self) -> None:
        from flama.models.engine.backend.ml.pytorch import PytorchBackend
        from flama.models.engine.backend.ml.tensorflow import TensorflowBackend
        from flama.models.engine.backend.ml.transformers import TransformersBackend

        assert MLBackend._resolve("sklearn") is SklearnBackend
        assert MLBackend._resolve("torch") is PytorchBackend
        assert MLBackend._resolve("transformers") is TransformersBackend
        assert MLBackend._resolve("tensorflow") is TensorflowBackend
        assert MLBackend._resolve("keras") is TensorflowBackend

    def test_resolve_populates_registry_on_first_call(self) -> None:
        snapshot = dict(MLBackend._REGISTRY) if MLBackend._REGISTRY is not None else None
        try:
            MLBackend._REGISTRY = None

            MLBackend._resolve("sklearn")

            assert MLBackend._REGISTRY is not None
            assert set(MLBackend._REGISTRY) == {"sklearn", "torch", "tensorflow", "keras", "transformers"}
        finally:
            MLBackend._REGISTRY = snapshot

    def test_resolve_raises_value_error_for_unknown_lib(self) -> None:
        with pytest.raises(ValueError, match="Wrong backend key"):
            MLBackend._resolve("unknown")  # ty: ignore[invalid-argument-type]
