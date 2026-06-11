import abc
import functools
import logging
import typing as t

from flama import exceptions, types
from flama.models.engine.backend._base import Backend
from flama.models.engine.llm.delta import EngineDelta
from flama.models.engine.llm.input import EngineInput
from flama.models.exceptions import LLMUnsupportedCapability
from flama.models.transport.input.llm.message import (
    AssistantMessage,
    AudioContent,
    Content,
    ImageContent,
    Message,
    TextContent,
    ToolCall,
    ToolMessage,
    UserMessage,
)
from flama.models.transport.input.llm.tool import Tool
from flama.serialize.data_structures import LLMModelCapabilities, ModelArtifact

if t.TYPE_CHECKING:
    import numpy as np
    from PIL.Image import Image as PILImage

__all__ = ["LLMBackend", "TransformerLLMBackend"]

logger = logging.getLogger(__name__)


class LLMBackend(Backend):
    """Abstract base for any LLM runtime.

    Carries family-level concerns only: lazy runtime resolution (:meth:`_resolve`,
    :meth:`runnable`, :meth:`from_model_artifact`), capability advertisement, the canonical L2 to
    L3 :meth:`prepare_input` boundary, raw-text :meth:`encode`, :meth:`generate`, and the
    chat-template introspection contract (:attr:`chat_template`, :meth:`chat_template_sample`,
    :attr:`default_transport`).

    Concrete LLM families extend this class with their own template-rendering machinery.
    Today's only family is :class:`TransformerLLMBackend`, which delegates rendering to the
    HuggingFace ``transformers`` tokenizer / ``AutoProcessor`` stack and is shared by
    :class:`~flama.models.engine.backend.llm.vllm.VLLMBackend` and
    :class:`~flama.models.engine.backend.llm.mlx.MLXBackend`. A non-HuggingFace runtime would
    either extend :class:`LLMBackend` directly or seed a sibling family ABC.
    """

    family: t.ClassVar[types.ModelFamily] = "llm"
    DEFAULT_MAX_TOKENS: t.ClassVar[int] = 4096
    _REGISTRY: t.ClassVar[dict[types.LLMRuntime, type["LLMBackend"]] | None] = None

    @classmethod
    def _resolve(cls) -> type["LLMBackend"]:
        """Lazily resolve the first runnable LLM runtime backend in probe order.

        Concrete backends are imported on first call so the side-effect-free
        ``from flama.models.engine.backend.llm._base import LLMBackend`` does not pull every
        runtime adapter into the import graph. Subsequent calls reuse the cached
        :attr:`_REGISTRY`. Probe order is the registry's insertion order (vLLM before MLX).

        :return: First registered backend class whose :meth:`runnable` reports its framework
            dependencies as importable on the host.
        :raises FrameworkNotInstalled: When no probed runtime is importable on this system.
        """
        if cls._REGISTRY is None:
            from flama.models.engine.backend.llm.mlx import MLXBackend
            from flama.models.engine.backend.llm.vllm import VLLMBackend

            cls._REGISTRY = {
                "vllm": VLLMBackend,
                "mlx": MLXBackend,
            }
        for backend_cls in cls._REGISTRY.values():
            if backend_cls.runnable():
                return backend_cls
        raise exceptions.FrameworkNotInstalled("vllm or mlx-lm")

    @classmethod
    @abc.abstractmethod
    def runnable(cls) -> bool:
        """Return ``True`` when this backend's framework dependencies are importable on the host.

        Probed at backend resolution time by :meth:`_resolve` to pick the first usable runtime.
        Concrete backends typically check the module-level sentinels populated by their
        optional-dep ``try / except`` import block.
        """
        ...

    @classmethod
    def from_model_artifact(cls, artifact: ModelArtifact) -> "LLMBackend":
        """Instantiate the first available LLM runtime backend for this system.

        Engine parameters persisted on :attr:`Metadata.framework.config` and
        :attr:`Metadata.capabilities` are forwarded to the backend constructor.

        :param artifact: Deserialised model artifact.
        :return: Backend instance bound to :attr:`ModelArtifact.model`.
        :raises FrameworkNotInstalled: When no probed runtime is importable on this system.
        """
        return cls._resolve()(
            artifact.model,
            **{"capabilities": artifact.meta.capabilities, **(artifact.meta.framework.config or {})},
        )

    @functools.cached_property
    def capabilities(self) -> LLMModelCapabilities:
        """Modal capabilities advertised by this backend.

        Default: text-only :class:`LLMModelCapabilities`. Concrete backends override this
        :class:`functools.cached_property` to derive capabilities from the wrapped runtime.
        Resolved once per backend instance and cached for the rest of its lifetime.
        """
        return LLMModelCapabilities()

    @functools.cached_property
    def max_context(self) -> int:
        """Architectural ceiling for total tokens (prompt + generation), probed once.

        Calls :meth:`_max_context` to interrogate the underlying runtime; when the probe returns
        :data:`None` (or a non-positive value) a warning is logged and :attr:`DEFAULT_MAX_TOKENS`
        is used so generation never falls back to a model-specific default that would be
        surprising for callers (e.g. mlx-lm's 256 or vLLM's 16).
        """
        probed = self._max_context()
        if probed is None or probed <= 0:
            logger.warning("Cannot determine model context window, using default %d", self.DEFAULT_MAX_TOKENS)
            return self.DEFAULT_MAX_TOKENS
        return probed

    @abc.abstractmethod
    def _max_context(self) -> int | None:
        """Probe the underlying runtime for the model's max context length.

        Concrete backends interrogate framework-specific config attributes (vLLM:
        ``model_config.max_model_len``; MLX: ``model.args.max_position_embeddings``,
        ``model.config.text_config.max_position_embeddings`` for the multimodal variant) and
        return :data:`None` when none of the candidate paths surface a usable value —
        :attr:`max_context` then falls back to :attr:`DEFAULT_MAX_TOKENS` with a warning.
        """
        ...

    def _resolve_max_tokens(self, params: dict[str, t.Any], prompt_tokens: int, /) -> int:
        """Pop ``max_tokens`` / ``max_new_tokens`` from *params* and resolve the omitted /
        :data:`None` case to ``max_context - prompt_tokens``.

        Both backends route through this helper so absent / null ``max_tokens`` consistently
        means "until done" across runtimes — vLLM stops getting its own 16-token default and
        mlx-lm stops getting its 256, and any positive override flows through verbatim. Non-
        positive overrides fail loudly: a 0 or negative ``max_tokens`` is almost always a
        client bug and silently swallowing it would be worse than raising.

        :param params: Mutable kwargs forwarded to the engine; ``max_tokens`` and ``max_new_tokens``
            are consumed.
        :param prompt_tokens: Length of the rendered prompt; subtracted from :attr:`max_context`
            so the resolved cap respects the architectural ceiling.
        :raises ValueError: If the caller passes a non-positive ``max_tokens`` /
            ``max_new_tokens``.
        """
        explicit = params.pop("max_tokens", params.pop("max_new_tokens", None))
        if explicit is None:
            return max(self.max_context - prompt_tokens, 1)
        if not isinstance(explicit, int) or explicit <= 0:
            raise ValueError("max_tokens must be a positive integer")
        return explicit

    @property
    @abc.abstractmethod
    def chat_template(self) -> str | None:
        """The chat template string (Jinja, Mustache, ...) embedded in the model, or :data:`None` for base models."""
        ...

    @property
    def default_transport(self) -> types.LLMTransportShape:
        """Resolve the right default transport for this backend from its chat template.

        Backends advertising a :attr:`chat_template` are instruction-tuned and default to
        ``chat``; the rest (base or continued-pretraining models) default to ``raw``.

        :return: ``"chat"`` if :attr:`chat_template` is set, ``"raw"`` otherwise.
        """
        return "chat" if self.chat_template is not None else "raw"

    @abc.abstractmethod
    def encode(self, text: str, /, *, add_special_tokens: bool = True) -> list[int]:
        """Encode raw text into token IDs.

        :param text: Source text to tokenise.
        :param add_special_tokens: When ``True``, prepend BOS / append EOS as configured by the
            tokenizer.
        :return: Token IDs ready to be fed to :meth:`generate`.
        """
        ...

    @abc.abstractmethod
    async def prepare_input(
        self,
        messages: t.Sequence[Message],
        /,
        *,
        tools: t.Sequence[Tool] | None = None,
        chat_template_kwargs: t.Mapping[str, t.Any] | None = None,
    ) -> EngineInput:
        """Convert canonical L2 messages into an engine-ready :class:`EngineInput`.

        Concrete LLM families implement this method to walk the L2 messages, gate per-modality
        capabilities, resolve any multimodal payloads, and produce token IDs (plus optional
        sidecar payloads) for :meth:`generate`.

        :param messages: Pre-built canonical L2 :class:`Message` instances. Dialect parsing
            happens upstream in each serving's
            :meth:`~flama.models.resources.serving.llm._base.LLMServing.parse`.
        :param tools: Optional canonical L2 :class:`Tool` specs forwarded to the renderer.
        :param chat_template_kwargs: Extra keyword arguments forwarded to the chat template
            (e.g. ``enable_thinking=False`` for Gemma).
        :return: Engine-ready :class:`EngineInput`.
        :raises LLMUnsupportedCapability: If a content part references a modality the
            backend does not advertise.
        :raises ValueError: If a content part carries malformed payload.
        """
        ...

    @abc.abstractmethod
    async def generate(self, inputs: EngineInput, /, **params: t.Any) -> t.AsyncIterator[EngineDelta]:
        """Yield generated deltas for the given engine-ready inputs.

        Each delta carries the new text fragment and, when the engine surfaces them, per-step
        token counts and a final ``finish_reason``. Backends that have no metadata to share
        leave the metadata fields :data:`None`; downstream code treats them as best-effort.

        :param inputs: Engine-ready :class:`EngineInput` (token IDs plus optional decoded
            multimodal payloads).
        :param params: Generation parameters forwarded to the engine (e.g. ``temperature``,
            ``max_tokens``).
        :return: Async iterator of :class:`EngineDelta` instances.
        :raises FrameworkNotInstalled: If the underlying framework is not installed.
        """
        yield EngineDelta()  # pragma: no cover

    def chat_template_sample(self) -> str | None:
        """Render a representative sample of model output for warmup detection.

        Default implementation returns :data:`None`; concrete families with a renderable
        template (e.g. :class:`TransformerLLMBackend`) override this to produce a fragment
        shaped like a real assistant reply with a synthetic tool-call inside, so the decoder
        can scan for marker pairs and probe tool-body parsers.

        :return: Rendered representative sample, or :data:`None` when the backend has no
            renderable template.
        """
        return None


