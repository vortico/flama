import typing as t

import marshmallow

from flama.schemas._libs.marshmallow.schemas.core import SCHEMAS
from flama.schemas._libs.marshmallow.schemas.llm_native import Message, Tool, ToolCall

__all__ = [
    "ChatChoice",
    "ChatChunkChoice",
    "ChatCompletionsChunk",
    "ChatCompletionsInput",
    "ChatCompletionsOutput",
    "ChatDelta",
    "ChatUsage",
    "CompletionsInput",
    "CompletionsOutput",
    "ModelEntry",
    "ModelsOutput",
    "ResponsesInput",
    "ResponsesOutput",
    "ResponsesUsage",
    "TextChoice",
    "ToolChoiceFunction",
    "ToolChoiceObject",
]


_TOOL_CHOICE_LITERALS: t.Final[frozenset[str]] = frozenset({"auto", "none", "required"})


class ToolChoiceFunction(marshmallow.Schema):
    name = marshmallow.fields.String(
        required=True,
        metadata={"title": "name", "description": "Target function name."},
    )


SCHEMAS["flama.llm_openai.ToolChoiceFunction"] = ToolChoiceFunction


class ToolChoiceObject(marshmallow.Schema):
    type = marshmallow.fields.String(
        load_default="function",
        validate=marshmallow.validate.OneOf(("function",)),
        metadata={"title": "type", "description": "Tool choice kind discriminator."},
    )
    function = marshmallow.fields.Nested(
        ToolChoiceFunction,
        required=True,
        metadata={"title": "function", "description": "Named function the model must call."},
    )


SCHEMAS["flama.llm_openai.ToolChoiceObject"] = ToolChoiceObject


class _ToolChoice(marshmallow.fields.Field):
    """Discriminated input field for OpenAI's ``tool_choice`` policy.

    Accepts the canonical literal strings (``auto`` / ``none`` / ``required``) or a named function object
    (validated against :class:`ToolChoiceObject`).
    """

    def _deserialize(
        self, value: t.Any, attr: str | None, data: t.Mapping[str, t.Any] | None, **kwargs: t.Any
    ) -> str | dict[str, t.Any]:
        if isinstance(value, str):
            if value not in _TOOL_CHOICE_LITERALS:
                raise marshmallow.ValidationError(
                    f"Wrong tool_choice {value!r}, expected one of: {sorted(_TOOL_CHOICE_LITERALS)} or a tool object"
                )
            return value
        if isinstance(value, dict):
            return t.cast(dict[str, t.Any], ToolChoiceObject().load(value))
        raise marshmallow.ValidationError("tool_choice must be a string or an object")

    def _jsonschema_type_mapping(self) -> dict[str, t.Any]:
        return {
            "oneOf": [
                {"type": "string", "enum": sorted(_TOOL_CHOICE_LITERALS)},
                {"$ref": f"#/components/schemas/{ToolChoiceObject.__name__}"},
            ],
        }


class ChatCompletionsInput(marshmallow.Schema):
    class Meta:
        unknown = marshmallow.INCLUDE

    model = marshmallow.fields.String(
        required=True,
        metadata={"title": "model", "description": "Model identifier; echoed back in the response."},
    )
    messages = marshmallow.fields.List(
        marshmallow.fields.Nested(Message()),
        required=True,
        metadata={
            "title": "messages",
            "description": "Conversation messages. Each entry must have at least 'role' and 'content' / 'tool_calls'.",
        },
    )
    stream = marshmallow.fields.Boolean(
        load_default=False,
        metadata={"title": "stream", "description": "If true, stream chunks via SSE."},
    )
    tools = marshmallow.fields.List(
        marshmallow.fields.Nested(Tool()),
        load_default=None,
        allow_none=True,
        metadata={"title": "tools", "description": "Function-tool specs advertised to the model."},
    )
    tool_choice = _ToolChoice(
        load_default=None,
        allow_none=True,
        metadata={
            "title": "tool_choice",
            "description": "Tool selection policy ('auto', 'none', 'required', or a named tool object).",
        },
    )


