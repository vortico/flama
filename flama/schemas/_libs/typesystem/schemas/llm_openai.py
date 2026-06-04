from typesystem import Reference, Schema, fields

from flama.schemas._libs.typesystem.schemas.core import SCHEMAS

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

ToolChoiceFunction = Schema(
    title="ToolChoiceFunction",
    fields={"name": fields.String(title="name", description="Target function name.")},
)
SCHEMAS["flama.llm_openai.ToolChoiceFunction"] = ToolChoiceFunction

ToolChoiceObject = Schema(
    title="ToolChoiceObject",
    fields={
        "type": fields.Choice(
            title="type",
            description="Tool choice kind discriminator.",
            choices=("function",),
            default="function",
        ),
        "function": Reference(to="flama.llm_openai.ToolChoiceFunction", definitions=SCHEMAS),
    },
)
SCHEMAS["flama.llm_openai.ToolChoiceObject"] = ToolChoiceObject

_ToolChoice = fields.Union(
    any_of=[
        fields.Choice(choices=("auto", "none", "required")),
        Reference(to="flama.llm_openai.ToolChoiceObject", definitions=SCHEMAS),
    ],
    allow_null=True,
    default=None,
)


ChatCompletionsInput = Schema(
    title="ChatCompletionsInput",
    fields={
        "model": fields.String(title="model", description="Model identifier; echoed back in the response."),
        "messages": fields.Array(
            title="messages",
            description=("Conversation messages. Each entry must have at least 'role' and 'content' / 'tool_calls'."),
            items=Reference(to="flama.llm_native.Message", definitions=SCHEMAS),
        ),
        "stream": fields.Boolean(title="stream", description="If true, stream chunks via SSE.", default=False),
        "tools": fields.Array(
            title="tools",
            description="Function-tool specs advertised to the model.",
            items=Reference(to="flama.llm_native.Tool", definitions=SCHEMAS),
            allow_null=True,
            default=None,
        ),
        "tool_choice": _ToolChoice,
    },
)
SCHEMAS["flama.llm_openai.ChatCompletionsInput"] = ChatCompletionsInput

ChatUsage = Schema(
    title="ChatUsage",
    fields={
        "prompt_tokens": fields.Integer(title="prompt_tokens", description="Input token count."),
        "completion_tokens": fields.Integer(title="completion_tokens", description="Output token count."),
        "total_tokens": fields.Integer(title="total_tokens", description="Combined token count."),
    },
)
SCHEMAS["flama.llm_openai.ChatUsage"] = ChatUsage

ChatChoice = Schema(
    title="ChatChoice",
    fields={
        "index": fields.Integer(title="index", description="Choice index (Flama always returns 0)."),
        "message": Reference(to="flama.llm_native.Message", definitions=SCHEMAS),
        "finish_reason": fields.String(
            title="finish_reason",
            description="Why generation ended (e.g. stop, length, tool_calls).",
            allow_null=True,
            default=None,
        ),
    },
)
SCHEMAS["flama.llm_openai.ChatChoice"] = ChatChoice

ChatDelta = Schema(
    title="ChatDelta",
    fields={
        "role": fields.Choice(
            title="role",
            description="Assistant role (only emitted on the first chunk).",
            choices=("assistant",),
            allow_null=True,
            default=None,
        ),
        "content": fields.String(
            title="content",
            description="Incremental answer text; absent on chunks that only carry reasoning or tool deltas.",
            allow_null=True,
            default=None,
        ),
        "reasoning_content": fields.String(
            title="reasoning_content",
            description="Incremental thinking text exposed for clients that render reasoning panels.",
            allow_null=True,
            default=None,
        ),
        "tool_calls": fields.Array(
            title="tool_calls",
            description="Incremental tool call deltas (assistant-side function-calling).",
            items=Reference(to="flama.llm_native.ToolCall", definitions=SCHEMAS),
            allow_null=True,
            default=None,
        ),
    },
)
SCHEMAS["flama.llm_openai.ChatDelta"] = ChatDelta

ChatChunkChoice = Schema(
    title="ChatChunkChoice",
    fields={
        "index": fields.Integer(title="index", description="Choice index (Flama always returns 0)."),
        "delta": Reference(to="flama.llm_openai.ChatDelta", definitions=SCHEMAS),
        "finish_reason": fields.String(
            title="finish_reason",
            description="Set on the terminal chunk only.",
            allow_null=True,
            default=None,
        ),
    },
)
SCHEMAS["flama.llm_openai.ChatChunkChoice"] = ChatChunkChoice

ChatCompletionsOutput = Schema(
    title="ChatCompletionsOutput",
    fields={
        "id": fields.String(title="id", description="Generation identifier."),
        "object": fields.Choice(
            title="object",
            description="Response object kind discriminator.",
            choices=("chat.completion",),
            default="chat.completion",
        ),
        "created": fields.Integer(title="created", description="Unix timestamp at which the response was produced."),
        "model": fields.String(title="model", description="Model identifier; echoes the request."),
        "choices": fields.Array(
            title="choices",
            description="Generation choices; Flama always returns a single choice.",
            items=Reference(to="flama.llm_openai.ChatChoice", definitions=SCHEMAS),
        ),
        "usage": Reference(to="flama.llm_openai.ChatUsage", definitions=SCHEMAS, allow_null=True, default=None),
    },
)
SCHEMAS["flama.llm_openai.ChatCompletionsOutput"] = ChatCompletionsOutput

