import marshmallow

from flama.schemas._libs.marshmallow.schemas.core import SCHEMAS

__all__ = [
    "MessagesInput",
    "MessagesOutput",
    "MessagesUsage",
    "ModelInfo",
    "ModelsOutput",
    "ToolChoiceObject",
]


class ToolChoiceObject(marshmallow.Schema):
    """Tool selection policy object accepted by Anthropic's Messages API."""

    class Meta:
        unknown = marshmallow.INCLUDE

    type = marshmallow.fields.String(
        required=True,
        metadata={"title": "type", "description": "Tool choice kind discriminator."},
    )
    name = marshmallow.fields.String(
        load_default=None,
        allow_none=True,
        metadata={"title": "name", "description": "Target tool name (only meaningful when ``type='tool'``)."},
    )


SCHEMAS["flama.llm_anthropic.ToolChoiceObject"] = ToolChoiceObject


class MessagesInput(marshmallow.Schema):
    class Meta:
        unknown = marshmallow.INCLUDE

    model = marshmallow.fields.String(
        required=True,
        metadata={"title": "model", "description": "Model identifier; echoed back in the response."},
    )
    messages = marshmallow.fields.List(
        marshmallow.fields.Dict(),
        required=True,
        metadata={
            "title": "messages",
            "description": "Conversation messages (Anthropic ``content`` blocks).",
        },
    )
    max_tokens = marshmallow.fields.Integer(
        required=True,
        metadata={
            "title": "max_tokens",
            "description": "Maximum number of tokens to generate (Anthropic-required).",
        },
    )
    system = marshmallow.fields.Raw(
        load_default=None,
        allow_none=True,
        metadata={
            "title": "system",
            "description": "Optional system instruction (string or list of typed blocks).",
        },
    )
    stream = marshmallow.fields.Boolean(
        load_default=False,
        metadata={"title": "stream", "description": "If true, stream named SSE events."},
    )
    tools = marshmallow.fields.List(
        marshmallow.fields.Dict(),
        load_default=None,
        allow_none=True,
        metadata={"title": "tools", "description": "Function-tool specs advertised to the model."},
    )
    tool_choice = marshmallow.fields.Nested(
        ToolChoiceObject,
        load_default=None,
        allow_none=True,
        metadata={"title": "tool_choice", "description": "Tool selection policy."},
    )
    thinking = marshmallow.fields.Dict(
        load_default=None,
        allow_none=True,
        metadata={"title": "thinking", "description": "Anthropic extended-thinking knob."},
    )


SCHEMAS["flama.llm_anthropic.MessagesInput"] = MessagesInput


class MessagesUsage(marshmallow.Schema):
    input_tokens = marshmallow.fields.Integer(
        required=True,
        metadata={"title": "input_tokens", "description": "Input token count."},
    )
    output_tokens = marshmallow.fields.Integer(
        required=True,
        metadata={"title": "output_tokens", "description": "Output token count."},
    )


SCHEMAS["flama.llm_anthropic.MessagesUsage"] = MessagesUsage


class MessagesOutput(marshmallow.Schema):
    id = marshmallow.fields.String(required=True, metadata={"title": "id", "description": "Generation identifier."})
    type = marshmallow.fields.String(
        load_default="message",
        validate=marshmallow.validate.OneOf(("message",)),
        metadata={"title": "type", "description": "Response object kind discriminator."},
    )
    role = marshmallow.fields.String(
        load_default="assistant",
        validate=marshmallow.validate.OneOf(("assistant",)),
        metadata={"title": "role", "description": "Anthropic always returns the assistant role."},
    )
    model = marshmallow.fields.String(
        required=True,
        metadata={"title": "model", "description": "Model identifier; echoes the request."},
    )
    content = marshmallow.fields.List(
        marshmallow.fields.Dict(),
        required=True,
        metadata={"title": "content", "description": "Ordered list of content blocks."},
    )
    stop_reason = marshmallow.fields.String(
        load_default=None,
        allow_none=True,
        metadata={"title": "stop_reason", "description": "Why generation ended."},
    )
    stop_sequence = marshmallow.fields.String(
        load_default=None,
        allow_none=True,
        metadata={"title": "stop_sequence", "description": "Stop sequence that terminated generation."},
    )
    usage = marshmallow.fields.Nested(
        MessagesUsage,
        load_default=None,
        allow_none=True,
        metadata={"title": "usage", "description": "Token usage tally."},
    )


SCHEMAS["flama.llm_anthropic.MessagesOutput"] = MessagesOutput


class ModelInfo(marshmallow.Schema):
    """Single entry returned by Anthropic ``GET /v1/models``.

    ``unknown=INCLUDE`` keeps Flama-specific extensions (notably the ``capabilities`` map) flowing through
    the validator unchanged.
    """

    class Meta:
        unknown = marshmallow.INCLUDE

    id = marshmallow.fields.String(
        required=True,
        metadata={"title": "id", "description": "Model identifier."},
    )
    type = marshmallow.fields.String(
        load_default="model",
        validate=marshmallow.validate.OneOf(("model",)),
        metadata={"title": "type", "description": "Entry kind discriminator."},
    )
    display_name = marshmallow.fields.String(
        required=True,
        metadata={"title": "display_name", "description": "Human-readable model name."},
    )
    created_at = marshmallow.fields.String(
        required=True,
        metadata={"title": "created_at", "description": "ISO-8601 timestamp at which the model was registered."},
    )


SCHEMAS["flama.llm_anthropic.ModelInfo"] = ModelInfo


class ModelsOutput(marshmallow.Schema):
    data = marshmallow.fields.List(
        marshmallow.fields.Nested(ModelInfo()),
        required=True,
        metadata={
            "title": "data",
            "description": "List of available models; Flama returns a single entry per resource.",
        },
    )
    has_more = marshmallow.fields.Boolean(
        load_default=False,
        metadata={"title": "has_more", "description": "Pagination flag."},
    )
    first_id = marshmallow.fields.String(
        load_default=None,
        allow_none=True,
        metadata={"title": "first_id", "description": "Cursor anchor (id of the first entry)."},
    )
    last_id = marshmallow.fields.String(
        load_default=None,
        allow_none=True,
        metadata={"title": "last_id", "description": "Cursor anchor (id of the last entry)."},
    )


SCHEMAS["flama.llm_anthropic.ModelsOutput"] = ModelsOutput
