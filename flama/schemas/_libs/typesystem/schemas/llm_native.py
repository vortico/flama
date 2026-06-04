from typesystem import Reference, Schema, fields

from flama.schemas._libs.typesystem.schemas.core import SCHEMAS

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

TextPart = Schema(
    title="TextPart",
    fields={
        "type": fields.Choice(
            title="type", description="Content part kind discriminator.", choices=("text",), default="text"
        ),
        "text": fields.String(title="text", description="Plain-text fragment."),
    },
)
SCHEMAS["flama.llm_native.TextPart"] = TextPart

ImageURLPart = Schema(
    title="ImageURLPart",
    fields={
        "type": fields.Choice(
            title="type",
            description="Content part kind discriminator.",
            choices=("image:url",),
            default="image:url",
        ),
        "url": fields.String(title="url", description="HTTP/HTTPS URL fetched at decode time."),
    },
)
SCHEMAS["flama.llm_native.ImageURLPart"] = ImageURLPart

ImageURIPart = Schema(
    title="ImageURIPart",
    fields={
        "type": fields.Choice(
            title="type",
            description="Content part kind discriminator.",
            choices=("image:uri",),
            default="image:uri",
        ),
        "data": fields.String(title="data", description="Base64-encoded image bytes."),
        "format": fields.Choice(
            title="format", description="Image codec hint.", choices=("png", "jpeg", "gif", "webp")
        ),
    },
)
SCHEMAS["flama.llm_native.ImageURIPart"] = ImageURIPart

AudioURLPart = Schema(
    title="AudioURLPart",
    fields={
        "type": fields.Choice(
            title="type",
            description="Content part kind discriminator.",
            choices=("audio:url",),
            default="audio:url",
        ),
        "url": fields.String(title="url", description="HTTP/HTTPS URL fetched at decode time."),
    },
)
SCHEMAS["flama.llm_native.AudioURLPart"] = AudioURLPart

AudioURIPart = Schema(
    title="AudioURIPart",
    fields={
        "type": fields.Choice(
            title="type",
            description="Content part kind discriminator.",
            choices=("audio:uri",),
            default="audio:uri",
        ),
        "data": fields.String(title="data", description="Base64-encoded audio bytes."),
        "format": fields.Choice(title="format", description="Audio codec hint.", choices=("wav", "mp3", "flac", "ogg")),
    },
)
SCHEMAS["flama.llm_native.AudioURIPart"] = AudioURIPart

ContentPart = fields.Union(
    any_of=[
        Reference(to="flama.llm_native.TextPart", definitions=SCHEMAS),
        Reference(to="flama.llm_native.ImageURLPart", definitions=SCHEMAS),
        Reference(to="flama.llm_native.ImageURIPart", definitions=SCHEMAS),
        Reference(to="flama.llm_native.AudioURLPart", definitions=SCHEMAS),
        Reference(to="flama.llm_native.AudioURIPart", definitions=SCHEMAS),
    ],
)

ToolFunction = Schema(
    title="ToolFunction",
    fields={
        "name": fields.String(title="name", description="Function name advertised to the model."),
        "description": fields.String(
            title="description",
            description="Optional human-readable description.",
            allow_null=True,
            default=None,
        ),
        "parameters": fields.Object(
            title="parameters",
            description="JSON Schema object describing the function arguments.",
            default={},
        ),
    },
)
SCHEMAS["flama.llm_native.ToolFunction"] = ToolFunction

ToolCallFunction = Schema(
    title="ToolCallFunction",
    fields={
        "name": fields.String(title="name", description="Function name the model is requesting to invoke."),
        "arguments": fields.Any(
            title="arguments",
            description="Function arguments, either a JSON-encoded string (OpenAI default) or a parsed object.",
        ),
    },
)
SCHEMAS["flama.llm_native.ToolCallFunction"] = ToolCallFunction

ToolCall = Schema(
    title="ToolCall",
    fields={
        "id": fields.String(
            title="id",
            description="Tool call identifier (OpenAI dialect only)",
            allow_null=True,
            default=None,
        ),
        "type": fields.Choice(
            title="type", description="Tool call kind discriminator", choices=("function",), default="function"
        ),
        "function": Reference(to="flama.llm_native.ToolCallFunction", definitions=SCHEMAS),
    },
)
SCHEMAS["flama.llm_native.ToolCall"] = ToolCall

