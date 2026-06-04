import typing as t

from pydantic import BaseModel, ConfigDict, Field

from flama.schemas._libs.pydantic.schemas.core import SCHEMAS

__all__ = [
    "AudioURIPart",
    "AudioURLPart",
    "Event",
    "ConfigureInput",
    "ConfigureOutput",
    "ContentPart",
    "ImageURIPart",
    "ImageURLPart",
    "Message",
    "NativeUsage",
    "QueryInput",
    "QueryOutput",
    "StreamInput",
    "StreamOutput",
    "TextEvent",
    "TextPart",
    "Tool",
    "ToolEvent",
    "ToolCall",
    "ToolCallFunction",
    "ToolFunction",
]


class TextPart(BaseModel):
    type: t.Literal["text"] = Field(default="text", title="type", description="Content part kind discriminator.")
    text: str = Field(title="text", description="Plain-text fragment.")


SCHEMAS["flama.llm_native.TextPart"] = TextPart


class ImageURLPart(BaseModel):
    type: t.Literal["image:url"] = Field(
        default="image:url", title="type", description="Content part kind discriminator."
    )
    url: str = Field(title="url", description="HTTP/HTTPS URL fetched at decode time.")


SCHEMAS["flama.llm_native.ImageURLPart"] = ImageURLPart


class ImageURIPart(BaseModel):
    type: t.Literal["image:uri"] = Field(
        default="image:uri", title="type", description="Content part kind discriminator."
    )
    data: str = Field(title="data", description="Base64-encoded image bytes.")
    format: t.Literal["png", "jpeg", "gif", "webp"] = Field(title="format", description="Image codec hint.")


SCHEMAS["flama.llm_native.ImageURIPart"] = ImageURIPart


class AudioURLPart(BaseModel):
    type: t.Literal["audio:url"] = Field(
        default="audio:url", title="type", description="Content part kind discriminator."
    )
    url: str = Field(title="url", description="HTTP/HTTPS URL fetched at decode time.")


SCHEMAS["flama.llm_native.AudioURLPart"] = AudioURLPart


class AudioURIPart(BaseModel):
    type: t.Literal["audio:uri"] = Field(
        default="audio:uri", title="type", description="Content part kind discriminator."
    )
    data: str = Field(title="data", description="Base64-encoded audio bytes.")
    format: t.Literal["wav", "mp3", "flac", "ogg"] = Field(title="format", description="Audio codec hint.")


SCHEMAS["flama.llm_native.AudioURIPart"] = AudioURIPart


ContentPart = t.Annotated[
    TextPart | ImageURLPart | ImageURIPart | AudioURLPart | AudioURIPart,
    Field(discriminator="type"),
]


class ToolFunction(BaseModel):
    """Function-tool spec advertised to the model (``tools[].function``)."""

    model_config = ConfigDict(extra="allow")

    name: str = Field(title="name", description="Function name advertised to the model.")
    description: str | None = Field(
        default=None, title="description", description="Optional human-readable description."
    )
    parameters: dict[str, t.Any] = Field(
        default_factory=dict,
        title="parameters",
        description="JSON Schema object describing the function arguments.",
    )


SCHEMAS["flama.llm_native.ToolFunction"] = ToolFunction


class ToolCallFunction(BaseModel):
    """Function-call payload issued by the assistant (``tool_calls[].function``)."""

    name: str = Field(title="name", description="Function name the model is requesting to invoke.")
    arguments: str | dict[str, t.Any] = Field(
        title="arguments",
        description="Function arguments, either a JSON-encoded string (OpenAI default) or a parsed object.",
    )


SCHEMAS["flama.llm_native.ToolCallFunction"] = ToolCallFunction


