import typing as t

from flama import types
from flama.models.resources.serving.base import Serving
from flama.models.transport.input.llm.message import Message
from flama.models.transport.input.llm.tool import Tool
from flama.models.wire.dialect.base import Dialect

__all__ = ["LLMServing"]


class LLMServing(Serving):
    """Base class for LLM HTTP serving layers (route registration only).

    Wire ↔ transport parsing lives on :class:`~flama.models.wire.dialect.base.Dialect` subclasses under
    ``flama.models.wire.dialect``. Concrete servings (e.g. :class:`NativeServing`) compose route mixins
    and bind a :attr:`DIALECT` class attribute; :meth:`parse` defaults to delegating to the bound
    dialect.
    """

    DIALECT: t.ClassVar[type[Dialect]]
    _REGISTRY: t.ClassVar[dict[types.LLMServing, type["LLMServing"]] | None] = None

    @classmethod
    def _resolve(cls, serving: types.LLMServing) -> type["LLMServing"]:
        """Lazily resolve the serving class registered for *serving*.

        Concrete layers are imported on first call so the side-effect-free
        ``from flama.models.resources.serving.llm.base import LLMServing`` does not pull every
        layer into the import graph. Subsequent calls reuse the cached :attr:`_REGISTRY`.

        :param serving: Serving layer name to resolve.
        :return: Serving class registered for *serving*.
        :raises KeyError: If *serving* is not a registered layer.
        """
        if cls._REGISTRY is None:
            from flama.models.resources.serving.llm.anthropic import AnthropicServing
            from flama.models.resources.serving.llm.native import NativeServing
            from flama.models.resources.serving.llm.ollama import OllamaServing
            from flama.models.resources.serving.llm.openai import OpenAIServing

            cls._REGISTRY = {
                "native": NativeServing,
                "openai": OpenAIServing,
                "ollama": OllamaServing,
                "anthropic": AnthropicServing,
            }
        return cls._REGISTRY[serving]

    @t.overload
    @classmethod
    def parse(
        cls,
        value: list[dict[str, t.Any]],
        /,
        *,
        kind: t.Literal["messages"],
        system: t.Any = None,
    ) -> tuple[Message, ...]: ...
    @t.overload
    @classmethod
    def parse(cls, value: list[t.Any], /, *, kind: t.Literal["tools"]) -> tuple[Tool, ...]: ...
    @classmethod
    def parse(
        cls,
        value: t.Any,
        /,
        *,
        kind: t.Literal["messages", "tools"],
        system: t.Any = None,
    ) -> tuple[Message, ...] | tuple[Tool, ...]:
        """Translate a dialect-shaped wire payload into a tuple of canonical L2 typed objects.

        Thin forwarder to :meth:`DIALECT.parse <flama.models.wire.dialect.base.Dialect.parse>`. Static
        return-type narrowing is provided by the literal :class:`~typing.overload` declarations.

        :param value: Wire payload — list of message dicts for ``kind="messages"`` or list of tool
            elements for ``kind="tools"``.
        :param kind: ``"messages"`` (-> tuple of :class:`~flama.models.Message`) or ``"tools"``
            (-> tuple of :class:`~flama.models.transport.input.llm.tool.Tool`).
        :param system: Optional top-level system payload accepted alongside ``kind="messages"``;
            consumed only by dialects that carry ``system`` outside the ``messages`` array
            (e.g. Anthropic's ``POST /v1/messages``).
        :raises ValueError: On structural violations propagated from the bound dialect.
        """
        if kind == "messages":
            return cls.DIALECT.parse(value, kind=kind, system=system)
        return cls.DIALECT.parse(value, kind=kind)

    @classmethod
    def _build_method_path(cls, serving: types.LLMServing, base: str) -> str:
        return f"{cls._resolve(serving).PREFIX}{base}"

    @classmethod
    def _build_method_name(cls, serving: types.LLMServing, base: str) -> str:
        return base if serving == "native" else f"{serving}_{base}"