SCHEMAS["flama.llm_openai.ChatCompletionsInput"] = ChatCompletionsInput


class ChatUsage(marshmallow.Schema):
    prompt_tokens = marshmallow.fields.Integer(
        required=True,
        metadata={"title": "prompt_tokens", "description": "Input token count."},
    )
    completion_tokens = marshmallow.fields.Integer(
        required=True,
        metadata={"title": "completion_tokens", "description": "Output token count."},
    )
    total_tokens = marshmallow.fields.Integer(
        required=True,
        metadata={"title": "total_tokens", "description": "Combined token count."},
    )


SCHEMAS["flama.llm_openai.ChatUsage"] = ChatUsage


class ChatChoice(marshmallow.Schema):
    index = marshmallow.fields.Integer(
        required=True,
        metadata={"title": "index", "description": "Choice index (Flama always returns 0)."},
    )
    message = marshmallow.fields.Nested(
        Message,
        required=True,
        metadata={"title": "message", "description": "Assistant turn produced by the model."},
    )
    finish_reason = marshmallow.fields.String(
        load_default=None,
        allow_none=True,
        metadata={"title": "finish_reason", "description": "Why generation ended (e.g. stop, length, tool_calls)."},
    )


SCHEMAS["flama.llm_openai.ChatChoice"] = ChatChoice


class ChatDelta(marshmallow.Schema):
    role = marshmallow.fields.String(
        load_default=None,
        allow_none=True,
        validate=marshmallow.validate.OneOf(("assistant",)),
        metadata={"title": "role", "description": "Assistant role (only emitted on the first chunk)."},
    )
    content = marshmallow.fields.String(
        load_default=None,
        allow_none=True,
        metadata={
            "title": "content",
            "description": "Incremental answer text; absent on chunks that only carry reasoning or tool deltas.",
        },
    )
    reasoning_content = marshmallow.fields.String(
        load_default=None,
        allow_none=True,
        metadata={
            "title": "reasoning_content",
            "description": "Incremental thinking text exposed for clients that render reasoning panels.",
        },
    )
    tool_calls = marshmallow.fields.List(
        marshmallow.fields.Nested(ToolCall()),
        load_default=None,
        allow_none=True,
        metadata={
            "title": "tool_calls",
            "description": "Incremental tool call deltas (assistant-side function-calling).",
        },
    )


SCHEMAS["flama.llm_openai.ChatDelta"] = ChatDelta


class ChatChunkChoice(marshmallow.Schema):
    index = marshmallow.fields.Integer(
        required=True,
        metadata={"title": "index", "description": "Choice index (Flama always returns 0)."},
    )
    delta = marshmallow.fields.Nested(
        ChatDelta,
        required=True,
        metadata={"title": "delta", "description": "Incremental assistant turn payload."},
    )
    finish_reason = marshmallow.fields.String(
        load_default=None,
        allow_none=True,
        metadata={"title": "finish_reason", "description": "Set on the terminal chunk only."},
    )


SCHEMAS["flama.llm_openai.ChatChunkChoice"] = ChatChunkChoice


class ChatCompletionsOutput(marshmallow.Schema):
    id = marshmallow.fields.String(required=True, metadata={"title": "id", "description": "Generation identifier."})
    object = marshmallow.fields.String(
        load_default="chat.completion",
        validate=marshmallow.validate.OneOf(("chat.completion",)),
        metadata={"title": "object", "description": "Response object kind discriminator."},
    )
    created = marshmallow.fields.Integer(
        required=True,
        metadata={"title": "created", "description": "Unix timestamp at which the response was produced."},
    )
    model = marshmallow.fields.String(
        required=True,
        metadata={"title": "model", "description": "Model identifier; echoes the request."},
    )
    choices = marshmallow.fields.List(
        marshmallow.fields.Nested(ChatChoice()),
        required=True,
        metadata={"title": "choices", "description": "Generation choices; Flama always returns a single choice."},
    )
    usage = marshmallow.fields.Nested(
        ChatUsage,
        load_default=None,
        allow_none=True,
        metadata={"title": "usage", "description": "Token usage tally."},
    )


