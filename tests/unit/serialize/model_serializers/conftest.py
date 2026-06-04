"""Shared spec table and helpers for per-framework model-serializer tests."""

import dataclasses
import pathlib
import typing as t
from contextlib import ExitStack
from unittest.mock import MagicMock, call, patch

from flama.serialize.model_serializers.base import BaseModelSerializer
from flama.serialize.model_serializers.pytorch import ModelSerializer as TorchModelSerializer
from flama.serialize.model_serializers.sklearn import ModelSerializer as SklearnModelSerializer
from flama.serialize.model_serializers.tensorflow import ModelSerializer as TensorflowModelSerializer
from flama.serialize.model_serializers.transformers import ModelSerializer as TransformersModelSerializer


@dataclasses.dataclass(frozen=True)
class Spec:
    """Per-framework table of test patch targets and the wire-level source shape its loader expects.

    :attr:`source_kind` mirrors the v2 :data:`~flama.types.SerializationModelKind` byte:
    ``"binary"`` serializers consume raw ``bytes`` and reject paths; ``"bundle"`` serializers
    consume :class:`pathlib.Path` directories and reject bytes.
    """

    serializer_cls: type[BaseModelSerializer]
    lib: str
    version_patch: str
    version_key: str
    framework_patch: str | None
    source_kind: t.Literal["binary", "bundle"]


SPECS: dict[str, Spec] = {
    "sklearn": Spec(
        serializer_cls=SklearnModelSerializer,
        lib="sklearn",
        version_patch="flama.serialize.model_serializers.sklearn.importlib.metadata.version",
        version_key="scikit-learn",
        framework_patch=None,
        source_kind="binary",
    ),
    "torch": Spec(
        serializer_cls=TorchModelSerializer,
        lib="torch",
        version_patch="flama.serialize.model_serializers.pytorch.importlib.metadata.version",
        version_key="torch",
        framework_patch="flama.serialize.model_serializers.pytorch.torch",
        source_kind="binary",
    ),
    "tensorflow": Spec(
        serializer_cls=TensorflowModelSerializer,
        lib="tensorflow",
        version_patch="flama.serialize.model_serializers.tensorflow.importlib.metadata.version",
        version_key="tensorflow",
        framework_patch="flama.serialize.model_serializers.tensorflow.keras_models",
        source_kind="binary",
    ),
    "transformers": Spec(
        serializer_cls=TransformersModelSerializer,
        lib="transformers",
        version_patch="flama.serialize.model_serializers.transformers.importlib.metadata.version",
        version_key="transformers",
        framework_patch="flama.serialize.model_serializers.transformers.transformers",
        source_kind="bundle",
    ),
}


LOAD_PATCHES: dict[str, dict[str, str]] = {
    "sklearn": {"pickle_loads": "flama.serialize.model_serializers.sklearn.pickle.loads"},
    "torch": {"torch": "flama.serialize.model_serializers.pytorch.torch"},
    "tensorflow": {"keras_models": "flama.serialize.model_serializers.tensorflow.keras_models"},
    "transformers": {"transformers": "flama.serialize.model_serializers.transformers.transformers"},
}


LOAD_EXTRA_KWARGS: dict[str, dict[str, t.Any]] = {
    "transformers": {"task": "text-generation"},
}


def dump_setup(
    framework: str, scenario: str, stack: ExitStack, tmp_path: pathlib.Path
) -> tuple[t.Any, dict[str, t.Any], MagicMock]:
    """Build (obj, kwargs, mocks) for a per-framework dump test scenario."""
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


def dump_assert(framework: str, scenario: str, mocks: MagicMock, obj: t.Any) -> None:
    if framework == "sklearn":
        assert mocks.pickle_dumps.call_args_list == [call(obj)]
    elif framework == "torch":
        assert mocks.torch.export.export.called
        assert mocks.torch.export.save.called
    elif framework == "tensorflow":
        assert mocks.keras_models.save_model.called
    elif framework == "transformers":
        assert mocks.tar.called
        if scenario == "pipeline":
            assert obj.save_pretrained.call_count == 1


def load_setup(
    framework: str, scenario: str, stack: ExitStack
) -> tuple[bytes | pathlib.Path, dict[str, t.Any], MagicMock]:
    """Build (source, kwargs, mocks) for a per-framework load test scenario.

    Picks the wire-level source shape from :class:`Spec.source_kind`: binary serializers get a
    bytes payload, bundle serializers get a :class:`pathlib.Path`. The ``"wrong-source"`` scenario
    flips the shape to verify the runtime ``isinstance`` rejection in each concrete serializer.
    """
    spec = SPECS[framework]
    mocks = MagicMock()
    kwargs: dict[str, t.Any] = {}

    if scenario == "not-installed":
        assert spec.framework_patch is not None
        stack.enter_context(patch(spec.framework_patch, None))
    else:
        for name, target in LOAD_PATCHES.get(framework, {}).items():
            setattr(mocks, name, stack.enter_context(patch(target)))

    if scenario == "extra":
        kwargs.update(LOAD_EXTRA_KWARGS.get(framework, {}))

    source: bytes | pathlib.Path
    if scenario == "wrong-source":
        source = pathlib.Path("/tmp/model") if spec.source_kind == "binary" else b""
    else:
        source = pathlib.Path("/tmp/model") if spec.source_kind == "bundle" else b""

    return source, kwargs, mocks


def load_assert(
    framework: str, mocks: MagicMock, kwargs: dict[str, t.Any], source: bytes | pathlib.Path, result: t.Any
) -> None:
    if framework == "sklearn":
        assert result is mocks.pickle_loads.return_value
    elif framework == "torch":
        assert result is mocks.torch.export.load.return_value.module.return_value
    elif framework == "tensorflow":
        assert result is mocks.keras_models.load_model.return_value
    elif framework == "transformers":
        assert isinstance(source, pathlib.Path)
        assert mocks.transformers.pipeline.call_args == call(task=kwargs.get("task"), model=str(source))
        assert result is mocks.transformers.pipeline.return_value


def info_model(framework: str, model_attrs: dict[str, t.Any]) -> t.Any:
    if model_attrs.get("_raise"):
        return _raising_model(framework)
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
    return _transformers_model(model_attrs)


def _raising_model(framework: str) -> t.Any:
    m: t.Any = MagicMock()
    if framework == "sklearn":
        m.get_params.side_effect = RuntimeError("boom")
    elif framework == "transformers":
        m.model.config.to_dict.side_effect = RuntimeError("boom")
    else:
        type(m).model = property(lambda self: (_ for _ in ()).throw(RuntimeError("boom")))
    return m


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
