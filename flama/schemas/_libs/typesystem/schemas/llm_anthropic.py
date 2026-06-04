from typesystem import Reference, Schema, fields

from flama.schemas._libs.typesystem.schemas.core import SCHEMAS

__all__ = [
    "MessagesInput",
    "MessagesOutput",
    "MessagesUsage",
    "ModelInfo",
    "ModelsOutput",
    "ToolChoiceObject",
]


ToolChoiceObject = Schema(
    title="ToolChoiceObject",
    fields={
        "type": fields.String(title="type", description="Tool choice kind discriminator."),
        "name": fields.String(
            title="name",
            description="Target tool name (only meaningful when ``type='tool'``).",
            allow_null=True,
            default=None,
        ),
    },
)
SCHEMAS["flama.llm_anthropic.ToolChoiceObject"] = ToolChoiceObject

MessagesInput = Schema(
    title="MessagesInput",
    fields={
        "model": fields.String(title="model", description="Model identifier; echoed back in the response."),
        "messages": fields.Array(
            title="messages",
            description="Conversation messages (Anthropic ``content`` blocks).",
            items=fields.Object(),
        ),
        "max_tokens": fields.Integer(
            title="max_tokens",
            description="Maximum number of tokens to generate (Anthropic-required).",
        ),
        "system": fields.Any(
            title="system",
            description="Optional system instruction (string or list of typed blocks).",
            allow_null=True,
            default=None,
        ),
        "stream": fields.Boolean(title="stream", description="If true, stream named SSE events.", default=False),
        "tools": fields.Array(
            title="tools",
            description="Function-tool specs advertised to the model.",
            items=fields.Object(),
            allow_null=True,
            default=None,
        ),
        "tool_choice": Reference(
            to="flama.llm_anthropic.ToolChoiceObject", definitions=SCHEMAS, allow_null=True, default=None
        ),
        "thinking": fields.Object(
            title="thinking",
            description="Anthropic extended-thinking knob.",
            allow_null=True,
            default=None,
        ),
    },
)
SCHEMAS["flama.llm_anthropic.MessagesInput"] = MessagesInput

MessagesUsage = Schema(
    title="MessagesUsage",
    fields={
        "input_tokens": fields.Integer(title="input_tokens", description="Input token count."),
        "output_tokens": fields.Integer(title="output_tokens", description="Output token count."),
    },
)
SCHEMAS["flama.llm_anthropic.MessagesUsage"] = MessagesUsage

MessagesOutput = Schema(
    title="MessagesOutput",
    fields={
        "id": fields.String(title="id", description="Generation identifier."),
        "type": fields.Choice(
            title="type",
            description="Response object kind discriminator.",
            choices=("message",),
            default="message",
        ),
        "role": fields.Choice(
            title="role",
            description="Anthropic always returns the assistant role.",
            choices=("assistant",),
            default="assistant",
        ),
        "model": fields.String(title="model", description="Model identifier; echoes the request."),
        "content": fields.Array(
            title="content",
            description="Ordered list of content blocks.",
            items=fields.Object(),
        ),
        "stop_reason": fields.String(
            title="stop_reason",
            description="Why generation ended.",
            allow_null=True,
            default=None,
        ),
        "stop_sequence": fields.String(
            title="stop_sequence",
            description="Stop sequence that terminated generation.",
            allow_null=True,
            default=None,
        ),
        "usage": Reference(to="flama.llm_anthropic.MessagesUsage", definitions=SCHEMAS, allow_null=True, default=None),
    },
)
SCHEMAS["flama.llm_anthropic.MessagesOutput"] = MessagesOutput

ModelInfo = Schema(
    title="ModelInfo",
    fields={
        "id": fields.String(title="id", description="Model identifier."),
        "type": fields.Choice(
            title="type",
            description="Entry kind discriminator.",
            choices=("model",),
            default="model",
        ),
        "display_name": fields.String(
            title="display_name",
            description="Human-readable model name.",
        ),
        "created_at": fields.String(
            title="created_at",
            description="ISO-8601 timestamp at which the model was registered.",
        ),
    },
)
SCHEMAS["flama.llm_anthropic.ModelInfo"] = ModelInfo

ModelsOutput = Schema(
    title="ModelsOutput",
    fields={
        "data": fields.Array(
            title="data",
            description="List of available models; Flama returns a single entry per resource.",
            items=Reference(to="flama.llm_anthropic.ModelInfo", definitions=SCHEMAS),
        ),
        "has_more": fields.Boolean(
            title="has_more",
            description="Pagination flag.",
            default=False,
        ),
        "first_id": fields.String(
            title="first_id",
            description="Cursor anchor (id of the first entry).",
            allow_null=True,
            default=None,
        ),
        "last_id": fields.String(
            title="last_id",
            description="Cursor anchor (id of the last entry).",
            allow_null=True,
            default=None,
        ),
    },
)
SCHEMAS["flama.llm_anthropic.ModelsOutput"] = ModelsOutput
