import logging
import os
import typing as t

from flama.models.base import LLMModel
from flama.models.components import ModelComponent, ModelComponentBuilder
from flama.models.engine.llm.decoder.decoder import Decoder
from flama.models.resources.llm import LLMResource, LLMResourceType
from flama.models.resources.ml import MLResource, MLResourceType
from flama.models.streams import CleanupTask, StreamsRegistry
from flama.modules import Module

if t.TYPE_CHECKING:
    from flama import types
    from flama.resources import ResourceRoute

__all__ = ["ModelsModule"]

logger = logging.getLogger(__name__)

_DEFAULT_STREAM_TTL: t.Final[float] = 600.0
_DEFAULT_STREAM_DISK_USAGE: t.Final[int] = 1 << 30  # 1 GiB aggregate budget across all per-model logs.
_DEFAULT_STREAM_CLEANUP_PERIOD: t.Final[float] = 60.0


class ModelsModule(Module):
    """Application module wiring packaged ML and LLM artifacts into Flama.

    Exposes high-level helpers to register a model artifact under an HTTP path. Dispatch keys off the ``family`` field
    recorded in the manifest at download time: ``"ml"`` artifacts are wrapped in :class:`MLResource` while ``"llm"``
    artifacts are wrapped in :class:`LLMResource`. Bundled artifacts are tracked on the module instance for later
    introspection.

    LLM resources additionally share a single :class:`~flama.models.streams.StreamsRegistry`. The registry's backend
    lifecycle is wired through :meth:`on_startup` and :meth:`on_shutdown` so cold storage (a tempdir for the default
    file backend) is opened when the app boots and reclaimed when it shuts down. The default registry ships a
    :class:`~flama.models.streams.CleanupTask`; pass ``streams_registry`` to swap in a custom one.

    Model components registered through :meth:`add_model` / :meth:`add_model_resource` are materialised in
    :meth:`on_startup` *sequentially*. Sequential loading is intentional: LLM/ML artifacts can be multi-GB and
    serialising load avoids peak-RAM spikes; the trade-off is longer cold-start when several models are wired.

    :param streams_registry: Optional pre-configured registry. ``None`` (default) builds a
        :class:`~flama.models.streams.FileStreamsBackend` + :class:`~flama.models.streams.CleanupTask` combo.
    """

    name = "models"

    def __init__(self, *, streams_registry: StreamsRegistry | None = None) -> None:
        super().__init__()
        self._components: list[ModelComponent] = []
        self._registry: StreamsRegistry = (
            streams_registry
            if streams_registry is not None
            else StreamsRegistry(
                cleanup=CleanupTask(
                    ttl=_DEFAULT_STREAM_TTL,
                    disk_usage=_DEFAULT_STREAM_DISK_USAGE,
                    period=_DEFAULT_STREAM_CLEANUP_PERIOD,
                )
            )
        )

    async def on_startup(self) -> None:
        """Open the streams registry and materialise every registered model component.

        Components are started sequentially to bound peak memory. The streams registry is opened first so its
        backend is ready before any handler could ever push a buffer.
        """
        await self._registry.aopen()
        for component in self._components:
            await component.startup()

    async def on_shutdown(self) -> None:
        """Close the underlying streams registry, dropping all in-memory and cold-storage state."""
        await self._registry.aclose()

    def add_model(
        self,
        path: str,
        model: str | os.PathLike,
        name: str,
        tags: dict[str, dict[str, t.Any]] | None = None,
        *args,
        decoder: "Decoder | None" = None,
        params: dict[str, t.Any] | None = None,
        serving: "tuple[types.LLMServing, ...] | None" = None,
        **kwargs,
    ) -> "ResourceRoute":
        """Register a packaged model under *path*, auto-routing to the appropriate resource type.

        Registration is cheap: only the artifact's metadata header is read so the right resource
        class can be selected. Heavy deserialisation runs inside
        :meth:`~flama.models.components.ModelComponent.startup`, registered on
        ``app.events.startup`` so uvicorn binds the port before model loading begins.

        Reserved keys in *params* (currently ``reasoning``) are validated via
        :meth:`LLMModel.validate_config`, lifted off the generation-params dict and forwarded
        to dedicated resource attributes (e.g. :attr:`BaseLLMResource.reasoning`) so they
        never reach ``backend.generate(...)`` as keyword arguments. Open-typed hints such as
        ``reasoning_effort`` ride alongside ``temperature`` / ``max_tokens`` in the remaining
        params and are forwarded as-is to :meth:`LLMModel.configure`.

        :param path: Mount path for the resource.
        :param model: Filesystem path to the packaged model artifact.
        :param name: Resource name used for OpenAPI tags.
        :param tags: Method-level tags forwarded to the resource.
        :param decoder: Optional :class:`Decoder` configuration for LLM artifacts. ``None``
            (default) defers to the model's own default (auto-detect at startup). Rejected
            at build time for non-LLM artifacts.
        :param params: Optional default generation parameters for LLM artifacts. Reserved keys
            are lifted onto resource attributes; the remainder is forwarded to
            :meth:`LLMModel.configure`. Rejected at build time for non-LLM artifacts.
        :param serving: Optional tuple of serving layer names enabled for LLM artifacts (see
            :data:`~flama.types.LLMServing`). ``None`` (default) defers to
            :attr:`LLMResourceType.DEFAULT_SERVING`. Ignored for non-LLM artifacts.
        :return: The mounted :class:`ResourceRoute`.
        :raises ValueError: If *decoder* or *params* is set for a non-LLM artifact, or if
            any reserved key in *params* carries an unsupported value.
        """
        reasoning: bool | None = None
        if params is not None:
            params = LLMModel.validate_config(dict(params))
            if "reasoning" in params:
                reasoning = bool(params.pop("reasoning"))

        component = ModelComponentBuilder.build(model, name=name, decoder=decoder, params=params or None)
        family = component.model.meta.framework.family
        logger.info("Adding model %r from %s (family=%s)", name, model, family)

        namespace: dict[str, t.Any] = {"name": name, "component": component}

        if issubclass(component.get_model_type(), LLMModel):
            if serving is not None:
                namespace["serving"] = serving
            resource = LLMResourceType("Resource", (LLMResource,), namespace)()
            if reasoning is not None:
                resource.reasoning = reasoning
        else:
            if reasoning is not None:
                raise ValueError(f"'reasoning' is not supported by family {family!r}")
            resource = MLResourceType("Resource", (MLResource,), namespace)()

        return self.add_model_resource(path, resource, tags, *args, **kwargs)

    def model_resource(self, path: str, tags: dict[str, dict[str, t.Any]] | None = None, *args, **kwargs) -> t.Callable:
        """Decorator registering an :class:`MLResource` or :class:`LLMResource` subclass at *path*.

        Extra positional and keyword arguments are forwarded to :meth:`add_model_resource`.

        :param path: Mount path for the resource.
        :param tags: Method-level tags forwarded to the resource.
        :return: Decorator returning the original resource class unchanged.
        """

        def decorator(resource: type[MLResource | LLMResource]) -> type[MLResource | LLMResource]:
            self.add_model_resource(path, resource, tags, *args, **kwargs)
            return resource

        return decorator

    def add_model_resource(
        self,
        path: str,
        resource: MLResource | LLMResource | type[MLResource | LLMResource],
        tags: dict[str, dict[str, t.Any]] | None = None,
        *args,
        **kwargs,
    ) -> "ResourceRoute":
        """Register an :class:`MLResource` or :class:`LLMResource` instance/class under *path*.

        The resource's component is added to the app and tracked on the module so :meth:`on_startup`
        can materialise it once the app boots. Eager components (those constructed via
        :meth:`ModelComponentBuilder.build`) flow through the same path: their ``startup()`` is a
        no-op so the bookkeeping stays uniform.

        :param path: Mount path for the resource.
        :param resource: Resource instance or class.
        :param tags: Method-level tags forwarded to the resource.
        :return: The mounted :class:`ResourceRoute`.
        """
        component = resource.component
        self.app.add_component(component)
        self._components.append(component)

        target_cls = resource if isinstance(resource, type) else type(resource)
        if issubclass(target_cls, LLMResource) and not hasattr(target_cls, "_streams"):
            target_cls._streams = self._registry.add(target_cls._meta.name)

        return self.app.resources.add_resource(path, resource, *args, tags=tags, **kwargs)
