import os
import pathlib
import tempfile
import typing as t

from flama import exceptions
from flama.modules import Module
from flama.serialize.serializer import Serializer

try:
    import transformers
except Exception:  # pragma: no cover
    transformers = None  # ty: ignore[invalid-assignment]

__all__ = ["HuggingFaceModule"]


class HuggingFaceModule(Module):
    name = "huggingface"

    @staticmethod
    def get(
        model_name: str,
        output: str | os.PathLike | pathlib.Path,
        *,
        task: str | None = None,
        **kwargs: t.Any,
    ) -> pathlib.Path:
        """Download a HuggingFace model and serialize it as .flm.

        :param model_name: HuggingFace model identifier (e.g. "google/gemma-2-2b").
        :param output: Output path for the .flm file.
        :param task: Pipeline task (auto-detected if omitted).
        :param kwargs: Additional keyword arguments passed to transformers.pipeline().
        :return: Path to the created .flm file.
        """
        if transformers is None:  # noqa
            raise exceptions.FrameworkNotInstalled("transformers")

        pipe: t.Any = transformers.pipeline(task=t.cast(t.Any, task), model=model_name, **kwargs)

        with tempfile.TemporaryDirectory() as tmpdir:
            pipe.save_pretrained(tmpdir)

            artifacts = {}
            tmpdir_path = pathlib.Path(tmpdir)
            for file_path in tmpdir_path.rglob("*"):
                if file_path.is_file():
                    artifacts[file_path.relative_to(tmpdir_path).as_posix()] = file_path

            output_path = pathlib.Path(str(output))
            Serializer.dump(
                pipe,
                path=output_path,
                artifacts=artifacts,
                extra={"task": pipe.task, "model_name": model_name},
            )

        return output_path
