import abc
import typing as t

from flama import types
from flama.models.engine.backend._base import Backend
from flama.serialize.data_structures import ModelArtifact

__all__ = ["MLBackend"]


class MLBackend(Backend):
    """Framework-specific runtime adapter for a traditional ML model.

    Concrete subclasses implement :meth:`predict` for their framework. Streaming is layered on top
    by :class:`~flama.models.MLModel` by repeatedly invoking :meth:`predict` in a thread pool.
    """

    family: t.ClassVar[types.ModelFamily] = "ml"
    _REGISTRY: t.ClassVar[dict[types.ModelLib, type["MLBackend"]] | None] = None

    @classmethod
    def _resolve(cls, lib: types.ModelLib) -> type["MLBackend"]:
        """Lazily resolve the backend class registered for *lib*.

        Concrete backends are imported on first call so the side-effect-free
        ``from flama.models.engine.backend.ml._base import MLBackend`` does not pull every
        framework adapter into the import graph. Subsequent calls reuse the cached
        :attr:`_REGISTRY`.

        :param lib: Framework library key persisted in :attr:`Metadata.framework.lib`.
        :return: Backend class registered for *lib*.
        :raises ValueError: If *lib* is not a registered framework key.
        """
        if cls._REGISTRY is None:
            from flama.models.engine.backend.ml.pytorch import PytorchBackend
            from flama.models.engine.backend.ml.sklearn import SklearnBackend
            from flama.models.engine.backend.ml.tensorflow import TensorflowBackend
            from flama.models.engine.backend.ml.transformers import TransformersBackend

            cls._REGISTRY = {
                "sklearn": SklearnBackend,
                "torch": PytorchBackend,
                "tensorflow": TensorflowBackend,
                "keras": TensorflowBackend,
                "transformers": TransformersBackend,
            }
        try:
            return cls._REGISTRY[lib]
        except KeyError:
            raise ValueError(f"Wrong backend key {lib!r}") from None

    @classmethod
    def from_model_artifact(cls, artifact: ModelArtifact) -> "MLBackend":
        """Instantiate the backend registered for :attr:`Metadata.framework.lib`.

        :param artifact: Deserialised model artifact.
        :return: Backend instance bound to :attr:`ModelArtifact.model`.
        :raises ValueError: If the framework library is not registered.
        """
        return cls._resolve(artifact.meta.framework.lib)(artifact.model)

    @abc.abstractmethod
    def predict(self, x: t.Iterable[t.Iterable[t.Any]], /) -> t.Any:
        """Run a synchronous batch prediction.

        :param x: Batch of input feature vectors.
        :return: Framework-specific prediction output (typically a list of predictions).
        :raises FrameworkNotInstalled: If the underlying framework is not installed.
        """
        ...
