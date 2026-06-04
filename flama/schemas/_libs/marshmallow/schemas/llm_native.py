import typing as t

import marshmallow

from flama.schemas._libs.marshmallow.schemas.core import SCHEMAS

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


class TextPart(marshmallow.Schema):
    type = marshmallow.fields.String(
        load_default="text",
        validate=marshmallow.validate.OneOf(("text",)),
        metadata={"title": "type", "description": "Content part kind discriminator."},
    )
    text = marshmallow.fields.String(
        required=True,
        metadata={"title": "text", "description": "Plain-text fragment."},
    )


SCHEMAS["flama.llm_native.TextPart"] = TextPart


class ImageURLPart(marshmallow.Schema):
    type = marshmallow.fields.String(
        load_default="image:url",
        validate=marshmallow.validate.OneOf(("image:url",)),
        metadata={"title": "type", "description": "Content part kind discriminator."},
    )
    url = marshmallow.fields.String(
        required=True,
        metadata={"title": "url", "description": "HTTP/HTTPS URL fetched at decode time."},
    )


SCHEMAS["flama.llm_native.ImageURLPart"] = ImageURLPart


class ImageURIPart(marshmallow.Schema):
    type = marshmallow.fields.String(
        load_default="image:uri",
        validate=marshmallow.validate.OneOf(("image:uri",)),
        metadata={"title": "type", "description": "Content part kind discriminator."},
    )
    data = marshmallow.fields.String(
        required=True,
        metadata={"title": "data", "description": "Base64-encoded image bytes."},
    )
    format = marshmallow.fields.String(
        required=True,
        validate=marshmallow.validate.OneOf(("png", "jpeg", "gif", "webp")),
        metadata={"title": "format", "description": "Image codec hint."},
    )


SCHEMAS["flama.llm_native.ImageURIPart"] = ImageURIPart


class AudioURLPart(marshmallow.Schema):
    type = marshmallow.fields.String(
        load_default="audio:url",
        validate=marshmallow.validate.OneOf(("audio:url",)),
        metadata={"title": "type", "description": "Content part kind discriminator."},
    )
    url = marshmallow.fields.String(
        required=True,
        metadata={"title": "url", "description": "HTTP/HTTPS URL fetched at decode time."},
    )


SCHEMAS["flama.llm_native.AudioURLPart"] = AudioURLPart


class AudioURIPart(marshmallow.Schema):
    type = marshmallow.fields.String(
        load_default="audio:uri",
        validate=marshmallow.validate.OneOf(("audio:uri",)),
        metadata={"title": "type", "description": "Content part kind discriminator."},
    )
    data = marshmallow.fields.String(
        required=True,
        metadata={"title": "data", "description": "Base64-encoded audio bytes."},
    )
    format = marshmallow.fields.String(
        required=True,
        validate=marshmallow.validate.OneOf(("wav", "mp3", "flac", "ogg")),
        metadata={"title": "format", "description": "Audio codec hint."},
    )


SCHEMAS["flama.llm_native.AudioURIPart"] = AudioURIPart


_CONTENT_PART_SCHEMAS: t.Final[dict[str, type[marshmallow.Schema]]] = {
    "text": TextPart,
    "image:url": ImageURLPart,
    "image:uri": ImageURIPart,
    "audio:url": AudioURLPart,
    "audio:uri": AudioURIPart,
}


class ContentPart(marshmallow.fields.Field):
    """Discriminated-union field over :data:`flama.models.transport.input.llm.message.ContentPart` shapes.

    Validates structured-content parts inside :class:`Message.content`. Dispatch is driven by the
    ``type`` discriminator: each value is delegated to the matching ``*Part`` schema's :meth:`load`
    so per-arm field constraints (string formats, codec literals, ...) are enforced uniformly. The
    OpenAPI emission exposes the union as ``oneOf`` plus the ``discriminator`` keyword so doc
    consumers see the same shape pydantic emits.
    """

    def _deserialize(
        self, value: t.Any, attr: str | None, data: t.Mapping[str, t.Any] | None, **kwargs: t.Any
    ) -> dict[str, t.Any]:
        if not isinstance(value, dict):
            raise marshmallow.ValidationError("content parts must be objects")
        kind = value.get("type")
        schema_cls = _CONTENT_PART_SCHEMAS.get(kind)
        if schema_cls is None:
            raise marshmallow.ValidationError(
                f"Wrong content part type {kind!r}, expected one of: {sorted(_CONTENT_PART_SCHEMAS)}"
            )
        return t.cast(dict[str, t.Any], schema_cls().load(value))

    def _jsonschema_type_mapping(self) -> dict[str, t.Any]:
        return {
            "oneOf": [{"$ref": f"#/components/schemas/{cls.__name__}"} for cls in _CONTENT_PART_SCHEMAS.values()],
            "discriminator": {
                "propertyName": "type",
                "mapping": {tag: f"#/components/schemas/{cls.__name__}" for tag, cls in _CONTENT_PART_SCHEMAS.items()},
            },
        }