Message = Schema(
    title="Message",
    fields={
        "role": fields.Choice(
            title="role", description="Message role", choices=("system", "user", "assistant", "tool")
        ),
        "content": fields.Any(
            title="content",
            description=(
                "Message content. Either a plain string (legacy text shape) or a list of typed content parts "
                "(``TextPart`` / ``ImageURLPart`` / ``ImageURIPart`` / ``AudioURLPart`` / ``AudioURIPart``). "
                "Structured shape is only valid on user messages. May be omitted on assistant turns that only "
                "emit tool_calls."
            ),
            allow_null=True,
            default=None,
        ),
        "tool_calls": fields.Array(
            title="tool_calls",
            description="Tool calls issued by the assistant turn (assistant role only)",
            items=Reference(to="flama.llm_native.ToolCall", definitions=SCHEMAS),
            allow_null=True,
            default=None,
        ),
        "tool_call_id": fields.String(
            title="tool_call_id",
            description="Identifier of the tool call this turn responds to (tool role only)",
            allow_null=True,
            default=None,
        ),
        "thinking": fields.String(
            title="thinking",
            description=(
                "Concatenated chain-of-thought emitted by the assistant turn (assistant role only). Populated "
                "when the model produced reasoning blocks on a non-output channel; absent or null when the "
                "model didn't emit any thinking. Distinct from ``content``, which carries the user-visible answer."
            ),
            allow_null=True,
            default=None,
        ),
    },
)
SCHEMAS["flama.llm_native.Message"] = Message

Tool = Schema(
    title="Tool",
    fields={
        "type": fields.Choice(
            title="type", description="Tool kind discriminator", choices=("function",), default="function"
        ),
        "function": Reference(to="flama.llm_native.ToolFunction", definitions=SCHEMAS),
    },
)
SCHEMAS["flama.llm_native.Tool"] = Tool

TextEvent = Schema(
    title="TextEvent",
    fields={
        "type": fields.Choice(title="type", description="Block kind discriminator", choices=("text",), default="text"),
        "channel": fields.String(
            title="channel",
            description=(
                "Channel discriminator. ``'output'`` for the user-visible answer; an arbitrary captured name "
                "(e.g. ``'analysis'``, ``'thought'``) for meta-content; ``null`` when the model's marker "
                "captured no identity at all."
            ),
            allow_null=True,
            default=None,
        ),
        "text": fields.String(title="text", description="Block text content"),
    },
)
SCHEMAS["flama.llm_native.TextEvent"] = TextEvent

ToolEvent = Schema(
    title="ToolEvent",
    fields={
        "type": fields.Choice(title="type", description="Block kind discriminator", choices=("tool",), default="tool"),
        "id": fields.String(title="id", description="Tool call identifier"),
        "name": fields.String(title="name", description="Function name the model is requesting to invoke"),
        "arguments": fields.Object(title="arguments", description="Parsed JSON arguments object", default={}),
    },
)
SCHEMAS["flama.llm_native.ToolEvent"] = ToolEvent

Event = fields.Union(
    any_of=[
        Reference(to="flama.llm_native.TextEvent", definitions=SCHEMAS),
        Reference(to="flama.llm_native.ToolEvent", definitions=SCHEMAS),
    ],
)

NativeUsage = Schema(
    title="NativeUsage",
    fields={
        "input_tokens": fields.Integer(title="input_tokens", description="Prompt token count."),
        "output_tokens": fields.Integer(title="output_tokens", description="Completion token count."),
    },
)
SCHEMAS["flama.llm_native.NativeUsage"] = NativeUsage

ConfigureInput = Schema(
    title="ConfigureInput",
    fields={
        "params": fields.Object(title="params", description="Generation parameters"),
    },
)
SCHEMAS["flama.llm_native.ConfigureInput"] = ConfigureInput

ConfigureOutput = Schema(
    title="ConfigureOutput",
    fields={
        "params": fields.Object(title="params", description="Current generation parameters"),
    },
)
SCHEMAS["flama.llm_native.ConfigureOutput"] = ConfigureOutput

