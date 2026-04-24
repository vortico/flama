import importlib.metadata
import io
import logging
import os
import pathlib
import tarfile
import tempfile
import typing as t

from flama import exceptions, types
from flama.serialize.model_serializers.base import BaseModelSerializer

try:
    import transformers
    import transformers.utils.logging

    transformers.utils.logging.set_verbosity_error()
    transformers.utils.logging.disable_progress_bar()
except Exception:  # pragma: no cover
    transformers = None  # ty: ignore[invalid-assignment]

if t.TYPE_CHECKING:
    from flama.types import JSONSchema

logger = logging.getLogger(__name__)

__all__ = ["ModelSerializer"]


class ModelSerializer(BaseModelSerializer):
    lib: t.ClassVar[types.MLLib] = "transformers"

    @staticmethod
    def _tar_directory(directory: pathlib.Path) -> bytes:
        """Pack a directory into an uncompressed tar archive in memory.

        :param directory: Path to the directory to archive.
        :return: Tar archive bytes.
        """
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            tar.add(
                str(directory),
                arcname=".",
                filter=lambda x: None if pathlib.PurePosixPath(x.name).name.startswith(".") else x,
            )
        return buf.getvalue()

    def dump(self, obj: t.Any, /, **kwargs) -> bytes:
        """Serialize a transformers model into tar bytes.

        :param obj: A directory path (:class:`~pathlib.Path`, :class:`str`, or :class:`os.PathLike`) containing
            pretrained model files, or a :class:`transformers.Pipeline` whose weights are saved and archived.
        :return: Tar archive bytes containing the model directory.
        """
        if transformers is None:  # noqa
            raise exceptions.FrameworkNotInstalled("transformers")

        if isinstance(obj, str | os.PathLike | pathlib.Path):
            return self._tar_directory(pathlib.Path(obj))

        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir)
            obj.save_pretrained(path)
            return self._tar_directory(path)

    def load(
        self,
        model: bytes,
        /,
        *,
        model_dir: pathlib.Path | None = None,
        task: str | None = None,
        framework: str | None = None,
        **kwargs,
    ) -> t.Any:
        """Deserialize tar bytes into a :class:`transformers.Pipeline`.

        :param model: Raw model bytes (unused when *model_dir* is provided by the protocol).
        :param model_dir: Extracted model directory (set by the protocol when the body is a tar archive).
        :param task: Pipeline task name (e.g. ``"text-generation"``).
        :param framework: DL framework to use (``"pt"`` or ``"tf"``).
        :return: A ready-to-use :class:`transformers.Pipeline`.
        """
        if transformers is None:  # noqa
            raise exceptions.FrameworkNotInstalled("transformers")

        if model_dir is None:
            raise ValueError("Transformers model requires a model directory (tar archive expected in model body)")

        return t.cast(t.Callable[..., t.Any], transformers.pipeline)(task=task, model=str(model_dir), **kwargs)

    def info(self, model: t.Any, /) -> "JSONSchema | None":
        try:
            info: dict[str, t.Any] = {}
            if hasattr(model, "model") and hasattr(model.model, "config"):
                info["config"] = model.model.config.to_dict()
            if hasattr(model, "task"):
                info["task"] = model.task
            if hasattr(model, "model") and hasattr(model.model, "name_or_path"):
                info["model_name"] = model.model.name_or_path
            return info or None
        except Exception:  # noqa
            logger.exception("Cannot collect info from model")
            return None

    def version(self) -> str:
        try:
            return importlib.metadata.version("transformers")
        except Exception:  # noqa
            raise exceptions.FrameworkNotInstalled("transformers")