class ToolFunction(marshmallow.Schema):
    class Meta:
        unknown = marshmallow.INCLUDE

    name = marshmallow.fields.String(
        required=True,
        metadata={"title": "name", "description": "Function name advertised to the model."},
    )
    description = marshmallow.fields.String(
        load_default=None,
        allow_none=True,
        metadata={"title": "description", "description": "Optional human-readable description."},
    )
    parameters = marshmallow.fields.Dict(
        load_default=dict,
        metadata={
            "title": "parameters",
            "description": "JSON Schema object describing the function arguments.",
        },
    )


SCHEMAS["flama.llm_native.ToolFunction"] = ToolFunction


class ToolCallFunction(marshmallow.Schema):
    name = marshmallow.fields.String(
        required=True,
        metadata={"title": "name", "description": "Function name the model is requesting to invoke."},
    )
    arguments = marshmallow.fields.Raw(
        required=True,
        metadata={
            "title": "arguments",
            "description": "Function arguments, either a JSON-encoded string (OpenAI default) or a parsed object.",
        },
    )


SCHEMAS["flama.llm_native.ToolCallFunction"] = ToolCallFunction


class ToolCall(marshmallow.Schema):
    """Assistant-issued tool call.

    OpenAI-style requests / responses set ``id`` and ``type``; Ollama-style payloads omit them
    (Ollama's wire format only carries ``function``). Both are valid here so the same ``Message``
    schema can describe both dialects.
    """

    id = marshmallow.fields.String(
        load_default=None,
        allow_none=True,
        metadata={"title": "id", "description": "Tool call identifier (OpenAI dialect only)"},
    )
    type = marshmallow.fields.String(
        load_default="function",
        validate=marshmallow.validate.OneOf(("function",)),
        metadata={"title": "type", "description": "Tool call kind discriminator"},
    )
    function = marshmallow.fields.Nested(
        ToolCallFunction,
        required=True,
        metadata={
            "title": "function",
            "description": "Function payload (name + arguments) the model is requesting to invoke",
        },
    )


SCHEMAS["flama.llm_native.ToolCall"] = ToolCall


class Message(marshmallow.Schema):
    """Conversation turn shared across native, OpenAI, and Ollama input schemas.

    ``unknown=INCLUDE`` keeps Ollama's sibling ``images: list[base64]`` (and any future dialect extras) flowing
    through the validator unchanged so
    :meth:`flama.models.wire.dialect.llm.ollama.parser.OllamaParser._canonicalize_message` can reshape them
    into structured content parts before backend dispatch.
    """

    class Meta:
        unknown = marshmallow.INCLUDE

    role = marshmallow.fields.String(
        required=True,
        validate=marshmallow.validate.OneOf(("system", "user", "assistant", "tool")),
        metadata={"title": "role", "description": "Message role"},
    )
    content = marshmallow.fields.Raw(
        load_default=None,
        allow_none=True,
        metadata={
            "title": "content",
            "description": (
                "Message content. Either a plain string (legacy text shape) or a list of typed content parts "
                "(``TextPart`` / ``ImageURLPart`` / ``ImageURIPart`` / ``AudioURLPart`` / ``AudioURIPart``). "
                "Structured shape is only valid on user messages. May be omitted on assistant turns that only "
                "emit tool_calls."
            ),
        },
    )
    tool_calls = marshmallow.fields.List(
        marshmallow.fields.Nested(ToolCall()),
        load_default=None,
        allow_none=True,
        metadata={
            "title": "tool_calls",
            "description": "Tool calls issued by the assistant turn (assistant role only)",
        },
    )
    tool_call_id = marshmallow.fields.String(
        load_default=None,
        allow_none=True,
        metadata={
            "title": "tool_call_id",
            "description": "Identifier of the tool call this turn responds to (tool role only)",
        },
    )
    thinking = marshmallow.fields.String(
        load_default=None,
        allow_none=True,
        metadata={
            "title": "thinking",
            "description": (
                "Concatenated chain-of-thought emitted by the assistant turn (assistant role only). Populated "
                "when the model produced reasoning blocks on a non-output channel; absent or null when the "
                "model didn't emit any thinking. Distinct from ``content``, which carries the user-visible answer."
            ),
        },
    )


SCHEMAS["flama.llm_native.Message"] = Message


class Tool(marshmallow.Schema):
    type = marshmallow.fields.String(
        load_default="function",
        validate=marshmallow.validate.OneOf(("function",)),
        metadata={"title": "type", "description": "Tool kind discriminator"},
    )
    function = marshmallow.fields.Nested(
        ToolFunction,
        required=True,
        metadata={
            "title": "function",
            "description": "Function spec: name, optional description, and JSON Schema parameters object",
        },
    )