QueryInput = Schema(
    title="QueryInput",
    fields={
        "transport": fields.Choice(
            title="transport",
            description=(
                "Input shape: raw (verbatim), chat (templated single-turn), conversation (templated multi-turn). "
                "If omitted, the model's default transport is used."
            ),
            choices=("raw", "chat", "conversation"),
            allow_null=True,
            default=None,
        ),
        "prompt": fields.String(
            title="prompt", description="Input prompt for raw or chat transport.", allow_null=True, default=None
        ),
        "system": fields.String(
            title="system", description="Optional system instruction for chat.", allow_null=True, default=None
        ),
        "messages": fields.Array(
            title="messages",
            description="Conversation history for conversation transport.",
            items=Reference(to="flama.llm_native.Message", definitions=SCHEMAS),
            allow_null=True,
            default=None,
        ),
        "tools": fields.Array(
            title="tools",
            description="Function-tool specs advertised to the model (templated transports only)",
            items=Reference(to="flama.llm_native.Tool", definitions=SCHEMAS),
            allow_null=True,
            default=None,
        ),
        "params": fields.Object(
            title="params",
            description=(
                "Generation parameters override. ``max_tokens`` may be omitted or set to null to let the engine "
                "generate until natural completion (EOS) bounded only by the model's context window; pass a "
                "positive integer to enforce a hard cap. Non-positive values are rejected."
            ),
            default={},
        ),
        "chat_template_kwargs": fields.Object(
            title="chat_template_kwargs",
            description="Extra keyword arguments forwarded to the tokenizer's chat template",
            allow_null=True,
            default=None,
        ),
    },
)
SCHEMAS["flama.llm_native.QueryInput"] = QueryInput

QueryOutput = Schema(
    title="QueryOutput",
    fields={
        "id": fields.String(title="id", description="Generation identifier"),
        "created": fields.Integer(title="created", description="Unix timestamp at which the generation completed"),
        "blocks": fields.Array(
            title="blocks",
            description="Channel-tagged output blocks (text or tool)",
            items=Event,
        ),
        "stop_reason": fields.String(
            title="stop_reason",
            description="Why generation ended (e.g. stop, error, max_tokens)",
            allow_null=True,
            default=None,
        ),
        "usage": Reference(
            to="flama.llm_native.NativeUsage",
            definitions=SCHEMAS,
            allow_null=True,
            default=None,
        ),
    },
)
SCHEMAS["flama.llm_native.QueryOutput"] = QueryOutput

StreamInput = Schema(
    title="StreamInput",
    fields={
        "transport": fields.Choice(
            title="transport",
            description=(
                "Input shape: raw (verbatim), chat (templated single-turn), conversation (templated multi-turn). "
                "If omitted, the model's default transport is used."
            ),
            choices=("raw", "chat", "conversation"),
            allow_null=True,
            default=None,
        ),
        "prompt": fields.String(
            title="prompt", description="Input prompt for raw or chat transport.", allow_null=True, default=None
        ),
        "system": fields.String(
            title="system", description="Optional system instruction for chat.", allow_null=True, default=None
        ),
        "messages": fields.Array(
            title="messages",
            description="Conversation history for conversation transport.",
            items=Reference(to="flama.llm_native.Message", definitions=SCHEMAS),
            allow_null=True,
            default=None,
        ),
        "tools": fields.Array(
            title="tools",
            description="Function-tool specs advertised to the model (templated transports only)",
            items=Reference(to="flama.llm_native.Tool", definitions=SCHEMAS),
            allow_null=True,
            default=None,
        ),
        "params": fields.Object(
            title="params",
            description=(
                "Generation parameters override. ``max_tokens`` may be omitted or set to null to let the engine "
                "generate until natural completion (EOS) bounded only by the model's context window; pass a "
                "positive integer to enforce a hard cap. Non-positive values are rejected."
            ),
            default={},
        ),
        "chat_template_kwargs": fields.Object(
            title="chat_template_kwargs",
            description="Extra keyword arguments forwarded to the tokenizer's chat template",
            allow_null=True,
            default=None,
        ),
    },
)
SCHEMAS["flama.llm_native.StreamInput"] = StreamInput

StreamOutput = Schema(
    title="StreamOutput",
    fields={
        "id": fields.String(
            title="id",
            description="Generation identifier; consume the stream via GET /stream/{id}/ as Server-Sent Events.",
        ),
    },
)
SCHEMAS["flama.llm_native.StreamOutput"] = StreamOutput
