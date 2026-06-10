import abc
import typing as t

from flama.compat import Self
from flama.serialize.data_structures import ModelArtifact

__all__ = ["Backend"]


class Backend(abc.ABC):
    """Adapter to a specific ML/LLM framework runtime.

    Concrete backends wrap a deserialised engine on :attr:`model` and expose a framework-agnostic
    surface that the :class:`~flama.models.LLMModel` / :class:`~flama.models.MLModel`
    wrappers consume. ML and LLM ABCs add their own abstract methods on top of this shared root.
    """

    model: t.Any

    def __init__(self, model: t.Any, /) -> None:
        """Bind the backend to a deserialised engine.

        :param model: The deserialised model object owned by this backend.
        """
        self.model = model

    @classmethod
    @abc.abstractmethod
    def from_model_artifact(cls, artifact: ModelArtifact) -> Self:
        """Pick and instantiate the concrete backend for *artifact*.

        Family ABCs (:class:`~flama.models.engine.backend.MLBackend`,
        :class:`~flama.models.engine.backend.LLMBackend`) implement the dispatch logic against
        their registered subclasses. ML dispatch keys on :attr:`Metadata.framework.lib`; LLM
        dispatch probes runtime availability on the host system.

        :param artifact: Deserialised model artifact produced by :class:`~flama.serialize.serializer.Serializer`.
        :return: A backend instance bound to :attr:`ModelArtifact.model`.
        :raises ValueError: If the artifact metadata does not map to a registered backend.
        :raises FrameworkNotInstalled: When no suitable runtime is importable on this system (LLM only).
        """
        ...
