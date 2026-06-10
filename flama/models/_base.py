import abc
import logging
import pathlib
import time
import typing as t
import uuid

from flama import concurrency, exceptions, types
from flama.models.engine.backend import Backend
from flama.models.engine.backend.llm import LLMBackend
from flama.models.engine.backend.ml import MLBackend
from flama.models.engine.llm.codec import LLMCodec
from flama.models.engine.llm.decoder.decoder import Decoder
from flama.models.transport.input.llm.message import Message
from flama.models.transport.input.llm.shape import Shape
from flama.models.transport.input.llm.tool import Tool
from flama.models.transport.output.llm.event import Event, TextEvent, ToolEvent
from flama.serialize.serializer import Serializer

if t.TYPE_CHECKING:
    from flama.serialize.data_structures import Artifacts, Metadata, ModelArtifact

__all__ = ["BaseModel", "MLModel", "LLMModel"]

logger = logging.getLogger(__name__)

B = t.TypeVar("B", bound=Backend)


class BaseModel(abc.ABC, t.Generic[B]):
    """Base class for all Flama model wrappers.

    Backed by three independent lazy tiers — :attr:`meta`, :attr:`artifacts`, :attr:`backend` —
    each cached after first access. Construction only stores configuration; deserialisation is
    deferred to :meth:`load` (sync) or :meth:`startup` (async). Eager construction (passing
    ``backend`` / ``meta`` / ``artifacts``) bypasses every tier; the lazy properties short-circuit
    on the pre-populated private fields.

    Concrete subclasses point :attr:`_BACKEND_CLS` at the family backend ABC
    (:class:`~flama.models.engine.backend.MLBackend` or
    :class:`~flama.models.engine.backend.LLMBackend`). :meth:`load` delegates backend selection
    to :meth:`~flama.models.engine.backend.Backend.from_model_artifact`.
    """

    _BACKEND_CLS: t.ClassVar[type[Backend]]

    def __init__(
        self,
        backend: B | None = None,
        meta: "Metadata | None" = None,
        artifacts: "Artifacts | None" = None,
        *,
        name: str | None = None,
        path: pathlib.Path | None = None,
        autoload: bool = False,
    ) -> None:
        """Initialise the model wrapper.

        Eager mode supplies *backend* / *meta* / *artifacts* directly; lazy mode supplies *path*
        and defers materialisation to :meth:`load` or :meth:`startup`. Both modes can coexist:
        any subset of eager fields short-circuits the matching lazy tier.

        :param backend: Pre-built framework-specific :class:`~flama.models.engine.backend.Backend`.
        :param meta: Pre-loaded serialisation metadata associated with the model.
        :param artifacts: Pre-loaded mapping of artifact names to filesystem paths, if any.
        :param name: Human-readable identifier registered on the application; surfaces in logs.
        :param path: Filesystem path to the packaged model artifact (lazy mode).
        :param autoload: If ``True``, accessing :attr:`backend` triggers a synchronous
            :meth:`load` instead of raising. Reserved for single-threaded callers (CLI).
        """
        self.name = name
        self._backend: B | None = backend
        self._meta: Metadata | None = meta
        self._artifacts: Artifacts | None = artifacts
        self._manifest: tuple[str, ...] | None = None
        self._artifact: ModelArtifact | None = None
        self._path = path
        self._autoload = autoload

    @property
    def meta(self) -> "Metadata":
        """Return the model metadata, reading the cheap header on first access.

        Cached after first access. Pre-populated values supplied to :meth:`__init__` short-circuit
        the read.

        :return: The model metadata.
        :raises ApplicationError: If the model has neither pre-populated metadata nor a path.
        """
        if self._meta is None:
            if self._path is None:
                raise exceptions.ApplicationError(f"Model {self.name!r} has no metadata and no path to read it from")
            self._meta = Serializer.meta(path=self._path)
        return self._meta

    @property
    def manifest(self) -> tuple[str, ...]:
        """Return the names of bundled artifacts; cheap manifest read.

        Tier-1 sibling of :attr:`meta`: surfaces *what* the serialised model packages without
        paying the deserialisation cost or even the metadata decode. After :meth:`load` runs
        the names are taken from the materialised :attr:`artifacts` mapping.

        :return: The names of bundled artifacts, in packed order. Empty if the model bundles
            no artifacts or no path is configured.
        """
        if self._manifest is None:
            if self._artifacts is not None:
                self._manifest = tuple(self._artifacts.keys())
            elif self._path is not None:
                self._manifest = Serializer.manifest(path=self._path)
            else:
                return ()
        return self._manifest

    @property
    def artifacts(self) -> "Artifacts | None":
        """Return the bundled artifacts mapping name → extracted filesystem path.

        Only meaningful post-:meth:`load`. Pre-load returns ``None`` even if the model packages
        artifacts — use :attr:`manifest` for cheap name-only introspection.

        :return: Mapping of artifact names to filesystem paths, or ``None`` if the model has
            not been loaded or bundles no artifacts.
        """
        return self._artifacts

    @property
    def backend(self) -> B:
        """Return the backend wrapping the deserialised engine.

        Heavy load: triggers a synchronous :meth:`load` only when ``autoload=True``. Otherwise
        raises :class:`~flama.exceptions.ApplicationError` so callers can surface a clear error
        instead of accidentally blocking the event loop.

        :return: The backend instance.
        :raises ApplicationError: If the model is not loaded and ``autoload`` is ``False``.
        """
        if self._backend is None:
            if not self._autoload:
                raise exceptions.ApplicationError(
                    f"Model {self.name!r} not loaded; call .load() or await .startup() first"
                )
            self.load()
        return t.cast(B, self._backend)

    @property
    def model(self) -> t.Any:
        """Return the wrapped engine. Triggers :attr:`backend` (and :meth:`load` if autoloaded)."""
        return self.backend.model

    def inspect(self) -> dict[str, t.Any]:
        """Return a dictionary describing the model metadata and bundled artifact names.

        Reads only the cheap :attr:`meta` and :attr:`manifest` tiers; never triggers
        :meth:`load`.

        :return: Dictionary with ``meta`` and ``manifest`` keys.
        """
        return {"meta": self.meta.to_dict(), "manifest": list(self.manifest)}

    def load(self) -> None:
        """Synchronously deserialise the artifact and bind the backend.

        Idempotent: returns early if the backend has already been materialised. Resolves the
        backend via :meth:`~flama.models.engine.backend.Backend.from_model_artifact`, then
        updates every cached tier (:attr:`meta`, :attr:`artifacts`, :attr:`backend`) with the
        freshly-loaded values.

        :raises ApplicationError: If the model was constructed without a ``path`` and the backend
            has not been pre-populated.
        :raises ValueError: If the artifact metadata does not map to a registered backend.
        """
        if self._backend is not None:
            return
        if self._path is None:
            raise exceptions.ApplicationError(f"Model {self.name!r} cannot be loaded without a 'path'")

        logger.info("Model starting (name: %s, id: %s)", self.name, self.meta.id)
        started = time.monotonic()

        artifact = Serializer.load(path=self._path)
        self._backend = t.cast(B, type(self)._BACKEND_CLS.from_model_artifact(artifact))
        self._meta = artifact.meta
        self._artifacts = artifact.artifacts
        self._artifact = artifact

        logger.info("Model loaded (name: %s, id: %s) in %.1fs", self.name, artifact.meta.id, time.monotonic() - started)

    async def startup(self) -> None:
        """Run model-level startup tasks during the application lifespan.

        Default implementation deserialises the artifact in a thread (so it never blocks the
        event loop) and logs readiness. Subclasses override to fold in extra setup that needs an
        event loop (e.g. decoder detection on :class:`LLMModel`). Called once per model from the
        application's lifespan startup phase.
        """
        await concurrency.run(self.load)
        logger.info("Model ready (name: %s, id: %s)", self.name, self.meta.id)


