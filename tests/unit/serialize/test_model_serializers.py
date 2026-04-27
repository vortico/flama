import dataclasses
import importlib.metadata
import pathlib
import sys
import types as py_types
import typing as t
from contextlib import ExitStack
from unittest.mock import MagicMock, call, patch

import pytest

from flama import exceptions
from flama.serialize.model_serializers.base import BaseModelSerializer, ModelSerializer
from flama.serialize.model_serializers.pytorch import ModelSerializer as TorchModelSerializer
from flama.serialize.model_serializers.sklearn import ModelSerializer as SklearnModelSerializer
from flama.serialize.model_serializers.tensorflow import ModelSerializer as TensorflowModelSerializer
from flama.serialize.model_serializers.transformers import ModelSerializer as TransformersModelSerializer
from flama.serialize.model_serializers.vllm import CudaModelSerializer, MetalModelSerializer


@dataclasses.dataclass(frozen=True)
class _Spec:
    serializer_cls: type[BaseModelSerializer]
    lib: str
    version_patch: str
    version_key: str
    framework_patch: str | None
    needs_model_dir: bool


_SPECS: dict[str, _Spec] = {
    "sklearn": _Spec(
        serializer_cls=SklearnModelSerializer,
        lib="sklearn",
        version_patch="flama.serialize.model_serializers.sklearn.importlib.metadata.version",
        version_key="scikit-learn",
        framework_patch=None,
        needs_model_dir=False,
    ),
    "torch": _Spec(
        serializer_cls=TorchModelSerializer,
        lib="torch",
        version_patch="flama.serialize.model_serializers.pytorch.importlib.metadata.version",
        version_key="torch",
        framework_patch="flama.serialize.model_serializers.pytorch.torch",
        needs_model_dir=False,
    ),
    "tensorflow": _Spec(
        serializer_cls=TensorflowModelSerializer,
        lib="tensorflow",
        version_patch="flama.serialize.model_serializers.tensorflow.importlib.metadata.version",
        version_key="tensorflow",
        framework_patch="flama.serialize.model_serializers.tensorflow.keras_models",
        needs_model_dir=False,
    ),
    "transformers": _Spec(
        serializer_cls=TransformersModelSerializer,
        lib="transformers",
        version_patch="flama.serialize.model_serializers.transformers.importlib.metadata.version",
        version_key="transformers",
        framework_patch="flama.serialize.model_serializers.transformers.transformers",
        needs_model_dir=True,
    ),
    "vllm-cuda": _Spec(
        serializer_cls=CudaModelSerializer,
        lib="vllm",
        version_patch="flama.serialize.model_serializers.vllm.importlib.metadata.version",
        version_key="vllm",
        framework_patch="flama.serialize.model_serializers.vllm.vllm",
        needs_model_dir=True,
    ),
    "vllm-metal": _Spec(
        serializer_cls=MetalModelSerializer,
        lib="vllm",
        version_patch="flama.serialize.model_serializers.vllm.importlib.metadata.version",
        version_key="vllm-metal",
        framework_patch="flama.serialize.model_serializers.vllm.MetalModelRunner",
        needs_model_dir=True,
    ),
}


_FRAMEWORKS = list(_SPECS)


_LOAD_PATCHES: dict[str, dict[str, str]] = {
    "sklearn": {"pickle_loads": "flama.serialize.model_serializers.sklearn.pickle.loads"},
    "torch": {"torch": "flama.serialize.model_serializers.pytorch.torch"},
    "tensorflow": {"keras_models": "flama.serialize.model_serializers.tensorflow.keras_models"},
    "transformers": {"transformers": "flama.serialize.model_serializers.transformers.transformers"},
    "vllm-cuda": {
        "vllm": "flama.serialize.model_serializers.vllm.vllm",
        "engine_args": "flama.serialize.model_serializers.vllm.AsyncEngineArgs",
    },
    "vllm-metal": {"runner_cls": "flama.serialize.model_serializers.vllm.MetalModelRunner"},
}


_LOAD_EXTRA_KWARGS: dict[str, dict[str, t.Any]] = {
    "transformers": {"task": "text-generation"},
    "vllm-cuda": {"engine_params": {"max_model_len": 4096}},
}


