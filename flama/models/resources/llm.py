import contextlib
import os
import typing as t

from flama import exceptions, types
from flama.models.components import ModelComponentBuilder
from flama.models.resources.serving.llm import LLMServing
from flama.models.streams import ModelStreams
from flama.resources import data_structures
from flama.resources.exceptions import (
    ResourceAttributeNotFound,
    ResourceModelNotFound,
    ResourceServingLayerUnknown,
    ResourceServingMethodInvalidPrefix,
)
from flama.resources.resource import Resource, ResourceType

if t.TYPE_CHECKING:
    from flama.models.components import ModelComponent

__all__ = ["BaseLLMResource", "LLMResource", "LLMResourceType"]


Component = t.TypeVar("Component", bound="ModelComponent")

_SERVINGS: tuple[types.LLMServing, ...] = t.get_args(types.LLMServing)


class LLMResourceType(ResourceType, *(LLMServing._resolve(s) for s in _SERVINGS)):
    """Resource metaclass for :class:`BaseLLMResource` subclasses.

    Wires the resource to a :class:`~flama.models.components.ModelComponent` and registers HTTP
    methods drawn from one or more serving layers. The selection is controlled by the
    ``serving`` attribute on the resource class (a tuple of :data:`~flama.types.LLMServing`
    names); when omitted, defaults to :attr:`DEFAULT_SERVING`. :attr:`SERVING_METHODS` is
    derived by resolving every entry of :data:`~flama.types.LLMServing` through
    :meth:`LLMServing._resolve` and maps each layer name to its method tuple, which
    :meth:`_build_methods` flattens into the ``methods`` argument of
    :meth:`ResourceType._build_methods` while preserving any explicit methods passed by callers.
    """

    SERVING_METHODS: t.ClassVar[dict[types.LLMServing, tuple[str, ...]]] = {
        s: LLMServing._resolve(s).METHODS for s in _SERVINGS
    }
    DEFAULT_SERVING: t.ClassVar[tuple[types.LLMServing, ...]] = _SERVINGS

    def __new__(mcs, name: str, bases: tuple[type], namespace: dict[str, t.Any]):
        if not mcs._is_abstract(namespace):
            component = mcs._get_model_component(name, bases, namespace)
            namespace["component"] = component
            namespace["model"] = component.model

            namespace.setdefault("_meta", data_structures.Metadata()).namespaces["model"] = {
                "component": component,
                "model": component.model,
                "model_type": component.get_model_type(),
            }

        return super().__new__(mcs, name, bases, namespace)

    @classmethod
    def _build_methods(
        cls, namespace: dict[str, t.Any], methods: t.Sequence[str] | None = None
    ) -> dict[str, t.Callable]:
        """Combine serving-derived methods with any explicit *methods* and delegate to the parent.

        Resolves the resource's ``serving`` attribute from *namespace* (defaulting to
        :attr:`DEFAULT_SERVING`), validates each name against :attr:`SERVING_METHODS`, asserts the
        method-name prefix convention (non-native layers must prefix every method name with
        ``<NAME>_``), and flattens the corresponding method tuples into a single ordered sequence.
        Explicit *methods* passed by callers (e.g. sub-metaclasses chaining through ``super()``) are
        kept and placed **first** in the combined tuple; collisions on equal names dedupe silently
        through :func:`dict.fromkeys`.

        :param namespace: Variables namespace used to create the class.
        :param methods: Optional explicit list of method names contributed by a downstream
            metaclass; combined with — not replaced by — the serving-derived set.
        :return: Methods namespace as produced by :meth:`ResourceType._build_methods`.
        :raises ResourceServingLayerUnknown: If *namespace* requests a serving layer name that is
            not in :attr:`SERVING_METHODS`.
        :raises ResourceServingMethodInvalidPrefix: If any non-native registered layer declares a
            method name that does not start with ``<NAME>_``.
        """
        qualname = namespace.get("__qualname__", "<resource>")
        serving = namespace.pop("serving", cls.DEFAULT_SERVING)

        if unknown := set(serving) - cls.SERVING_METHODS.keys():
            raise ResourceServingLayerUnknown(
                name=qualname,
                layers=", ".join(sorted(unknown)),
                known=", ".join(sorted(cls.SERVING_METHODS)),
            )

        if invalid := {
            (m, s) for s in serving for m in cls.SERVING_METHODS[s] if s != "native" and not m.startswith(f"{s}_")
        }:
            renames = ", ".join(sorted(f'"{m}" -> "{s}_{m}"' for m, s in invalid))
            raise ResourceServingMethodInvalidPrefix(name=qualname, methods=renames)

        serving_methods = tuple(m for layer in serving for m in cls.SERVING_METHODS[layer])
        combined = tuple(dict.fromkeys((*(methods or ()), *serving_methods)))
        return super()._build_methods(namespace, methods=combined)

    @staticmethod
    def _is_abstract(namespace: dict[str, t.Any]) -> bool:
        return namespace.get("__module__") == "flama.models.resources.llm" and namespace.get("__qualname__") in (
            "BaseLLMResource",
            "LLMResource",
        )

    @classmethod
    def _get_model_component(cls, name: str, bases: t.Sequence[t.Any], namespace: dict[str, t.Any]) -> "ModelComponent":
        with contextlib.suppress(ResourceAttributeNotFound):
            return cls._get_attribute(name, "component", bases, namespace, metadata_namespace="model")

        with contextlib.suppress(ResourceAttributeNotFound):
            return ModelComponentBuilder.build(
                cls._get_attribute(name, "model_path", bases, namespace, metadata_namespace="model")
            )

        raise ResourceModelNotFound(name=name)


class BaseLLMResource(Resource, t.Generic[Component], metaclass=LLMResourceType):
    component: Component
    model: t.Any
    model_path: str | os.PathLike
    serving: t.ClassVar[tuple[types.LLMServing, ...]]
    reasoning: bool = True
    """Whether the resource asks the underlying model to produce reasoning content.

    Resource-level default; overridable per-request on dialects that surface a thinking
    toggle (the Ollama ``/api/chat`` ``think`` field, or the presence of the OpenAI
    Responses ``reasoning`` object). Chat-completions has no per-request bool field, so
    only the resource default applies there. When the bound backend doesn't advertise
    :attr:`~flama.models.engine.backend.LLMBackendCapabilities.reasoning`, the value is
    ignored at the handler boundary.
    """
    heartbeat_interval: t.ClassVar[float] = 15.0

    _streams: t.ClassVar[ModelStreams]
    """Per-model :class:`~flama.models.streams.ModelStreams` handle.

    Framework-managed: bound by :meth:`~flama.models.modules.ModelsModule.add_model_resource` at wiring time and
    not intended to be set by subclass authors. Read it from outside the class through the :attr:`streams`
    property, which surfaces a clear :class:`~flama.exceptions.ApplicationError` when the resource has not yet
    been wired.
    """

    @property
    def streams(self) -> ModelStreams:
        """Per-model streams handle exposed to handlers and external consumers.

        :raises ApplicationError: If the resource has not been wired through a
            :class:`~flama.models.modules.ModelsModule` (i.e. ``_streams`` is unbound).
        """
        try:
            return self._streams
        except AttributeError as e:
            raise exceptions.ApplicationError(
                "LLM resource is not wired through ModelsModule; mount it via add_model_resource"
            ) from e


class LLMResource(BaseLLMResource["ModelComponent"]): ...
