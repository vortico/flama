import types as py_types
import typing as t
from unittest.mock import MagicMock, call, patch

import pytest

from flama.serialize.model_serializers.base import ModelSerializer


class TestCaseModelSerializerFromLib:
    @pytest.mark.parametrize(
        ["lib", "expected_submodule"],
        [
            pytest.param("sklearn", "sklearn", id="sklearn"),
            pytest.param("keras", "tensorflow", id="keras_maps_tensorflow"),
            pytest.param("tensorflow", "tensorflow", id="tensorflow"),
            pytest.param("torch", "pytorch", id="torch_maps_pytorch"),
            pytest.param("transformers", "transformers", id="transformers"),
        ],
    )
    def test_from_lib_success(self, lib: str, expected_submodule: str) -> None:
        instance = MagicMock()
        fake_module = MagicMock()
        fake_module.ModelSerializer = MagicMock(return_value=instance)
        expected_name = f"flama.serialize.model_serializers.{expected_submodule}"

        with patch("flama.serialize.model_serializers.base.importlib.import_module", return_value=fake_module) as im:
            result = ModelSerializer.from_lib(t.cast(t.Any, lib))

        assert result is instance
        assert im.call_args_list == [call(expected_name)]


class TestCaseModelSerializerFromModel:
    def test_from_model_first_object_succeeds(self) -> None:
        mod = py_types.ModuleType("sklearn.pipeline")
        expected = MagicMock()

        class _M:
            __module__ = "sklearn.pipeline"

        model = _M()

        with (
            patch("flama.serialize.model_serializers.base.inspect.getmodule", return_value=mod),
            patch.object(ModelSerializer, "from_lib", return_value=expected) as flib,
        ):
            out = ModelSerializer.from_model(model)

        assert out is expected
        assert flib.call_args_list == [call("sklearn")]

    def test_from_model_skips_none_module_then_succeeds(self) -> None:
        mod = py_types.ModuleType("torch.nn")

        class _M:
            __module__ = "torch.nn"

        model = _M()
        expected = MagicMock()
        modules: list[py_types.ModuleType | None] = [None, mod]

        def _getmodule(obj: t.Any) -> py_types.ModuleType | None:
            return modules.pop(0)

        with (
            patch("flama.serialize.model_serializers.base.inspect.getmodule", side_effect=_getmodule),
            patch.object(ModelSerializer, "from_lib", return_value=expected) as flib,
        ):
            out = ModelSerializer.from_model(model)

        assert out is expected
        assert flib.call_args_list == [call("torch")]

    def test_from_model_valueerror_then_mro_succeeds(self) -> None:
        mod_tf = py_types.ModuleType("tensorflow.keras")
        mod_sk = py_types.ModuleType("sklearn.pipeline")
        expected = MagicMock()

        class _M:
            __module__ = "tensorflow.keras"

        model = _M()

        def _getmodule(obj: t.Any) -> py_types.ModuleType:
            if obj is model:
                return mod_tf
            return mod_sk

        def _from_lib(lib: str) -> MagicMock:
            if lib == "tensorflow":
                raise ValueError("skip")
            return expected

        with (
            patch("flama.serialize.model_serializers.base.inspect.getmodule", side_effect=_getmodule),
            patch.object(ModelSerializer, "from_lib", side_effect=_from_lib),
        ):
            out = ModelSerializer.from_model(model)

        assert out is expected