class TestCaseBaseModelSerializer:
    @pytest.mark.parametrize("framework", [pytest.param(k, id=k) for k in _FRAMEWORKS])
    def test_lib(self, framework: str) -> None:
        spec = _SPECS[framework]
        assert spec.serializer_cls.lib == spec.lib

    @staticmethod
    def _dump_setup(
        framework: str, scenario: str, stack: ExitStack, tmp_path: pathlib.Path
    ) -> tuple[t.Any, dict[str, t.Any], MagicMock]:
        mocks = MagicMock()
        if framework == "sklearn":
            mocks.pickle_dumps = stack.enter_context(
                patch("flama.serialize.model_serializers.sklearn.pickle.dumps", return_value=b"raw")
            )
            return MagicMock(), {}, mocks
        if framework == "torch":
            mocks.torch = stack.enter_context(patch("flama.serialize.model_serializers.pytorch.torch"))
            return MagicMock(), {"example_inputs": (MagicMock(),)}, mocks
        if framework == "tensorflow":
            mocks.keras_models = stack.enter_context(patch("flama.serialize.model_serializers.tensorflow.keras_models"))
            return MagicMock(), {}, mocks
        if framework == "transformers":
            stack.enter_context(patch("flama.serialize.model_serializers.transformers.transformers"))
            mocks.tar = stack.enter_context(patch("flama.serialize.model_serializers.transformers.tar"))
            if scenario == "path":
                return tmp_path, {}, mocks
            obj: t.Any = MagicMock(spec=["save_pretrained"])
            return obj, {}, mocks
        return MagicMock(), {}, mocks

    @staticmethod
    def _dump_assert(framework: str, scenario: str, mocks: MagicMock, obj: t.Any) -> None:
        if framework == "sklearn":
            mocks.pickle_dumps.assert_called_once_with(obj)
        elif framework == "torch":
            assert mocks.torch.export.export.called
            assert mocks.torch.export.save.called
        elif framework == "tensorflow":
            assert mocks.keras_models.save_model.called
        elif framework == "transformers":
            assert mocks.tar.called
            if scenario == "pipeline":
                obj.save_pretrained.assert_called_once()

    @pytest.mark.parametrize(
        ["framework", "scenario", "exception"],
        [
            pytest.param("sklearn", "default", None, id="sklearn"),
            pytest.param("torch", "default", None, id="torch"),
            pytest.param("tensorflow", "default", None, id="tensorflow"),
            pytest.param("transformers", "path", None, id="transformers-path"),
            pytest.param("transformers", "pipeline", None, id="transformers-pipeline"),
            pytest.param("vllm-cuda", "default", (NotImplementedError, "cannot be serialised"), id="vllm-cuda"),
            pytest.param("vllm-metal", "default", (NotImplementedError, "cannot be serialised"), id="vllm-metal"),
        ],
        indirect=["exception"],
    )
    def test_dump(self, framework: str, scenario: str, exception, tmp_path: pathlib.Path) -> None:
        spec = _SPECS[framework]
        with ExitStack() as stack:
            obj, kwargs, mocks = self._dump_setup(framework, scenario, stack, tmp_path)
            with exception:
                result = spec.serializer_cls().dump(obj, **kwargs)

            if not exception:
                assert isinstance(result, bytes)
                self._dump_assert(framework, scenario, mocks, obj)

    @staticmethod
    def _load_setup(framework: str, scenario: str, stack: ExitStack) -> tuple[bytes, dict[str, t.Any], MagicMock]:
        spec = _SPECS[framework]
        mocks = MagicMock()
        kwargs: dict[str, t.Any] = {}

        if scenario == "not-installed":
            assert spec.framework_patch is not None
            stack.enter_context(patch(spec.framework_patch, None))
        elif scenario != "no-model-dir":
            for name, target in _LOAD_PATCHES.get(framework, {}).items():
                setattr(mocks, name, stack.enter_context(patch(target)))

        if scenario != "no-model-dir" and spec.needs_model_dir:
            kwargs["model_dir"] = pathlib.Path("/tmp/model")
        if scenario == "extra":
            kwargs.update(_LOAD_EXTRA_KWARGS.get(framework, {}))

        return b"", kwargs, mocks

    @staticmethod
    def _load_assert(framework: str, mocks: MagicMock, kwargs: dict[str, t.Any], result: t.Any) -> None:
        if framework == "sklearn":
            assert result is mocks.pickle_loads.return_value
        elif framework == "torch":
            assert result is mocks.torch.export.load.return_value.module.return_value
        elif framework == "tensorflow":
            assert result is mocks.keras_models.load_model.return_value
        elif framework == "transformers":
            assert mocks.transformers.pipeline.call_args == call(
                task=kwargs.get("task"), model=str(kwargs["model_dir"])
            )
            assert result is mocks.transformers.pipeline.return_value
        elif framework == "vllm-cuda":
            engine_params = kwargs.get("engine_params", {})
            assert mocks.engine_args.call_args == call(
                model=str(kwargs["model_dir"]), disable_log_stats=True, **engine_params
            )
            assert result is mocks.vllm.AsyncLLMEngine.from_engine_args.return_value
        elif framework == "vllm-metal":
            assert mocks.runner_cls.call_count == 1
            config = mocks.runner_cls.call_args[0][0]
            assert config.model_config.model == str(kwargs["model_dir"])
            mocks.runner_cls.return_value.load_model.assert_called_once()
            assert result is mocks.runner_cls.return_value

    @pytest.mark.parametrize(
        ["framework", "scenario", "exception"],
        [
            pytest.param("sklearn", "default", None, id="sklearn"),
            pytest.param("torch", "default", None, id="torch"),
            pytest.param("torch", "not-installed", exceptions.FrameworkNotInstalled, id="torch-not-installed"),
            pytest.param("tensorflow", "default", None, id="tensorflow"),
            pytest.param(
                "tensorflow", "not-installed", exceptions.FrameworkNotInstalled, id="tensorflow-not-installed"
            ),
            pytest.param("transformers", "default", None, id="transformers"),
            pytest.param("transformers", "extra", None, id="transformers-extra"),
            pytest.param(
                "transformers", "no-model-dir", (ValueError, "model directory"), id="transformers-no-model-dir"
            ),
            pytest.param(
                "transformers", "not-installed", exceptions.FrameworkNotInstalled, id="transformers-not-installed"
            ),
            pytest.param("vllm-cuda", "default", None, id="vllm-cuda"),
            pytest.param("vllm-cuda", "extra", None, id="vllm-cuda-extra"),
            pytest.param("vllm-cuda", "no-model-dir", (ValueError, "model directory"), id="vllm-cuda-no-model-dir"),
            pytest.param("vllm-cuda", "not-installed", exceptions.FrameworkNotInstalled, id="vllm-cuda-not-installed"),
            pytest.param("vllm-metal", "default", None, id="vllm-metal"),
            pytest.param("vllm-metal", "no-model-dir", (ValueError, "model directory"), id="vllm-metal-no-model-dir"),
            pytest.param(
                "vllm-metal", "not-installed", exceptions.FrameworkNotInstalled, id="vllm-metal-not-installed"
            ),
        ],
        indirect=["exception"],
    )
    def test_load(self, framework: str, scenario: str, exception) -> None:
        spec = _SPECS[framework]
        with ExitStack() as stack:
            data, kwargs, mocks = self._load_setup(framework, scenario, stack)
            with exception:
                result = spec.serializer_cls().load(data, **kwargs)

            if not exception:
                self._load_assert(framework, mocks, kwargs, result)

    @staticmethod
    def _info_model(framework: str, model_attrs: dict[str, t.Any]) -> t.Any:
        if model_attrs.get("_raise"):
            return TestCaseBaseModelSerializer._raising_model(framework)
        if framework == "sklearn":
            m: t.Any = MagicMock()
            m.get_params.return_value = model_attrs.get("params", {})
            return m
        if framework == "torch":
            m = MagicMock()
            m.modules.return_value = model_attrs.get("modules", [])
            m.named_parameters.return_value = list(model_attrs.get("parameters", {}).items())
            m.state_dict.return_value = model_attrs.get("state", {})
            return m
        if framework == "tensorflow":
            m = MagicMock()
            m.to_json.return_value = model_attrs.get("to_json", "{}")
            return m
        if framework == "transformers":
            return TestCaseBaseModelSerializer._transformers_model(model_attrs)
        return TestCaseBaseModelSerializer._vllm_model(model_attrs)

    @staticmethod
    def _raising_model(framework: str) -> t.Any:
        m: t.Any = MagicMock()
        if framework == "sklearn":
            m.get_params.side_effect = RuntimeError("boom")
        elif framework == "transformers":
            m.model.config.to_dict.side_effect = RuntimeError("boom")
        else:
            type(m).model = property(lambda self: (_ for _ in ()).throw(RuntimeError("boom")))
        return m

    @staticmethod
    def _transformers_model(model_attrs: dict[str, t.Any]) -> t.Any:
        m: t.Any = MagicMock(spec=[])
        if "task" in model_attrs:
            m.task = model_attrs["task"]
        if "config" in model_attrs or "name" in model_attrs:
            m.model = MagicMock(spec=[])
        if "config" in model_attrs:
            m.model.config = MagicMock()
            m.model.config.to_dict.return_value = model_attrs["config"]
        if "name" in model_attrs:
            m.model.name_or_path = model_attrs["name"]
        return m

    @staticmethod
    def _vllm_model(model_attrs: dict[str, t.Any]) -> t.Any:
        if "model" in model_attrs:
            m: t.Any = MagicMock()
            m.model = model_attrs["model"]
            return m
        return MagicMock(spec=[])

    @pytest.mark.parametrize(
        ["framework", "model_attrs", "expected"],
        [
            pytest.param(
                "sklearn",
                {"params": {"alpha": 0.5, "fit_intercept": True}},
                {"alpha": 0.5, "fit_intercept": True},
                id="sklearn",
            ),
            pytest.param("sklearn", {"_raise": True}, None, id="sklearn-exception"),
            pytest.param(
                "torch",
                {"modules": [object()], "parameters": {}, "state": {}},
                {"modules", "parameters", "state"},
                id="torch",
            ),
            pytest.param("tensorflow", {"to_json": '{"name": "m"}'}, {"name": "m"}, id="tensorflow"),
            pytest.param(
                "transformers",
                {"task": "text-generation", "config": {"hidden_size": 768}, "name": "google/gemma-2-2b"},
                {"config", "task", "model_name"},
                id="transformers-full",
            ),
            pytest.param("transformers", {"config": {"hidden_size": 768}}, {"config"}, id="transformers-config-only"),
            pytest.param("transformers", {"task": "text-generation"}, {"task"}, id="transformers-task-only"),
            pytest.param("transformers", {}, None, id="transformers-empty"),
            pytest.param("transformers", {"_raise": True}, None, id="transformers-exception"),
            pytest.param(
                "vllm-cuda",
                {"model": "google/gemma-2-2b"},
                {"model_name": "google/gemma-2-2b"},
                id="vllm-cuda-with-model",
            ),
            pytest.param("vllm-cuda", {}, None, id="vllm-cuda-no-model"),
            pytest.param("vllm-cuda", {"_raise": True}, None, id="vllm-cuda-exception"),
            pytest.param(
                "vllm-metal",
                {"model": "google/gemma-2-2b"},
                {"model_name": "google/gemma-2-2b"},
                id="vllm-metal-with-model",
            ),
            pytest.param("vllm-metal", {}, None, id="vllm-metal-no-model"),
            pytest.param("vllm-metal", {"_raise": True}, None, id="vllm-metal-exception"),
        ],
    )
    def test_info(self, framework: str, model_attrs: dict[str, t.Any], expected: t.Any) -> None:
        spec = _SPECS[framework]
        model = self._info_model(framework, model_attrs)

        result = spec.serializer_cls().info(model)

        if expected is None:
            assert result is None
        elif isinstance(expected, set):
            assert set(result.keys()) == expected
        else:
            assert result == expected

    @pytest.mark.parametrize(
        ["framework", "scenario", "exception"],
        [
            *(pytest.param(k, "ok", None, id=k) for k in _FRAMEWORKS),
            *(
                pytest.param(k, "not-installed", exceptions.FrameworkNotInstalled, id=f"{k}-not-installed")
                for k in _FRAMEWORKS
            ),
        ],
        indirect=["exception"],
    )
    def test_version(self, framework: str, scenario: str, exception) -> None:
        spec = _SPECS[framework]
        version_value = "1.2.3"
        side_effect = importlib.metadata.PackageNotFoundError() if scenario == "not-installed" else None
        return_value = None if scenario == "not-installed" else version_value

        with patch(spec.version_patch, return_value=return_value, side_effect=side_effect) as mock_ver:
            with exception:
                result = spec.serializer_cls().version()

        if not exception:
            assert result == version_value
            mock_ver.assert_called_with(spec.version_key)


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
            pytest.param(
                "vllm",
                "flama.serialize.model_serializers.vllm",
                "MetalModelSerializer" if sys.platform == "darwin" else "CudaModelSerializer",
                id="vllm",
            ),
        ],
    )
    def test_from_lib(self, lib: str, expected_module: str, expected_class: str) -> None:
        instance = MagicMock()
        fake_module = MagicMock()
        setattr(fake_module, expected_class, MagicMock(return_value=instance))

        with patch("flama.serialize.model_serializers.base.importlib.import_module", return_value=fake_module) as im:
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
                "flama.serialize.model_serializers.base.inspect.getmodule",
                side_effect=lambda obj: next(modules_iter),
            ),
            patch.object(ModelSerializer, "from_lib", side_effect=_from_lib),
        ):
            result = ModelSerializer.from_model(model)

        assert result is expected