class MLModel(BaseModel[MLBackend]):
    """Wrapper for traditional ML models (predict / stream).

    All framework-specific code lives in the :class:`~flama.models.engine.backend.MLBackend` instance
    bound to :attr:`backend`; this class is concrete and engine-agnostic.
    """

    family: t.ClassVar[types.ModelFamily] = "ml"
    _BACKEND_CLS: t.ClassVar[type[MLBackend]] = MLBackend

    def predict(self, x: t.Iterable[t.Iterable[t.Any]], /) -> t.Any:
        """Run a synchronous prediction against the backend.

        Engine errors propagate as plain Python exceptions; HTTP error mapping happens at the
        resource boundary. :class:`~flama.exceptions.FrameworkNotInstalled` is propagated so
        callers see missing-dependency errors directly.

        :param x: Batch of input feature vectors.
        :return: Backend prediction.
        :raises FrameworkNotInstalled: If the underlying framework is not installed.
        """
        return self.backend.predict(x)

    async def stream(
        self, x: t.AsyncIterable[t.Iterable[t.Any]] | t.Iterable[t.Iterable[t.Any]], /
    ) -> t.AsyncIterator[t.Any]:
        """Yield predictions asynchronously from a batch of input feature vectors.

        Accepts either a synchronous or asynchronous iterable; each item is forwarded to
        :meth:`MLBackend.predict` (wrapped in a one-element batch) inside a thread to avoid
        blocking the event loop. :class:`~flama.exceptions.FrameworkNotInstalled` is propagated
        so callers see missing-dependency errors; any other exception terminates the stream
        cleanly, since the HTTP response has already started by the time predictions are being
        produced.

        :param x: (Async) iterable of input feature vectors, mirroring :meth:`predict`'s element
            type.
        :return: Async iterator of predictions.
        """
        async for item in concurrency.iterate(x):
            try:
                yield await concurrency.run(self.backend.predict, [item])
            except exceptions.FrameworkNotInstalled:
                raise
            except Exception:
                return