class TransformerLLMBackend(LLMBackend):
    """LLM family that delegates tokenisation and chat-template rendering to the HuggingFace
    ``transformers`` stack.

    All current LLM backends — :class:`~flama.models.engine.backend.llm.vllm.VLLMBackend`,
    :class:`~flama.models.engine.backend.llm.mlx.MLXBackend` — extend this family, since both
    runtimes load HuggingFace-formatted models and dispatch their chat templates through
    :class:`~transformers.PreTrainedTokenizerBase` (text-only) or
    :class:`~transformers.AutoProcessor` (multimodal). Vision- or audio-capable subclasses
    override :attr:`_renderer` to point at the bound :class:`~transformers.AutoProcessor` so
    the same rendering path covers multimodal templates.

    Owns the HuggingFace dialect end-to-end:

    - :meth:`apply_chat_template` adapts the renderer's API to a normalised shape
      (``BatchEncoding`` quirks handled here).
    - :meth:`encode` adapts the tokenizer's raw-text encode primitive.
    - :meth:`_dump_message` / :meth:`_dump_tool` / :meth:`_dump_tool_call` /
      :meth:`_dump_content_part` translate canonical L2 :class:`Message` / :class:`Tool` /
      :class:`Content` / :class:`ToolCall` instances into the HuggingFace
      ``apply_chat_template`` input dict shape. The dialect strings (``"text"``, ``"image"``,
      ``"audio"``, ``"function"``) live exclusively on these classmethods.
    - :meth:`prepare_input` orchestrates the family contract: capability gating, multimodal
      payload resolution into :class:`EngineInput`, dump + tokenise.
    - :meth:`chat_template_sample` reuses the same dump path through :meth:`apply_chat_template`
      with class-level L2 fixtures.
    """

    _SAMPLE_MESSAGES: t.ClassVar[tuple[Message, ...]] = (
        UserMessage(content=(TextContent(text=""),)),
        AssistantMessage(
            content=(TextContent(text=""),),
            reasoning_content="sample",
            tool_calls=(ToolCall(function={"name": "fn", "arguments": {}}),),
        ),
    )
    _SAMPLE_TOOLS: t.ClassVar[tuple[Tool, ...]] = (Tool(name="fn", description="", parameters={}),)

    @property
    @abc.abstractmethod
    def _tokenizer(self) -> t.Any:
        """Return the underlying HuggingFace tokenizer."""
        ...

    @property
    @abc.abstractmethod
    def _renderer(self) -> t.Any:
        """Return the object whose ``apply_chat_template`` is invoked by :meth:`apply_chat_template`.

        Defaults to :attr:`_tokenizer`; vision-capable backends override this to return the bound
        :class:`~transformers.AutoProcessor` so the same code path renders both text-only and
        multimodal templates.
        """
        ...

    @property
    def chat_template(self) -> str | None:
        """The chat template embedded in the tokenizer / processor, or :data:`None` for base models."""
        return getattr(self._renderer, "chat_template", None) or getattr(self._tokenizer, "chat_template", None)

    def encode(self, text: str, /, *, add_special_tokens: bool = True) -> list[int]:
        return list(self._tokenizer.encode(text, add_special_tokens=add_special_tokens))

    @t.overload
    def apply_chat_template(
        self,
        messages: list[dict[str, t.Any]],
        /,
        *,
        tokenize: t.Literal[False],
        add_generation_prompt: bool = True,
        **kwargs,
    ) -> str: ...
    @t.overload
    def apply_chat_template(
        self,
        messages: list[dict[str, t.Any]],
        /,
        *,
        tokenize: t.Literal[True] = True,
        add_generation_prompt: bool = True,
        **kwargs,
    ) -> list[int]: ...
    def apply_chat_template(
        self,
        messages: list[dict[str, t.Any]],
        /,
        *,
        tokenize: bool = True,
        add_generation_prompt: bool = True,
        **kwargs,
    ) -> list[int] | str:
        """Render *messages* through the chat template into token IDs (or a string when ``tokenize=False``).

        :param messages: Ordered list of role/content dicts forming the conversation, already
            shaped per the HuggingFace ``apply_chat_template`` input contract (typically
            produced by :meth:`_dump_message`).
        :param tokenize: When ``True``, return token IDs; when ``False``, return the rendered
            prompt as a string (used by :meth:`chat_template_sample`).
        :param add_generation_prompt: Whether to append the model's "ready for assistant turn"
            marker at the end of the rendered prompt.
        :param kwargs: Extra keyword arguments forwarded verbatim to the underlying chat template
            renderer (e.g. ``enable_thinking=False`` for Gemma).
        :return: Token IDs (when ``tokenize=True``) or the rendered prompt string (when
            ``tokenize=False``).
        :raises ValueError: If the backend has no chat template.
        """
        if self.chat_template is None:
            raise ValueError("Model has no chat template, use transport='raw'")
        rendered = self._renderer.apply_chat_template(
            messages, tokenize=tokenize, add_generation_prompt=add_generation_prompt, **kwargs
        )
        if not tokenize:
            return rendered
        if hasattr(rendered, "keys") and "input_ids" in rendered:
            rendered = rendered["input_ids"]
        return list(rendered)

    @classmethod
    def _dump_content_part(cls, content: Content) -> dict[str, t.Any]:
        """Project an L2 :class:`Content` part into the HuggingFace chat-template input shape."""
        match content:
            case TextContent():
                return {"type": "text", "text": content.text}
            case ImageContent():
                return {"type": "image"}
            case AudioContent():
                return {"type": "audio"}
            case _:
                raise ValueError(f"Unsupported content type: {type(content).__name__}")

    @classmethod
    def _dump_tool_call(cls, tool_call: ToolCall) -> dict[str, t.Any]:
        """Project an L2 :class:`ToolCall` into the HuggingFace chat-template input shape."""
        out: dict[str, t.Any] = {"type": tool_call.type, "function": dict(tool_call.function)}
        if tool_call.id is not None:
            out["id"] = tool_call.id
        return out

    @classmethod
    def _dump_message(cls, message: Message) -> dict[str, t.Any]:
        """Project an L2 :class:`Message` into the HuggingFace chat-template input shape.

        Single-text content collapses to a bare ``content: str`` for compatibility with
        text-only chat templates; multipart content (multimodal or mixed) stays as a list
        of typed parts. ``reasoning_content`` is forwarded verbatim for reasoning-aware
        templates. Role-specific fields (``tool_calls`` / ``reasoning_content`` on assistant
        turns, ``tool_call_id`` on tool turns) are gated by subclass dispatch.
        """
        entry: dict[str, t.Any] = {"role": message.role}
        if message.content is not None:
            parts = [cls._dump_content_part(c) for c in message.content]
            entry["content"] = (
                parts[0]["text"] if len(parts) == 1 and isinstance(message.content[0], TextContent) else parts
            )
        if isinstance(message, AssistantMessage):
            if message.reasoning_content is not None:
                entry["reasoning_content"] = message.reasoning_content
            if message.tool_calls is not None:
                entry["tool_calls"] = [cls._dump_tool_call(tc) for tc in message.tool_calls]
        elif isinstance(message, ToolMessage):
            entry["tool_call_id"] = message.tool_call_id
        return entry

    @classmethod
    def _dump_tool(cls, tool: Tool) -> dict[str, t.Any]:
        """Project an L2 :class:`Tool` into the HuggingFace chat-template input shape."""
        function: dict[str, t.Any] = {"name": tool.name}
        if tool.description is not None:
            function["description"] = tool.description
        function["parameters"] = tool.parameters
        return {"type": tool.type, "function": function}

    async def prepare_input(
        self,
        messages: t.Sequence[Message],
        /,
        *,
        tools: t.Sequence[Tool] | None = None,
        chat_template_kwargs: t.Mapping[str, t.Any] | None = None,
    ) -> EngineInput:
        """Convert canonical L2 messages into an engine-ready :class:`EngineInput`.

        Walks *messages* once: every content part is dispatched against
        :attr:`capabilities` (image/audio gating) and any multimodal payload is resolved via
        :meth:`~flama.models.transport.input.llm.message.ImageContent.image` /
        :meth:`~flama.models.transport.input.llm.message.AudioContent.audio` and appended to
        :attr:`EngineInput.images` / :attr:`EngineInput.audios`. The L2-to-template-input
        projection is delegated to :meth:`_dump_message` / :meth:`_dump_tool` so the
        HuggingFace dialect is anchored in one place.

        :param messages: Pre-built canonical L2 :class:`Message` instances.
        :param tools: Optional canonical L2 :class:`Tool` specs forwarded to the chat template.
        :param chat_template_kwargs: Extra keyword arguments forwarded to the chat template.
        :return: Engine-ready :class:`EngineInput`.
        :raises LLMUnsupportedCapability: If a content part references a modality the
            backend does not advertise.
        :raises ValueError: If a content part carries malformed payload.
        """
        kwargs: dict[str, t.Any] = dict(chat_template_kwargs or {})
        if tools is not None:
            kwargs["tools"] = [self._dump_tool(tool) for tool in tools]

        images: list[PILImage] = []
        audios: list[tuple[np.ndarray, int]] = []
        for msg in messages:
            for content in msg.content or ():
                match content:
                    case ImageContent():
                        if not self.capabilities.image:
                            raise LLMUnsupportedCapability("image")
                        images.append(await content.image())
                    case AudioContent():
                        if not self.capabilities.audio:
                            raise LLMUnsupportedCapability("audio")
                        audios.append(await content.audio())

        template_msgs = [self._dump_message(msg) for msg in messages]
        tokens = list(self.apply_chat_template(template_msgs, **kwargs))
        return EngineInput(tokens=tokens, images=tuple(images), audios=tuple(audios))

    def chat_template_sample(self) -> str | None:
        """Render the class-level L2 fixture through the chat template for warmup detection.

        Produces a fragment shaped like a real assistant reply with a synthetic tool-call (and
        a ``reasoning_content`` field exercised by reasoning-aware templates) so the decoder
        can scan for marker pairs and probe tool-body parsers.

        :return: Rendered representative sample, or :data:`None` when the renderer cannot
            produce one (typically a base model with no chat template).
        """
        try:
            msgs = [self._dump_message(m) for m in self._SAMPLE_MESSAGES]
            tools = [self._dump_tool(tool) for tool in self._SAMPLE_TOOLS]
            return self.apply_chat_template(msgs, tools=tools, tokenize=False, add_generation_prompt=False)
        except Exception:
            return None
