import types as py_types
import typing as t
from unittest.mock import MagicMock, call, patch

import pytest

from flama.serialize.model_serializers._base import ModelSerializer


class TestCaseModelSerializer:
    @pytest.mark.parametrize(
        ["lib", "expected_module", "expected_class"],
        [
            pytest.param("sklearn", "flama.serialize.model_serializers.sklearn", "ModelSerializer", id="sklearn"),
            pytest.param("keras", "flama.serialize.model_serializers.tensorflow", "ModelSerializer", id="keras"),
            pytest.param(
                "tensorflow", "flama.serialize.model_serializers.tensorflow", "ModelSerializer", id="tensorflow"
            ),
            pytest.param("torch", "flama.serialize.model_serializers.pytorch", "ModelSerializer", id="torch"),
            pytest.param(
                "transformers", "flama.serialize.model_serializers.transformers", "ModelSerializer", id="transformers"
            ),
        ],
    )
    def test_from_lib(self, lib: str, expected_module: str, expected_class: str) -> None:
        instance = MagicMock()
        fake_module = MagicMock()
        setattr(fake_module, expected_class, MagicMock(return_value=instance))

        with patch("flama.serialize.model_serializers._base.importlib.import_module", return_value=fake_module) as im:
            result = ModelSerializer.from_lib(t.cast(t.Any, lib))

        assert result is instance
        assert im.call_args_list == [call(expected_module)]

    @pytest.mark.parametrize(
        ["model_module", "getmodule_returns", "from_lib_error_lib", "expected_lib"],
        [
            pytest.param("sklearn.pipeline", ["sklearn.pipeline"], None, "sklearn", id="direct"),
            pytest.param("torch.nn", [None, "torch.nn"], None, "torch", id="skip-none-module"),
            pytest.param(
                "tensorflow.keras",
                ["tensorflow.keras", "sklearn.pipeline"],
                "tensorflow",
                "sklearn",
                id="valueerror-then-mro",
            ),
        ],
    )
    def test_from_model(
        self,
        model_module: str,
        getmodule_returns: list[str | None],
        from_lib_error_lib: str | None,
        expected_lib: str,
    ) -> None:
        expected = MagicMock()

        class _M:
            pass

        _M.__module__ = model_module
        model = _M()

        modules_iter = iter(py_types.ModuleType(m) if m else None for m in getmodule_returns)

        def _from_lib(lib: str) -> MagicMock:
            if lib == from_lib_error_lib:
                raise ValueError("skip")
            return expected

        with (
            patch(
                "flama.serialize.model_serializers._base.inspect.getmodule",
                side_effect=lambda obj: next(modules_iter),
            ),
            patch.object(ModelSerializer, "from_lib", side_effect=_from_lib),
        ):
            result = ModelSerializer.from_model(model)

        assert result is expected
