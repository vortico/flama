import os
import pathlib
import typing as t

from flama import exceptions
from flama.modules import Module
from flama.serialize.serializer import Serializer

try:
    import huggingface_hub
    import huggingface_hub.utils

    huggingface_hub.utils.disable_progress_bars()
except Exception:  # pragma: no cover
    huggingface_hub = None  # ty: ignore[invalid-assignment]

__all__ = ["HuggingFaceModule"]


class HuggingFaceModule(Module):
    name = "huggingface"

    @staticmethod
    def get(
        model_name: str,
        output: str | os.PathLike | pathlib.Path,
        *,
        task: str | None = None,
        engine: t.Literal["transformers", "vllm"] = "transformers",
        **kwargs: t.Any,
    ) -> pathlib.Path:
        """Download a HuggingFace model and serialize it as .flm.

        Uses huggingface_hub to download the model repository snapshot directly to disk, then packages it into Flama's
        .flm format with the appropriate engine tag.

        :param model_name: HuggingFace model identifier (e.g. "google/gemma-2-2b").
        :param output: Output path for the .flm file.
        :param task: Pipeline task override (auto-detected from model card if omitted).
        :param engine: Engine to use for serving ("transformers" or "vllm").
        :param kwargs: Additional keyword arguments passed to huggingface_hub.snapshot_download().
        :return: Path to the created .flm file.
        """
        if huggingface_hub is None:  # noqa
            raise exceptions.FrameworkNotInstalled("huggingface_hub")

        if task is None:
            info = huggingface_hub.hf_model_info(model_name)
            task = info.pipeline_tag

        output_path = pathlib.Path(str(output))
        Serializer.dump(
            huggingface_hub.snapshot_download(repo_id=model_name, **kwargs),
            path=output_path,
            config={"task": task},
            extra={"model_name": model_name},
            lib=engine,
        )

        return output_path