ChatCompletionsChunk = Schema(
    title="ChatCompletionsChunk",
    fields={
        "id": fields.String(title="id", description="Generation identifier; identical across chunks."),
        "object": fields.Choice(
            title="object",
            description="Response object kind discriminator.",
            choices=("chat.completion.chunk",),
            default="chat.completion.chunk",
        ),
        "created": fields.Integer(title="created", description="Unix timestamp at which the chunk was produced."),
        "model": fields.String(title="model", description="Model identifier."),
        "choices": fields.Array(
            title="choices",
            description="Single-entry delta list: index, delta, optional finish_reason.",
            items=Reference(to="flama.llm_openai.ChatChunkChoice", definitions=SCHEMAS),
        ),
    },
)
SCHEMAS["flama.llm_openai.ChatCompletionsChunk"] = ChatCompletionsChunk

CompletionsInput = Schema(
    title="CompletionsInput",
    fields={
        "model": fields.String(title="model", description="Model identifier; echoed back in the response."),
        "prompt": fields.Any(title="prompt", description="Input prompt or list of prompts."),
        "stream": fields.Boolean(title="stream", description="If true, stream chunks via SSE.", default=False),
    },
)
SCHEMAS["flama.llm_openai.CompletionsInput"] = CompletionsInput

TextChoice = Schema(
    title="TextChoice",
    fields={
        "index": fields.Integer(title="index", description="Choice index (Flama always returns 0)."),
        "text": fields.String(title="text", description="Generated completion text."),
        "finish_reason": fields.String(
            title="finish_reason",
            description="Why generation ended (e.g. stop, length).",
            allow_null=True,
            default=None,
        ),
    },
)
SCHEMAS["flama.llm_openai.TextChoice"] = TextChoice

CompletionsOutput = Schema(
    title="CompletionsOutput",
    fields={
        "id": fields.String(title="id", description="Generation identifier."),
        "object": fields.Choice(
            title="object",
            description="Response object kind discriminator.",
            choices=("text_completion",),
            default="text_completion",
        ),
        "created": fields.Integer(title="created", description="Unix timestamp at which the response was produced."),
        "model": fields.String(title="model", description="Model identifier; echoes the request."),
        "choices": fields.Array(
            title="choices",
            description="Generation choices; each has index, text, finish_reason.",
            items=Reference(to="flama.llm_openai.TextChoice", definitions=SCHEMAS),
        ),
        "usage": Reference(to="flama.llm_openai.ChatUsage", definitions=SCHEMAS, allow_null=True, default=None),
    },
)
SCHEMAS["flama.llm_openai.CompletionsOutput"] = CompletionsOutput

ResponsesInput = Schema(
    title="ResponsesInput",
    fields={
        "model": fields.String(title="model", description="Model identifier; echoed back in the response."),
        "input": fields.Any(title="input", description="Input text or conversation items."),
        "instructions": fields.String(
            title="instructions", description="Optional system instruction.", allow_null=True, default=None
        ),
        "stream": fields.Boolean(title="stream", description="If true, stream named SSE events.", default=False),
        "tools": fields.Array(
            title="tools",
            description="Function-tool specs advertised to the model.",
            items=Reference(to="flama.llm_native.Tool", definitions=SCHEMAS),
            allow_null=True,
            default=None,
        ),
        "tool_choice": _ToolChoice,
    },
)
SCHEMAS["flama.llm_openai.ResponsesInput"] = ResponsesInput

ResponsesUsage = Schema(
    title="ResponsesUsage",
    fields={
        "input_tokens": fields.Integer(title="input_tokens", description="Input token count."),
        "output_tokens": fields.Integer(title="output_tokens", description="Output token count."),
        "total_tokens": fields.Integer(title="total_tokens", description="Combined token count."),
    },
)
SCHEMAS["flama.llm_openai.ResponsesUsage"] = ResponsesUsage

ResponsesOutput = Schema(
    title="ResponsesOutput",
    fields={
        "id": fields.String(title="id", description="Response identifier."),
        "object": fields.Choice(
            title="object",
            description="Response object kind discriminator.",
            choices=("response",),
            default="response",
        ),
        "created_at": fields.Integer(
            title="created_at", description="Unix timestamp at which the response was produced."
        ),
        "status": fields.String(title="status", description="Response status."),
        "model": fields.String(title="model", description="Model identifier; echoes the request."),
        "output": fields.Array(title="output", description="Response output items.", items=fields.Object()),
        "usage": Reference(to="flama.llm_openai.ResponsesUsage", definitions=SCHEMAS, allow_null=True, default=None),
    },
)
SCHEMAS["flama.llm_openai.ResponsesOutput"] = ResponsesOutput

ModelEntry = Schema(
    title="ModelEntry",
    fields={
        "id": fields.String(title="id", description="Model identifier."),
        "object": fields.Choice(
            title="object", description="Entry kind discriminator.", choices=("model",), default="model"
        ),
        "created": fields.Integer(title="created", description="Unix timestamp at which the model was registered."),
        "owned_by": fields.String(
            title="owned_by",
            description="Owning organisation; Flama returns its own identifier.",
        ),
    },
)
SCHEMAS["flama.llm_openai.ModelEntry"] = ModelEntry

ModelsOutput = Schema(
    title="ModelsOutput",
    fields={
        "object": fields.Choice(
            title="object",
            description="Response object kind discriminator.",
            choices=("list",),
            default="list",
        ),
        "data": fields.Array(
            title="data",
            description="List of available models; Flama returns a single entry per resource.",
            items=Reference(to="flama.llm_openai.ModelEntry", definitions=SCHEMAS),
        ),
    },
)
SCHEMAS["flama.llm_openai.ModelsOutput"] = ModelsOutput
