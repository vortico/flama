import abc
import typing as t

from flama import exceptions
from flama.concurrency import iterate, run

if t.TYPE_CHECKING:
    from flama.serialize.data_structures import Artifacts, Metadata

__all__ = ["BaseModel", "BaseMLModel", "BaseLLMModel"]


class BaseModel(abc.ABC):
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
    def _prediction(self, x: t.Iterable[t.Iterable[t.Any]], /) -> t.Any:
        """Run the engine-specific prediction.

        Subclasses implement the framework-specific call here. :meth:`predict` and :meth:`stream` are defined in terms
        of this method.

        :param x: Batch of input feature vectors.
        :return: Model prediction.
        :raises FrameworkNotInstalled: If the underlying framework is not installed.
        """
        ...

    def predict(self, x: t.Iterable[t.Iterable[t.Any]], /) -> t.Any:
        """Run a synchronous prediction.

        Delegates to :meth:`_prediction` and wraps engine errors as 400 :class:`~flama.exceptions.HTTPException`.
        :class:`~flama.exceptions.FrameworkNotInstalled` is propagated so callers see missing-dependency errors.

        :param x: Batch of input feature vectors.
        :return: Model prediction.
        :raises HTTPException: 400 on engine error.
        :raises FrameworkNotInstalled: If the underlying framework is not installed.
        """
        try:
            return self._prediction(x)
        except exceptions.FrameworkNotInstalled:
            raise
        except Exception as e:
            raise exceptions.HTTPException(status_code=400, detail=str(e))

    async def stream(
        self, x: t.AsyncIterable[t.Iterable[t.Any]] | t.Iterable[t.Iterable[t.Any]], /
    ) -> t.AsyncIterator[t.Any]:
        """Yield predictions asynchronously from a batch of input feature vectors.

        Accepts either a synchronous or asynchronous iterable; each item is forwarded to :meth:`predict` (wrapped in
        a one-element batch) inside a thread to avoid blocking the event loop.
        :class:`~flama.exceptions.FrameworkNotInstalled` is propagated so callers see missing-dependency errors; any
        other exception terminates the stream cleanly, since the HTTP response has already started by the time
        predictions are being produced.

        :param x: (Async) iterable of input feature vectors, mirroring :meth:`predict`'s element type.
        :return: Async iterator of predictions.
        """
        async for item in iterate(x):
            try:
                yield await run(self.predict, [item])
            except exceptions.FrameworkNotInstalled:
                raise
            except Exception:
                return


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
    async def _tokens(self, prompt: str, /, **params: t.Any) -> t.AsyncIterator[str]:
        """Yield generated text chunks for *prompt* one at a time.

        Subclasses implement the engine-specific iteration logic here. :meth:`query` and :meth:`stream` are defined
        in terms of this iterator.

        :param prompt: The input prompt.
        :param params: Override generation parameters for this call.
        :return: Async iterator of text chunks.
        """
        yield ""  # pragma: no cover

    async def query(self, prompt: str, /, **params: t.Any) -> t.Any:
        """Run an asynchronous query against the LLM and return the joined output.

        :param prompt: The input prompt.
        :param params: Override generation parameters for this call.
        :return: The full generated text.
        :raises HTTPException: 500 if the engine produces no output, 400 for any engine error.
        """
        try:
            chunks = [token async for token in self._tokens(prompt, **params)]
        except Exception as e:
            raise exceptions.HTTPException(status_code=400, detail=str(e))

        if not chunks:
            raise exceptions.HTTPException(status_code=500, detail="LLM engine produced no output")

        return "".join(chunks)

    async def stream(self, prompt: str, /, **params: t.Any) -> t.AsyncIterator[t.Any]:
        """Stream output tokens asynchronously from the LLM.

        Errors raised mid-iteration terminate the stream cleanly without propagating, since the HTTP response has
        already started by the time tokens are being produced.

        :param prompt: The input prompt.
        :param params: Override generation parameters for this call.
        :return: Async iterator of output tokens.
        """
        try:
            async for token in self._tokens(prompt, **params):
                yield token
        except Exception:
            return
