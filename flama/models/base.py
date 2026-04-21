import abc
import typing as t

if t.TYPE_CHECKING:
    from flama.serialize.data_structures import Artifacts, Metadata

__all__ = ["BaseModel", "BaseMLModel", "BaseLLMModel"]


class BaseModel:
    """Base class for all Flama model wrappers."""

    def __init__(self, model: t.Any, meta: "Metadata", artifacts: "Artifacts | None"):
        """Initialise the model wrapper.

        :param model: The deserialised model object.
        :param meta: Serialisation metadata associated with the model.
        :param artifacts: Mapping of artifact names to filesystem paths, if any.
        """
        self.model = model
        self.meta = meta
        self.artifacts = artifacts

    def inspect(self) -> t.Any:
        """Return a dictionary describing the model metadata and artifacts.

        :return: Dictionary with ``meta`` and ``artifacts`` keys.
        """
        return {"meta": self.meta.to_dict(), "artifacts": self.artifacts}


class BaseMLModel(BaseModel):
    """Base class for traditional ML model wrappers (predict / stream)."""

    @abc.abstractmethod
    def predict(self, x: list[list[t.Any]], /) -> t.Any:
        """Run a synchronous prediction.

        :param x: Input features.
        :return: Model prediction.
        """
        ...

    @abc.abstractmethod
    async def stream(self, x: t.Any, /) -> t.AsyncIterator[t.Any]:
        """Yield predictions asynchronously from an input stream.

        :param x: Async-iterable input.
        :return: Async iterator of predictions.
        """
        yield  # pragma: no cover


class BaseLLMModel(BaseModel):
    """Base class for large-language-model wrappers (query / stream)."""

    def __init__(self, model: t.Any, meta: "Metadata", artifacts: "Artifacts | None"):
        """Initialise the LLM wrapper with empty default generation parameters.

        :param model: The deserialised model object.
        :param meta: Serialisation metadata associated with the model.
        :param artifacts: Mapping of artifact names to filesystem paths, if any.
        """
        super().__init__(model, meta, artifacts)
        self.params: dict[str, t.Any] = {}

    def configure(self, params: dict[str, t.Any]) -> None:
        """Merge *params* into the default generation parameters.

        :param params: Key-value pairs to update.
        """
        self.params.update(params)

    @abc.abstractmethod
    async def query(self, prompt: str, /, **params: t.Any) -> t.Any:
        """Run an asynchronous query against the LLM.

        :param prompt: The input prompt.
        :param params: Override generation parameters for this call.
        :return: Model output.
        """
        ...

    @abc.abstractmethod
    async def stream(self, prompt: str, /, **params: t.Any) -> t.AsyncIterator[t.Any]:
        """Stream output tokens asynchronously from the LLM.

        :param prompt: The input prompt.
        :param params: Override generation parameters for this call.
        :return: Async iterator of output tokens.
        """
        yield  # pragma: no cover