class LLMModel(BaseModel[LLMBackend]):
    """Wrapper for large language models (query / stream).

    All framework-specific code lives in the :class:`~flama.models.engine.backend.LLMBackend` instance
    bound to :attr:`backend`; this class is concrete and engine-agnostic. Input shaping is
    delegated to the :class:`~flama.models.Shape` variant chosen for each call (rendered
    against the backend), and output goes through the codec wrapping :attr:`_codec` so
    reasoning and final answer surface as distinct :class:`~flama.models.Event` instances.
    The engine auto-detects the correct strategy on first :meth:`startup` (unless the user
    pre-resolved one via the ``decoder`` kwarg).

    Backend dispatch is hardware-driven: at load time
    :meth:`~flama.models.engine.backend.LLMBackend.from_model_artifact` picks vLLM when its
    package is importable (Linux/CUDA) and MLX when ``mlx.core`` is importable (macOS /
    Apple Silicon). The choice is *not* persisted in the artifact manifest - every system runs
    the artifact through whichever runtime it has available.
    """

    family: t.ClassVar[types.ModelFamily] = "llm"
    _BACKEND_CLS: t.ClassVar[type[LLMBackend]] = LLMBackend

    def __init__(
        self,
        backend: LLMBackend | None = None,
        meta: "Metadata | None" = None,
        artifacts: "Artifacts | None" = None,
        *,
        name: str | None = None,
        path: pathlib.Path | None = None,
        autoload: bool = False,
        decoder: Decoder | None = None,
    ) -> None:
        """Initialise the wrapper around a configured backend with empty default generation params.

        :param backend: Pre-built framework-specific :class:`~flama.models.engine.backend.LLMBackend`.
        :param meta: Pre-loaded serialisation metadata associated with the model.
        :param artifacts: Pre-loaded mapping of artifact names to filesystem paths, if any.
        :param name: Human-readable identifier registered on the application; surfaces in logs.
        :param path: Filesystem path to the packaged model artifact (lazy mode).
        :param autoload: If ``True``, accessing :attr:`backend` triggers a synchronous
            :meth:`load` instead of raising.
        :param decoder: Output decoder configuration. Defaults to :class:`Decoder` in
            auto-detect mode.
        """
        super().__init__(backend, meta, artifacts, name=name, path=path, autoload=autoload)
        self.params: dict[str, t.Any] = {}
        self._codec = LLMCodec(decoder)

    @classmethod
    def validate_config(cls, config: dict[str, t.Any], /) -> dict[str, t.Any]:
        """Validate a generation-config dict and return it unchanged on success.

        Reserved keys (currently: ``reasoning``) are checked against their expected types;
        ordinary generation parameters (``temperature``, ``max_tokens``, ``reasoning_effort``,
        ...) pass through without inspection — chat templates and backends interpret them at
        render / sample time and surface their own errors for unsupported values. Used by both
        :meth:`configure` (direct programmatic use) and
        :meth:`flama.models.modules.ModelsModule.add_model` (resource construction) so the
        same set of reserved keys is rejected uniformly regardless of the entry point.

        :param config: Free-form generation config (the same shape callers feed into
            :meth:`configure` or :meth:`add_model`'s ``params`` argument).
        :return: ``config`` unchanged on success.
        :raises ValueError: If any reserved key carries an unsupported value.
        """
        if "reasoning" in config and not isinstance(config["reasoning"], bool):
            raise ValueError(f"'reasoning' must be a bool; got {config['reasoning']!r}")
        return config

    def configure(self, params: dict[str, t.Any]) -> None:
        """Merge *params* into the default generation parameters.

        Validates the dict via :meth:`validate_config` and merges it into :attr:`params`. The
        ``reasoning`` flag is a resource-level concern (lifted onto :attr:`LLMResource.reasoning`
        by :meth:`~flama.models.modules.ModelsModule.add_model` before this method is reached);
        if a caller still routes it through here it stays in :attr:`params`, where backends and
        templates can read it alongside any other generation hint.

        :param params: Key-value pairs to update.
        :raises ValueError: If any reserved key carries an unsupported value.
        """
        self.params.update(type(self).validate_config(dict(params)))

    async def startup(self) -> None:
        """Materialise the model and run decoder detection.

        Loads the artifact in a thread (idempotent — :meth:`load` early-exits when the backend is
        already populated), then runs decoder detection so the right marker-aware strategy is
        picked before serving. Any failure during detection is swallowed by the engine and
        downgraded to passthrough — it will never block startup.
        """
        await concurrency.run(self.load)

        logger.info("Decoder detection starting (name: %s, id: %s)", self.name, self.meta.id)
        started = time.monotonic()
        await self._codec.detect(self)
        logger.info(
            "Decoder detection complete (name: %s, id: %s) in %.1fs",
            self.name,
            self.meta.id,
            time.monotonic() - started,
        )

        logger.info("Model ready (name: %s, id: %s)", self.name, self.meta.id)

    @property
    def default_transport(self) -> types.LLMTransportShape:
        """Resolve the default transport for the bound backend.

        Mirrors :attr:`LLMBackend.default_transport` so callers don't need to reach through to the
        backend.

        :return: ``"chat"`` if the backend has a chat template, ``"raw"`` otherwise.
        """
        return self.backend.default_transport

    async def query(
        self,
        prompt: str | None = None,
        /,
        *,
        system: str | None = None,
        messages: t.Sequence[Message] | None = None,
        tools: t.Sequence[Tool] | None = None,
        transport: types.LLMTransportShape | None = None,
        chat_template_kwargs: dict[str, t.Any] | None = None,
        message_id: uuid.UUID | None = None,
        **params: t.Any,
    ) -> list[Event]:
        """Run an asynchronous query against the LLM and return the produced blocks end-to-end.

        Pass ``prompt`` for single-turn queries (``raw`` / ``chat``) or ``messages`` for multi-turn
        ``conversation`` queries. ``transport`` defaults to :attr:`default_transport` when not explicitly
        specified. Output is decoded via :attr:`_codec`: the returned list opens with a
        :class:`~flama.models.StartEvent`, contains :class:`TextEvent` / :class:`ToolEvent` /
        :class:`~flama.models.TraceEvent` items as the model produces them, and closes with a
        :class:`~flama.models.StopEvent` snapshotting ``stop_reason`` and ``usage``. Callers extract
        whatever shape they need from this uniform list (e.g.
        :class:`~flama.models.transport.output.llm.buffer.EventBuffer` for the buffered query
        envelope).

        :param prompt: User prompt text (positional-only).
        :param system: Optional system instruction (``chat`` only).
        :param messages: Conversation history (``conversation`` only). Pre-built
            :class:`Message` instances — dialect parsing happens upstream in each serving's
            :meth:`~flama.models.resources.serving.llm._base.LLMServing.parse`.
        :param transport: Explicit transport discriminator. Defaults to :attr:`default_transport`.
        :param tools: Optional list of canonical L2 :class:`Tool` specs advertised to the model
            (templated transports only). Dialect parsing happens upstream in each serving's
            :meth:`~flama.models.resources.serving.llm._base.LLMServing.parse`.
        :param chat_template_kwargs: Extra keyword arguments forwarded to the chat template
            (templated transports only).
        :param message_id: Optional stream identifier surfaced in the opening :class:`StartEvent`. When
            omitted a fresh UUID4 is minted so every query yields a self-identifying log.
        :param params: Override generation parameters merged into :attr:`params`. ``max_tokens`` may
            be omitted or :data:`None` to generate until natural completion (EOS), bounded only by
            the model's context window; pass a positive integer to enforce a hard cap.
        :return: Ordered list of :class:`Event` events, framed by :class:`StartEvent` /
            :class:`StopEvent` lifecycle markers.
        :raises ValueError: For invalid transport / field combinations, or non-positive
            ``max_tokens``.
        :raises RuntimeError: If the engine produces no content blocks.
        """
        t = Shape.build(
            transport or self.backend.default_transport,
            prompt=prompt,
            system=system,
            messages=tuple(messages) if messages else None,
            tools=tuple(tools) if tools else None,
        )
        inputs = await t.render(self.backend, chat_template_kwargs=chat_template_kwargs)

        blocks: list[Event] = []
        async for item in self._codec.decode(
            self.backend.generate(inputs, **{**self.params, **params}),
            message_id=message_id or uuid.uuid4(),
            input_tokens=len(inputs.tokens),
        ):
            blocks.append(item)

        if not any(isinstance(b, (TextEvent, ToolEvent)) for b in blocks):
            raise RuntimeError("LLM engine produced no output")

        return blocks

    async def stream(
        self,
        prompt: str | None = None,
        /,
        *,
        system: str | None = None,
        messages: t.Sequence[Message] | None = None,
        tools: t.Sequence[Tool] | None = None,
        transport: types.LLMTransportShape | None = None,
        chat_template_kwargs: dict[str, t.Any] | None = None,
        message_id: uuid.UUID | None = None,
        **params: t.Any,
    ) -> t.AsyncIterator[Event]:
        """Stream channel-tagged blocks asynchronously from the LLM.

        Validation (transport build + render) happens before iteration starts so ``ValueError``
        surfaces to callers immediately. The iterator emits :class:`Event` instances of every
        kind produced by :class:`~flama.models.engine.llm.codec.LLMCodec` —
        :class:`~flama.models.StartEvent` / :class:`~flama.models.StopEvent` lifecycle
        markers framing :class:`TextEvent` / :class:`ToolEvent` content and :class:`TraceEvent`
        metadata. Errors raised mid-iteration propagate to the caller, which decides how to
        terminate the in-flight response (the SSE driver injects an ``"error"`` :class:`StopEvent`
        itself).

        :param prompt: User prompt text (positional-only).
        :param system: Optional system instruction (``chat`` only).
        :param messages: Conversation history (``conversation`` only).
        :param transport: Explicit transport discriminator. Defaults to :attr:`default_transport`.
        :param tools: Optional list of canonical L2 :class:`Tool` specs advertised to the model
            (templated transports only). Dialect parsing happens upstream in each serving's
            :meth:`~flama.models.resources.serving.llm._base.LLMServing.parse`.
        :param chat_template_kwargs: Extra keyword arguments forwarded to the chat template
            (templated transports only).
        :param message_id: Stream identifier surfaced in the opening :class:`StartEvent`. The serving layer
            passes the buffer uuid here so the wire frame, cold log, and replay all agree.
        :param params: Override generation parameters merged into :attr:`params`. ``max_tokens`` may
            be omitted or :data:`None` to generate until natural completion (EOS), bounded only by
            the model's context window; pass a positive integer to enforce a hard cap.
        :return: Async iterator of :class:`Event` events.
        :raises ValueError: For invalid transport / field combinations, or non-positive
            ``max_tokens``.
        """
        t = Shape.build(
            transport or self.backend.default_transport,
            prompt=prompt,
            system=system,
            messages=tuple(messages) if messages else None,
            tools=tuple(tools) if tools else None,
        )
        inputs = await t.render(self.backend, chat_template_kwargs=chat_template_kwargs)

        return self._codec.decode(
            self.backend.generate(inputs, **{**self.params, **params}),
            message_id=message_id,
            input_tokens=len(inputs.tokens),
        )