class ToolCall(BaseModel):
    """Assistant-issued tool call.

    OpenAI-style requests / responses set ``id`` and ``type``; Ollama-style payloads omit them
    (Ollama's wire format only carries ``function``). Both are valid here so the same ``Message``
    schema can describe both dialects.
    """

    id: str | None = Field(default=None, title="id", description="Tool call identifier (OpenAI dialect only)")
    type: t.Literal["function"] = Field(default="function", title="type", description="Tool call kind discriminator")
    function: ToolCallFunction = Field(
        title="function",
        description="Function payload (name + arguments) the model is requesting to invoke",
    )


SCHEMAS["flama.llm_native.ToolCall"] = ToolCall


class Message(BaseModel):
    """Conversation turn shared across native, OpenAI, and Ollama input schemas.

    ``extra="allow"`` keeps Ollama's sibling ``images: list[base64]`` (and any future dialect extras) flowing
    through the validator unchanged so
    :meth:`flama.models.wire.dialect.llm.ollama.parser.OllamaParser._canonicalize_message` can reshape them
    into structured content parts before backend dispatch.
    """

    model_config = ConfigDict(extra="allow")

    role: t.Literal["system", "user", "assistant", "tool"] = Field(title="role", description="Message role")
    content: str | list[ContentPart] | None = Field(
        default=None,
        title="content",
        description=(
            "Message content. Either a plain string (legacy text shape) or a list of typed content parts "
            "(``TextPart`` / ``ImageURLPart`` / ``ImageURIPart`` / ``AudioURLPart`` / ``AudioURIPart``). "
            "Structured shape is only valid on user messages. May be omitted on assistant turns that only "
            "emit tool_calls."
        ),
    )
    tool_calls: list[ToolCall] | None = Field(
        default=None,
        title="tool_calls",
        description="Tool calls issued by the assistant turn (assistant role only)",
    )
    tool_call_id: str | None = Field(
        default=None,
        title="tool_call_id",
        description="Identifier of the tool call this turn responds to (tool role only)",
    )
    thinking: str | None = Field(
        default=None,
        title="thinking",
        description=(
            "Concatenated chain-of-thought emitted by the assistant turn (assistant role only). Populated when "
            "the model produced reasoning blocks on a non-output channel; absent or null when the model didn't "
            "emit any thinking. Distinct from ``content``, which carries the user-visible answer."
        ),
    )


SCHEMAS["flama.llm_native.Message"] = Message


class Tool(BaseModel):
    type: t.Literal["function"] = Field(default="function", title="type", description="Tool kind discriminator")
    function: ToolFunction = Field(
        title="function",
        description="Function spec: name, optional description, and JSON Schema parameters object",
    )


SCHEMAS["flama.llm_native.Tool"] = Tool


class TextEvent(BaseModel):
    type: t.Literal["text"] = Field(default="text", title="type", description="Block kind discriminator")
    channel: str | None = Field(
        default=None,
        title="channel",
        description=(
            "Channel discriminator. ``'output'`` for the user-visible answer; an arbitrary captured name "
            "(e.g. ``'analysis'``, ``'thought'``) for meta-content; ``null`` when the model's marker "
            "captured no identity at all."
        ),
    )
    text: str = Field(title="text", description="Block text content")


SCHEMAS["flama.llm_native.TextEvent"] = TextEvent


class ToolEvent(BaseModel):
    type: t.Literal["tool"] = Field(default="tool", title="type", description="Block kind discriminator")
    id: str = Field(title="id", description="Tool call identifier")
    name: str = Field(title="name", description="Function name the model is requesting to invoke")
    arguments: dict[str, t.Any] = Field(
        default_factory=dict, title="arguments", description="Parsed JSON arguments object"
    )


SCHEMAS["flama.llm_native.ToolEvent"] = ToolEvent


Event = t.Annotated[TextEvent | ToolEvent, Field(discriminator="type")]


class NativeUsage(BaseModel):
    input_tokens: int = Field(title="input_tokens", description="Prompt token count.")
    output_tokens: int = Field(title="output_tokens", description="Completion token count.")


SCHEMAS["flama.llm_native.NativeUsage"] = NativeUsage


class ConfigureInput(BaseModel):
    params: dict[str, t.Any] = Field(title="params", description="Generation parameters")