SCHEMAS["flama.llm_native.Tool"] = Tool


class TextEvent(marshmallow.Schema):
    type = marshmallow.fields.String(
        load_default="text",
        validate=marshmallow.validate.OneOf(("text",)),
        metadata={"title": "type", "description": "Block kind discriminator"},
    )
    channel = marshmallow.fields.String(
        load_default=None,
        allow_none=True,
        metadata={
            "title": "channel",
            "description": (
                "Channel discriminator. ``'output'`` for the user-visible answer; an arbitrary captured name "
                "(e.g. ``'analysis'``, ``'thought'``) for meta-content; ``null`` when the model's marker "
                "captured no identity at all."
            ),
        },
    )
    text = marshmallow.fields.String(
        required=True,
        metadata={"title": "text", "description": "Block text content"},
    )


SCHEMAS["flama.llm_native.TextEvent"] = TextEvent


class ToolEvent(marshmallow.Schema):
    type = marshmallow.fields.String(
        load_default="tool",
        validate=marshmallow.validate.OneOf(("tool",)),
        metadata={"title": "type", "description": "Block kind discriminator"},
    )
    id = marshmallow.fields.String(required=True, metadata={"title": "id", "description": "Tool call identifier"})
    name = marshmallow.fields.String(
        required=True,
        metadata={"title": "name", "description": "Function name the model is requesting to invoke"},
    )
    arguments = marshmallow.fields.Dict(
        load_default=dict,
        metadata={"title": "arguments", "description": "Parsed JSON arguments object"},
    )


SCHEMAS["flama.llm_native.ToolEvent"] = ToolEvent


_BLOCK_SCHEMAS: t.Final[dict[str, type[marshmallow.Schema]]] = {
    "text": TextEvent,
    "tool": ToolEvent,
}


class Event(marshmallow.fields.Field):
    """Discriminated-union field over :class:`TextEvent` and :class:`ToolEvent`.

    Mirrors :data:`flama.models.Event` for OpenAPI emission and HTTP-side validation. Dispatch
    is driven by the ``type`` discriminator: ``text`` blocks are decoded by :class:`TextEvent` and
    ``tool`` blocks by :class:`ToolEvent`.
    """

    def _deserialize(
        self, value: t.Any, attr: str | None, data: t.Mapping[str, t.Any] | None, **kwargs: t.Any
    ) -> dict[str, t.Any]:
        if not isinstance(value, dict):
            raise marshmallow.ValidationError("blocks must be objects")
        kind = value.get("type")
        schema_cls = _BLOCK_SCHEMAS.get(kind)
        if schema_cls is None:
            raise marshmallow.ValidationError(f"Wrong block type {kind!r}, expected one of: {sorted(_BLOCK_SCHEMAS)}")
        return t.cast(dict[str, t.Any], schema_cls().load(value))

    def _jsonschema_type_mapping(self) -> dict[str, t.Any]:
        return {
            "oneOf": [{"$ref": f"#/components/schemas/{cls.__name__}"} for cls in _BLOCK_SCHEMAS.values()],
            "discriminator": {
                "propertyName": "type",
                "mapping": {tag: f"#/components/schemas/{cls.__name__}" for tag, cls in _BLOCK_SCHEMAS.items()},
            },
        }


class NativeUsage(marshmallow.Schema):
    input_tokens = marshmallow.fields.Integer(
        required=True,
        metadata={"title": "input_tokens", "description": "Prompt token count."},
    )
    output_tokens = marshmallow.fields.Integer(
        required=True,
        metadata={"title": "output_tokens", "description": "Completion token count."},
    )


SCHEMAS["flama.llm_native.NativeUsage"] = NativeUsage


class ConfigureInput(marshmallow.Schema):
    params = marshmallow.fields.Dict(
        required=True,
        metadata={"title": "params", "description": "Generation parameters"},
    )


SCHEMAS["flama.llm_native.ConfigureInput"] = ConfigureInput


class ConfigureOutput(marshmallow.Schema):
    params = marshmallow.fields.Dict(
        required=True,
        metadata={"title": "params", "description": "Current generation parameters"},
    )


SCHEMAS["flama.llm_native.ConfigureOutput"] = ConfigureOutput