SCHEMAS["flama.llm_openai.ChatCompletionsOutput"] = ChatCompletionsOutput


class ChatCompletionsChunk(marshmallow.Schema):
    id = marshmallow.fields.String(
        required=True,
        metadata={"title": "id", "description": "Generation identifier; identical across chunks."},
    )
    object = marshmallow.fields.String(
        load_default="chat.completion.chunk",
        validate=marshmallow.validate.OneOf(("chat.completion.chunk",)),
        metadata={"title": "object", "description": "Response object kind discriminator."},
    )
    created = marshmallow.fields.Integer(
        required=True,
        metadata={"title": "created", "description": "Unix timestamp at which the chunk was produced."},
    )
    model = marshmallow.fields.String(required=True, metadata={"title": "model", "description": "Model identifier."})
    choices = marshmallow.fields.List(
        marshmallow.fields.Nested(ChatChunkChoice()),
        required=True,
        metadata={"title": "choices", "description": "Single-entry delta list: index, delta, optional finish_reason."},
    )


SCHEMAS["flama.llm_openai.ChatCompletionsChunk"] = ChatCompletionsChunk


class CompletionsInput(marshmallow.Schema):
    class Meta:
        unknown = marshmallow.INCLUDE

    model = marshmallow.fields.String(
        required=True,
        metadata={"title": "model", "description": "Model identifier; echoed back in the response."},
    )
    prompt = marshmallow.fields.Raw(
        required=True,
        metadata={"title": "prompt", "description": "Input prompt or list of prompts."},
    )
    stream = marshmallow.fields.Boolean(
        load_default=False,
        metadata={"title": "stream", "description": "If true, stream chunks via SSE."},
    )


SCHEMAS["flama.llm_openai.CompletionsInput"] = CompletionsInput


class TextChoice(marshmallow.Schema):
    index = marshmallow.fields.Integer(
        required=True,
        metadata={"title": "index", "description": "Choice index (Flama always returns 0)."},
    )
    text = marshmallow.fields.String(
        required=True,
        metadata={"title": "text", "description": "Generated completion text."},
    )
    finish_reason = marshmallow.fields.String(
        load_default=None,
        allow_none=True,
        metadata={"title": "finish_reason", "description": "Why generation ended (e.g. stop, length)."},
    )


SCHEMAS["flama.llm_openai.TextChoice"] = TextChoice


class CompletionsOutput(marshmallow.Schema):
    id = marshmallow.fields.String(required=True, metadata={"title": "id", "description": "Generation identifier."})
    object = marshmallow.fields.String(
        load_default="text_completion",
        validate=marshmallow.validate.OneOf(("text_completion",)),
        metadata={"title": "object", "description": "Response object kind discriminator."},
    )
    created = marshmallow.fields.Integer(
        required=True,
        metadata={"title": "created", "description": "Unix timestamp at which the response was produced."},
    )
    model = marshmallow.fields.String(
        required=True,
        metadata={"title": "model", "description": "Model identifier; echoes the request."},
    )
    choices = marshmallow.fields.List(
        marshmallow.fields.Nested(TextChoice()),
        required=True,
        metadata={"title": "choices", "description": "Generation choices; each has index, text, finish_reason."},
    )
    usage = marshmallow.fields.Nested(
        ChatUsage,
        load_default=None,
        allow_none=True,
        metadata={"title": "usage", "description": "Token usage tally."},
    )


SCHEMAS["flama.llm_openai.CompletionsOutput"] = CompletionsOutput