SCHEMAS["flama.llm_native.ConfigureInput"] = ConfigureInput


class ConfigureOutput(BaseModel):
    params: dict[str, t.Any] = Field(title="params", description="Current generation parameters")


SCHEMAS["flama.llm_native.ConfigureOutput"] = ConfigureOutput


class QueryInput(BaseModel):
    transport: t.Literal["raw", "chat", "conversation"] | None = Field(
        default=None,
        title="transport",
        description="Input shape: raw (verbatim), chat (templated single-turn), conversation (templated multi-turn). "
        "If omitted, the model's default transport is used.",
    )
    prompt: str | None = Field(default=None, title="prompt", description="Input prompt for raw or chat transport.")
    system: str | None = Field(default=None, title="system", description="Optional system instruction for chat.")
    messages: list[Message] | None = Field(
        default=None, title="messages", description="Conversation history for conversation transport."
    )
    tools: list[Tool] | None = Field(
        default=None,
        title="tools",
        description="Function-tool specs advertised to the model (templated transports only).",
    )
    params: dict[str, t.Any] = Field(
        default_factory=dict,
        title="params",
        description=(
            "Generation parameters override. ``max_tokens`` may be omitted or set to null to let the engine "
            "generate until natural completion (EOS) bounded only by the model's context window; pass a positive "
            "integer to enforce a hard cap. Non-positive values are rejected."
        ),
    )
    chat_template_kwargs: dict[str, t.Any] | None = Field(
        default=None,
        title="chat_template_kwargs",
        description="Extra keyword arguments forwarded to the tokenizer's chat template",
    )


SCHEMAS["flama.llm_native.QueryInput"] = QueryInput


class QueryOutput(BaseModel):
    id: str = Field(title="id", description="Generation identifier")
    created: int = Field(title="created", description="Unix timestamp at which the generation completed")
    blocks: list[Event] = Field(title="blocks", description="Channel-tagged output blocks (text or tool)")
    stop_reason: str | None = Field(
        default=None, title="stop_reason", description="Why generation ended (e.g. stop, error, max_tokens)"
    )
    usage: NativeUsage | None = Field(
        default=None,
        title="usage",
        description="Token usage tally (input_tokens, output_tokens) when the backend exposes it",
    )


SCHEMAS["flama.llm_native.QueryOutput"] = QueryOutput


class StreamInput(BaseModel):
    transport: t.Literal["raw", "chat", "conversation"] | None = Field(
        default=None,
        title="transport",
        description="Input shape: raw (verbatim), chat (templated single-turn), conversation (templated multi-turn). "
        "If omitted, the model's default transport is used.",
    )
    prompt: str | None = Field(default=None, title="prompt", description="Input prompt for raw or chat transport.")
    system: str | None = Field(default=None, title="system", description="Optional system instruction for chat.")
    messages: list[Message] | None = Field(
        default=None, title="messages", description="Conversation history for conversation transport."
    )
    tools: list[Tool] | None = Field(
        default=None,
        title="tools",
        description="Function-tool specs advertised to the model (templated transports only).",
    )
    params: dict[str, t.Any] = Field(
        default_factory=dict,
        title="params",
        description=(
            "Generation parameters override. ``max_tokens`` may be omitted or set to null to let the engine "
            "generate until natural completion (EOS) bounded only by the model's context window; pass a positive "
            "integer to enforce a hard cap. Non-positive values are rejected."
        ),
    )
    chat_template_kwargs: dict[str, t.Any] | None = Field(
        default=None,
        title="chat_template_kwargs",
        description="Extra keyword arguments forwarded to the tokenizer's chat template",
    )


SCHEMAS["flama.llm_native.StreamInput"] = StreamInput


class StreamOutput(BaseModel):
    id: str = Field(
        title="id",
        description="Generation identifier; consume the stream via GET /stream/{id}/ as Server-Sent Events.",
    )


SCHEMAS["flama.llm_native.StreamOutput"] = StreamOutput
