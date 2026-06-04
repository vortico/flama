import abc
import dataclasses
import typing as t

from flama import compat, types
from flama.models.transport.input.llm.message import Message
from flama.models.transport.input.llm.tool import Tool

if t.TYPE_CHECKING:
    from flama.models.engine.backend.llm.base import LLMBackend
    from flama.models.engine.llm.input import EngineInput

__all__ = ["Shape"]


class _ShapeFields(t.TypedDict):
    """Type-narrowed bag of inputs accepted by :meth:`Shape.build` and the variants.

    Each variant consumes a subset of these keys via its :class:`~dataclasses.InitVar` and rejects
    the rest. ``messages`` must be a :class:`tuple` because the resulting transport is frozen;
    converting an iterable into an immutable sequence is the caller's responsibility.
    """

    prompt: compat.NotRequired[str]
    system: compat.NotRequired[str]
    messages: compat.NotRequired[tuple[Message, ...]]
    tools: compat.NotRequired[tuple[Tool, ...]]


class _ShapeRenderKwargs(t.TypedDict, total=False):
    """Marker / superset TypedDict for the kwargs accepted by :meth:`Shape.render`.

    Carries the currently-typed fields shared across :class:`Shape` variants. ``Raw`` ignores
    every field; ``Chat`` and ``Conversation`` consume ``chat_template_kwargs`` and forward it
    to :meth:`~flama.models.engine.backend.llm.base.LLMBackend.prepare_input`. Variants whose
    render surface diverges from the marker introduce their own TypedDict (extending or
    subsetting this one) and bind it through the :data:`_SK` parameter.
    """

    chat_template_kwargs: dict[str, t.Any] | None


_SK = t.TypeVar("_SK", bound=_ShapeRenderKwargs)


@dataclasses.dataclass(frozen=True)
class Shape(abc.ABC, t.Generic[_SK]):
    """Discriminated union for LLM input shapes.

    Each concrete variant declares its discriminator value via the class-level :attr:`transport`
    constant and implements :meth:`render` to convert itself into engine-ready token IDs using a
    :class:`~flama.models.engine.backend.LLMBackend`.

    Variants accept their construction inputs through a single ``fields`` :class:`InitVar` bag
    typed as :class:`_ShapeFields`. The shared :meth:`__post_init__` defined here rejects any
    key that is not a declared dataclass field on the concrete variant; subclasses override
    :meth:`__post_init__` to extract and validate their own fields and chain to ``super()`` to
    pick up the shared check. Use :meth:`Shape.build` as the public entry point; it
    dispatches on the discriminator and forwards the bag.

    The generic parameter ``_SK`` is the variant-specific :class:`~typing.TypedDict` describing the
    kwargs accepted by :meth:`render`; type-checked through PEP 692 ``Unpack`` on
    :meth:`render`'s ``**kwargs``. Variants whose render surface matches the marker bind
    :class:`_ShapeRenderKwargs` directly; future variants with divergent kwargs declare their own.
    """

    fields: dataclasses.InitVar[_ShapeFields | None] = None
    transport: t.ClassVar[types.LLMTransportShape]
    _REGISTRY: t.ClassVar[dict[types.LLMTransportShape, type["Shape[_ShapeRenderKwargs]"]] | None] = None

    @classmethod
    def _resolve(cls, transport: types.LLMTransportShape) -> type["Shape[_ShapeRenderKwargs]"]:
        """Lazily resolve the variant class registered for *transport*.

        Concrete variants are imported on first call so the side-effect-free
        ``from flama.models.transport.input.llm.shape.base import Shape`` does not pull every
        variant into the import graph. Subsequent calls reuse the cached :attr:`_REGISTRY`.

        :param transport: Shape discriminator.
        :return: :class:`Shape` subclass registered for *transport*.
        :raises ValueError: If *transport* is not a registered variant.
        """
        if cls._REGISTRY is None:
            from flama.models.transport.input.llm.shape.chat import Chat
            from flama.models.transport.input.llm.shape.conversation import Conversation
            from flama.models.transport.input.llm.shape.raw import Raw

            cls._REGISTRY = {"raw": Raw, "chat": Chat, "conversation": Conversation}
        try:
            return cls._REGISTRY[transport]
        except KeyError:
            raise ValueError(f"Wrong shape '{transport}', expected one of: {list(cls._REGISTRY)}") from None

    @classmethod
    def build(
        cls,
        transport: types.LLMTransportShape,
        /,
        **kwargs: compat.Unpack[_ShapeFields],
    ) -> "Shape[_ShapeRenderKwargs]":
        """Dispatch on *transport* and instantiate the matching variant.

        Inputs are forwarded as a :class:`_ShapeFields` bag to the variant. ``None`` values
        are stripped here so callers can pass every potential field uniformly (e.g.
        ``prompt=prompt, system=system, messages=messages``) without having to build a
        conditional bag themselves; the variant's own ``__post_init__`` then extracts and
        validates what it needs after the shared rejection check. Callers are expected to
        pre-convert any sequence-typed input (today: ``messages`` and ``tools``) into its
        immutable form before calling.

        :param transport: The variant discriminator.
        :param kwargs: Variant inputs as a :class:`_ShapeFields` bag.
        :return: A concrete :class:`Shape` instance.
        :raises ValueError: For unknown discriminators, missing required fields, type mismatches,
            or fields that are not valid for the chosen variant.
        """
        fields = t.cast(_ShapeFields, {k: v for k, v in kwargs.items() if v is not None})
        return cls._resolve(transport)(fields=fields)

    def __post_init__(self, fields: _ShapeFields | None) -> None:
        """Reject any key in *fields* that is not declared as a field on the concrete variant.

        Variants override this method to perform their own field extraction and validation; they
        must call ``super().__post_init__(fields)`` first to inherit the shared rejection check.
        The allow-list is derived from :func:`dataclasses.fields` of the concrete variant, so
        the set of accepted keys is always in sync with its declared attributes.

        :param fields: Bag of inputs forwarded by :meth:`build` (or supplied directly).
        :raises ValueError: When *fields* contains keys that are not attributes of the variant.
        """
        if not fields:
            return
        allowed = {f.name for f in dataclasses.fields(self.__class__)}
        unknown = [k for k in fields if k not in allowed]
        if unknown:
            formatted = ", ".join(f"'{k}'" for k in unknown)
            verb = "are" if len(unknown) > 1 else "is"
            raise ValueError(f"{formatted} {verb} not allowed when transport is '{self.transport}'")

    @abc.abstractmethod
    async def render(self, backend: "LLMBackend", /, **kwargs: compat.Unpack[_SK]) -> "EngineInput":
        """Convert this transport to engine-ready :class:`EngineInput` using *backend*.

        Returning structured inputs (not raw token IDs) keeps the multimodal pipeline uniform:
        text-only transports build :class:`EngineInput` directly from the tokenizer output,
        while templated transports delegate to :meth:`LLMBackend.prepare_input` so the
        backend's chat-template renderer (a vision processor on multimodal-capable backends)
        can produce token IDs aligned with image placeholders.

        :param backend: LLM backend exposing ``encode``, ``apply_chat_template`` and
            ``chat_template``.
        :param kwargs: Variant-specific render kwargs typed by ``_SK`` (chat-template knobs for
            templated transports; ignored by ``Raw``).
        :return: Engine-ready :class:`EngineInput` ready to be fed to
            :meth:`LLMBackend.generate`.
        :raises ValueError: If a templated transport is requested but the backend has no chat
            template, or a multimodal payload references a modality that is not advertised by
            the backend's :attr:`~LLMBackend.capabilities`.
        """
        ...