class ResponsesInput(marshmallow.Schema):
    class Meta:
        unknown = marshmallow.INCLUDE

    model = marshmallow.fields.String(
        required=True,
        metadata={"title": "model", "description": "Model identifier; echoed back in the response."},
    )
    input = marshmallow.fields.Raw(
        required=True,
        metadata={"title": "input", "description": "Input text or conversation items."},
    )
    instructions = marshmallow.fields.String(
        load_default=None,
        allow_none=True,
        metadata={"title": "instructions", "description": "Optional system instruction."},
    )
    stream = marshmallow.fields.Boolean(
        load_default=False,
        metadata={"title": "stream", "description": "If true, stream named SSE events."},
    )
    tools = marshmallow.fields.List(
        marshmallow.fields.Nested(Tool()),
        load_default=None,
        allow_none=True,
        metadata={"title": "tools", "description": "Function-tool specs advertised to the model."},
    )
    tool_choice = _ToolChoice(
        load_default=None,
        allow_none=True,
        metadata={"title": "tool_choice", "description": "Tool selection policy."},
    )


SCHEMAS["flama.llm_openai.ResponsesInput"] = ResponsesInput


class ResponsesUsage(marshmallow.Schema):
    input_tokens = marshmallow.fields.Integer(
        required=True,
        metadata={"title": "input_tokens", "description": "Input token count."},
    )
    output_tokens = marshmallow.fields.Integer(
        required=True,
        metadata={"title": "output_tokens", "description": "Output token count."},
    )
    total_tokens = marshmallow.fields.Integer(
        required=True,
        metadata={"title": "total_tokens", "description": "Combined token count."},
    )


SCHEMAS["flama.llm_openai.ResponsesUsage"] = ResponsesUsage


class ResponsesOutput(marshmallow.Schema):
    id = marshmallow.fields.String(required=True, metadata={"title": "id", "description": "Response identifier."})
    object = marshmallow.fields.String(
        load_default="response",
        validate=marshmallow.validate.OneOf(("response",)),
        metadata={"title": "object", "description": "Response object kind discriminator."},
    )
    created_at = marshmallow.fields.Integer(
        required=True,
        metadata={"title": "created_at", "description": "Unix timestamp at which the response was produced."},
    )
    status = marshmallow.fields.String(required=True, metadata={"title": "status", "description": "Response status."})
    model = marshmallow.fields.String(
        required=True,
        metadata={"title": "model", "description": "Model identifier; echoes the request."},
    )
    output = marshmallow.fields.List(
        marshmallow.fields.Dict(),
        required=True,
        metadata={"title": "output", "description": "Response output items."},
    )
    usage = marshmallow.fields.Nested(
        ResponsesUsage,
        load_default=None,
        allow_none=True,
        metadata={"title": "usage", "description": "Token usage tally."},
    )


SCHEMAS["flama.llm_openai.ResponsesOutput"] = ResponsesOutput


class ModelEntry(marshmallow.Schema):
    """Single entry returned by ``GET /v1/models``.

    ``unknown=INCLUDE`` keeps Flama-specific extensions (notably the ``capabilities`` map produced by the OpenAI
    serving layer) flowing through the validator unchanged.
    """

    class Meta:
        unknown = marshmallow.INCLUDE

    id = marshmallow.fields.String(
        required=True,
        metadata={"title": "id", "description": "Model identifier."},
    )
    object = marshmallow.fields.String(
        load_default="model",
        validate=marshmallow.validate.OneOf(("model",)),
        metadata={"title": "object", "description": "Entry kind discriminator."},
    )
    created = marshmallow.fields.Integer(
        required=True,
        metadata={"title": "created", "description": "Unix timestamp at which the model was registered."},
    )
    owned_by = marshmallow.fields.String(
        required=True,
        metadata={"title": "owned_by", "description": "Owning organisation; Flama returns its own identifier."},
    )


SCHEMAS["flama.llm_openai.ModelEntry"] = ModelEntry


class ModelsOutput(marshmallow.Schema):
    object = marshmallow.fields.String(
        load_default="list",
        validate=marshmallow.validate.OneOf(("list",)),
        metadata={"title": "object", "description": "Response object kind discriminator."},
    )
    data = marshmallow.fields.List(
        marshmallow.fields.Nested(ModelEntry()),
        required=True,
        metadata={
            "title": "data",
            "description": "List of available models; Flama returns a single entry per resource.",
        },
    )


SCHEMAS["flama.llm_openai.ModelsOutput"] = ModelsOutput