class QueryInput(marshmallow.Schema):
    transport = marshmallow.fields.String(
        load_default=None,
        allow_none=True,
        validate=marshmallow.validate.OneOf(("raw", "chat", "conversation")),
        metadata={
            "title": "transport",
            "description": (
                "Input shape: raw (verbatim), chat (templated single-turn), conversation (templated multi-turn). "
                "If omitted, the model's default transport is used."
            ),
        },
    )
    prompt = marshmallow.fields.String(
        load_default=None,
        allow_none=True,
        metadata={"title": "prompt", "description": "Input prompt for raw or chat transport."},
    )
    system = marshmallow.fields.String(
        load_default=None,
        allow_none=True,
        metadata={"title": "system", "description": "Optional system instruction for chat."},
    )
    messages = marshmallow.fields.List(
        marshmallow.fields.Nested(Message()),
        load_default=None,
        allow_none=True,
        metadata={"title": "messages", "description": "Conversation history for conversation transport."},
    )
    tools = marshmallow.fields.List(
        marshmallow.fields.Nested(Tool()),
        load_default=None,
        allow_none=True,
        metadata={
            "title": "tools",
            "description": "Function-tool specs advertised to the model (templated transports only)",
        },
    )
    params = marshmallow.fields.Dict(
        load_default={},
        metadata={
            "title": "params",
            "description": (
                "Generation parameters override. ``max_tokens`` may be omitted or set to null to let the engine "
                "generate until natural completion (EOS) bounded only by the model's context window; pass a "
                "positive integer to enforce a hard cap. Non-positive values are rejected."
            ),
        },
    )
    chat_template_kwargs = marshmallow.fields.Dict(
        load_default=None,
        allow_none=True,
        metadata={
            "title": "chat_template_kwargs",
            "description": "Extra keyword arguments forwarded to the tokenizer's chat template",
        },
    )


SCHEMAS["flama.llm_native.QueryInput"] = QueryInput


class QueryOutput(marshmallow.Schema):
    id = marshmallow.fields.String(required=True, metadata={"title": "id", "description": "Generation identifier"})
    created = marshmallow.fields.Integer(
        required=True,
        metadata={"title": "created", "description": "Unix timestamp at which the generation completed"},
    )
    blocks = marshmallow.fields.List(
        Event(),
        required=True,
        metadata={"title": "blocks", "description": "Channel-tagged output blocks (text or tool)"},
    )
    stop_reason = marshmallow.fields.String(
        load_default=None,
        allow_none=True,
        metadata={
            "title": "stop_reason",
            "description": "Why generation ended (e.g. stop, error, max_tokens)",
        },
    )
    usage = marshmallow.fields.Nested(
        NativeUsage,
        load_default=None,
        allow_none=True,
        metadata={
            "title": "usage",
            "description": "Token usage tally (input_tokens, output_tokens) when the backend exposes it",
        },
    )


SCHEMAS["flama.llm_native.QueryOutput"] = QueryOutput


class StreamInput(marshmallow.Schema):
    transport = marshmallow.fields.String(
        load_default=None,
        allow_none=True,
        validate=marshmallow.validate.OneOf(("raw", "chat", "conversation")),
        metadata={
            "title": "transport",
            "description": (
                "Input shape: raw (verbatim), chat (templated single-turn), conversation (templated multi-turn). "
                "If omitted, the model's default transport is used."
            ),
        },
    )
    prompt = marshmallow.fields.String(
        load_default=None,
        allow_none=True,
        metadata={"title": "prompt", "description": "Input prompt for raw or chat transport."},
    )
    system = marshmallow.fields.String(
        load_default=None,
        allow_none=True,
        metadata={"title": "system", "description": "Optional system instruction for chat."},
    )
    messages = marshmallow.fields.List(
        marshmallow.fields.Nested(Message()),
        load_default=None,
        allow_none=True,
        metadata={"title": "messages", "description": "Conversation history for conversation transport."},
    )
    tools = marshmallow.fields.List(
        marshmallow.fields.Nested(Tool()),
        load_default=None,
        allow_none=True,
        metadata={
            "title": "tools",
            "description": "Function-tool specs advertised to the model (templated transports only)",
        },
    )
    params = marshmallow.fields.Dict(
        load_default={},
        metadata={
            "title": "params",
            "description": (
                "Generation parameters override. ``max_tokens`` may be omitted or set to null to let the engine "
                "generate until natural completion (EOS) bounded only by the model's context window; pass a "
                "positive integer to enforce a hard cap. Non-positive values are rejected."
            ),
        },
    )
    chat_template_kwargs = marshmallow.fields.Dict(
        load_default=None,
        allow_none=True,
        metadata={
            "title": "chat_template_kwargs",
            "description": "Extra keyword arguments forwarded to the tokenizer's chat template",
        },
    )


SCHEMAS["flama.llm_native.StreamInput"] = StreamInput


class StreamOutput(marshmallow.Schema):
    id = marshmallow.fields.String(
        required=True,
        metadata={
            "title": "id",
            "description": "Generation identifier; consume the stream via GET /stream/{id}/ as Server-Sent Events.",
        },
    )


SCHEMAS["flama.llm_native.StreamOutput"] = StreamOutput
