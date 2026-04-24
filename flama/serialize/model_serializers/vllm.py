import importlib.metadata
import io
import logging
import os
import pathlib
import tarfile
import typing as t

from flama import exceptions, types
from flama.serialize.model_serializers.base import BaseModelSerializer

try:
    import vllm
    from vllm.engine.arg_utils import AsyncEngineArgs
except Exception:  # pragma: no cover
    vllm = None
    AsyncEngineArgs = None

try:
    from vllm_metal.model_runner import MetalModelRunner
except Exception:  # pragma: no cover
    MetalModelRunner = None

if t.TYPE_CHECKING:
    from flama.types import JSONSchema

logger = logging.getLogger(__name__)

__all__ = ["CudaModelSerializer", "MetalModelSerializer"]


class _BaseVllmModelSerializer(BaseModelSerializer):
    """Shared logic for all vLLM-family serializers."""

    lib: t.ClassVar[types.MLLib] = "vllm"

    def dump(self, obj: t.Any, /, **kwargs) -> bytes:
        """Serialize a model directory into tar bytes, dereferencing symlinks.

        :param obj: A directory path (:class:`~pathlib.Path`, :class:`str`, or :class:`os.PathLike`).
        :return: Tar archive bytes.
        :raises NotImplementedError: If *obj* is not a directory path.
        """
        if isinstance(obj, str | os.PathLike | pathlib.Path):
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w", dereference=True) as tar:
                tar.add(
                    str(pathlib.Path(obj)),
                    arcname=".",
                    filter=lambda x: None if pathlib.PurePosixPath(x.name).name.startswith(".") else x,
                )
            return buf.getvalue()

        raise NotImplementedError("vLLM models cannot be serialized from live objects")

    def info(self, model: t.Any, /) -> "JSONSchema | None":
        try:
            return {"model_name": model.model} if hasattr(model, "model") else None
        except Exception:  # noqa
            logger.exception("Cannot collect info from model")
            return None


class CudaModelSerializer(_BaseVllmModelSerializer):
    """Serializer for standard vLLM (Linux/CUDA) engines."""

    def load(
        self,
        model: bytes,
        /,
        *,
        model_dir: pathlib.Path | None = None,
        engine_params: dict[str, t.Any] | None = None,
        **kwargs,
    ) -> t.Any:
        """Deserialize tar bytes into a :class:`vllm.AsyncLLMEngine`.

        :param model: Raw model bytes (unused when *model_dir* is provided by the protocol).
        :param model_dir: Extracted model directory (set by the protocol when the body is a tar archive).
        :param engine_params: Additional keyword arguments forwarded to :class:`vllm.engine.arg_utils.AsyncEngineArgs`.
        :return: A ready-to-use :class:`vllm.AsyncLLMEngine`.
        """
        if model_dir is None:
            raise ValueError("vLLM model requires a model directory (tar archive expected in model body)")

        if vllm is None or AsyncEngineArgs is None:  # noqa
            raise exceptions.FrameworkNotInstalled("vllm")

        return vllm.AsyncLLMEngine.from_engine_args(
            AsyncEngineArgs(model=str(model_dir), disable_log_stats=True, **(engine_params or {}))
        )

    def version(self) -> str:
        try:
            return importlib.metadata.version("vllm")
        except importlib.metadata.PackageNotFoundError:
            raise exceptions.FrameworkNotInstalled("vllm")


class MetalModelSerializer(_BaseVllmModelSerializer):
    """Serializer for vllm-metal (macOS/Apple Silicon) engines backed by MLX."""

    def load(
        self,
        model: bytes,
        /,
        *,
        model_dir: pathlib.Path | None = None,
        engine_params: dict[str, t.Any] | None = None,
        **kwargs,
    ) -> t.Any:
        """Deserialize tar bytes into a :class:`vllm_metal.model_runner.MetalModelRunner`.

        :param model: Raw model bytes (unused when *model_dir* is provided by the protocol).
        :param model_dir: Extracted model directory (set by the protocol when the body is a tar archive).
        :param engine_params: Additional keyword arguments (currently unused).
        :return: A ready-to-use :class:`~vllm_metal.model_runner.MetalModelRunner`.
        """
        if model_dir is None:
            raise ValueError("vLLM model requires a model directory (tar archive expected in model body)")

        if MetalModelRunner is None:  # noqa
            raise exceptions.FrameworkNotInstalled("vllm-metal")

        class _VllmConfig:
            class model_config:
                model = str(model_dir)

        runner = MetalModelRunner(_VllmConfig())  # type: ignore[arg-type]
        runner.load_model()
        return runner

    def version(self) -> str:
        try:
            return importlib.metadata.version("vllm-metal")
        except importlib.metadata.PackageNotFoundError:
            raise exceptions.FrameworkNotInstalled("vllm-metal")
