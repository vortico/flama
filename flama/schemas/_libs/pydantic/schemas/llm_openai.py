import typing as t

from pydantic import BaseModel, ConfigDict, Field

from flama.schemas._libs.pydantic.schemas.core import SCHEMAS
from flama.schemas._libs.pydantic.schemas.llm_native import Message, Tool, ToolCall

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


class ToolChoiceFunction(BaseModel):
    name: str = Field(title="name", description="Target function name.")


SCHEMAS["flama.llm_openai.ToolChoiceFunction"] = ToolChoiceFunction


class ToolChoiceObject(BaseModel):
    type: t.Literal["function"] = Field(default="function", title="type", description="Tool choice kind discriminator.")
    function: ToolChoiceFunction = Field(title="function", description="Named function the model must call.")


SCHEMAS["flama.llm_openai.ToolChoiceObject"] = ToolChoiceObject


class ChatCompletionsInput(BaseModel):
    """OpenAI ``POST /v1/chat/completions`` request body.

    Permissive: unknown sampling parameters (``temperature``, ``top_p``, ``max_tokens``, ``seed``, ...) are accepted
    and forwarded to the underlying model as generation params.
    """

    model_config = ConfigDict(extra="allow")

    model: str = Field(title="model", description="Model identifier; echoed back in the response.")
    messages: list[Message] = Field(
        title="messages",
        description="Conversation messages. Each entry must have at least 'role' and 'content' / 'tool_calls'.",
    )
    stream: bool = Field(default=False, title="stream", description="If true, stream chunks via SSE.")
    tools: list[Tool] | None = Field(
        default=None, title="tools", description="Function-tool specs advertised to the model."
    )
    tool_choice: t.Literal["auto", "none", "required"] | ToolChoiceObject | None = Field(
        default=None,
        title="tool_choice",
        description="Tool selection policy ('auto', 'none', 'required', or a named tool object).",
    )


SCHEMAS["flama.llm_openai.ChatCompletionsInput"] = ChatCompletionsInput


class ChatUsage(BaseModel):
    """Token usage tally returned in chat completion responses."""

    prompt_tokens: int = Field(title="prompt_tokens", description="Input token count.")
    completion_tokens: int = Field(title="completion_tokens", description="Output token count.")
    total_tokens: int = Field(title="total_tokens", description="Combined token count.")


SCHEMAS["flama.llm_openai.ChatUsage"] = ChatUsage


class ChatChoice(BaseModel):
    index: int = Field(title="index", description="Choice index (Flama always returns 0).")
    message: Message = Field(title="message", description="Assistant turn produced by the model.")
    finish_reason: str | None = Field(
        default=None, title="finish_reason", description="Why generation ended (e.g. stop, length, tool_calls)."
    )


SCHEMAS["flama.llm_openai.ChatChoice"] = ChatChoice


class ChatDelta(BaseModel):
    """Streaming chunk payload describing the incremental assistant turn."""

    role: t.Literal["assistant"] | None = Field(
        default=None, title="role", description="Assistant role (only emitted on the first chunk)."
    )
    content: str | None = Field(
        default=None,
        title="content",
        description="Incremental answer text; absent on chunks that only carry reasoning or tool deltas.",
    )
    reasoning_content: str | None = Field(
        default=None,
        title="reasoning_content",
        description="Incremental thinking text exposed for clients that render reasoning panels.",
    )
    tool_calls: list[ToolCall] | None = Field(
        default=None,
        title="tool_calls",
        description="Incremental tool call deltas (assistant-side function-calling).",
    )


SCHEMAS["flama.llm_openai.ChatDelta"] = ChatDelta


class ChatChunkChoice(BaseModel):
    index: int = Field(title="index", description="Choice index (Flama always returns 0).")
    delta: ChatDelta = Field(title="delta", description="Incremental assistant turn payload.")
    finish_reason: str | None = Field(
        default=None, title="finish_reason", description="Set on the terminal chunk only."
    )


SCHEMAS["flama.llm_openai.ChatChunkChoice"] = ChatChunkChoice


class ChatCompletionsOutput(BaseModel):
    """OpenAI ``POST /v1/chat/completions`` non-streaming response body."""

    id: str = Field(title="id", description="Generation identifier.")
    object: t.Literal["chat.completion"] = Field(
        default="chat.completion", title="object", description="Response object kind discriminator."
    )
    created: int = Field(title="created", description="Unix timestamp at which the response was produced.")
    model: str = Field(title="model", description="Model identifier; echoes the request.")
    choices: list[ChatChoice] = Field(
        title="choices", description="Generation choices; Flama always returns a single choice."
    )
    usage: ChatUsage | None = Field(
        default=None, title="usage", description="Token usage tally (prompt_tokens, completion_tokens, total_tokens)."
    )


SCHEMAS["flama.llm_openai.ChatCompletionsOutput"] = ChatCompletionsOutput


class ChatCompletionsChunk(BaseModel):
    """OpenAI ``POST /v1/chat/completions`` streaming chunk body (documentary; chunks are serialised manually).

    Editor plugins consume these as ``data: {...}`` lines in the SSE response stream, terminated by a single
    ``data: [DONE]`` sentinel.
    """

    id: str = Field(title="id", description="Generation identifier; identical across chunks.")
    object: t.Literal["chat.completion.chunk"] = Field(
        default="chat.completion.chunk", title="object", description="Response object kind discriminator."
    )
    created: int = Field(title="created", description="Unix timestamp at which the chunk was produced.")
    model: str = Field(title="model", description="Model identifier.")
    choices: list[ChatChunkChoice] = Field(
        title="choices", description="Single-entry delta list: index, delta, optional finish_reason."
    )


SCHEMAS["flama.llm_openai.ChatCompletionsChunk"] = ChatCompletionsChunk


class CompletionsInput(BaseModel):
    """OpenAI ``POST /v1/completions`` request body (legacy text completion).

    Permissive: unknown sampling parameters are accepted and forwarded to the underlying model as generation params.
    """

    model_config = ConfigDict(extra="allow")

    model: str = Field(title="model", description="Model identifier; echoed back in the response.")
    prompt: str | list[str] = Field(title="prompt", description="Input prompt or list of prompts.")
    stream: bool = Field(default=False, title="stream", description="If true, stream chunks via SSE.")


SCHEMAS["flama.llm_openai.CompletionsInput"] = CompletionsInput


class TextChoice(BaseModel):
    index: int = Field(title="index", description="Choice index (Flama always returns 0).")
    text: str = Field(title="text", description="Generated completion text.")
    finish_reason: str | None = Field(
        default=None, title="finish_reason", description="Why generation ended (e.g. stop, length)."
    )


SCHEMAS["flama.llm_openai.TextChoice"] = TextChoice


class CompletionsOutput(BaseModel):
    """OpenAI ``POST /v1/completions`` non-streaming response body."""

    id: str = Field(title="id", description="Generation identifier.")
    object: t.Literal["text_completion"] = Field(
        default="text_completion", title="object", description="Response object kind discriminator."
    )
    created: int = Field(title="created", description="Unix timestamp at which the response was produced.")
    model: str = Field(title="model", description="Model identifier; echoes the request.")
    choices: list[TextChoice] = Field(
        title="choices", description="Generation choices; each has index, text, finish_reason."
    )
    usage: ChatUsage | None = Field(default=None, title="usage", description="Token usage tally.")


SCHEMAS["flama.llm_openai.CompletionsOutput"] = CompletionsOutput


class ResponsesInput(BaseModel):
    """OpenAI ``POST /v1/responses`` request body.

    Permissive: unknown sampling parameters are accepted and forwarded to the underlying model. The ``input`` field
    keeps a loose ``list[dict]`` shape on purpose: its discriminated-union schema is a separate, non-trivial task.
    """

    model_config = ConfigDict(extra="allow")

    model: str = Field(title="model", description="Model identifier; echoed back in the response.")
    input: str | list[dict[str, t.Any]] = Field(title="input", description="Input text or conversation items.")
    instructions: str | None = Field(default=None, title="instructions", description="Optional system instruction.")
    stream: bool = Field(default=False, title="stream", description="If true, stream named SSE events.")
    tools: list[Tool] | None = Field(
        default=None, title="tools", description="Function-tool specs advertised to the model."
    )
    tool_choice: t.Literal["auto", "none", "required"] | ToolChoiceObject | None = Field(
        default=None, title="tool_choice", description="Tool selection policy."
    )


SCHEMAS["flama.llm_openai.ResponsesInput"] = ResponsesInput


class ResponsesUsage(BaseModel):
    """Token usage tally returned in ``/v1/responses`` payloads."""

    input_tokens: int = Field(title="input_tokens", description="Input token count.")
    output_tokens: int = Field(title="output_tokens", description="Output token count.")
    total_tokens: int = Field(title="total_tokens", description="Combined token count.")


SCHEMAS["flama.llm_openai.ResponsesUsage"] = ResponsesUsage


class ResponsesOutput(BaseModel):
    """OpenAI ``POST /v1/responses`` non-streaming response body.

    The ``output`` field stays loose (``list[dict]``): its discriminated-union schema (reasoning, message,
    tool_call, ...) is large enough to merit its own task and is intentionally out of scope for this PR.
    """

    id: str = Field(title="id", description="Response identifier.")
    object: t.Literal["response"] = Field(
        default="response", title="object", description="Response object kind discriminator."
    )
    created_at: int = Field(title="created_at", description="Unix timestamp at which the response was produced.")
    status: str = Field(title="status", description="Response status.")
    model: str = Field(title="model", description="Model identifier; echoes the request.")
    output: list[dict[str, t.Any]] = Field(title="output", description="Response output items.")
    usage: ResponsesUsage | None = Field(default=None, title="usage", description="Token usage tally.")


SCHEMAS["flama.llm_openai.ResponsesOutput"] = ResponsesOutput


class ModelEntry(BaseModel):
    """Single entry returned by ``GET /v1/models``.

    ``extra="allow"`` keeps Flama-specific extensions (notably the ``capabilities`` map produced
    by the OpenAI serving layer) flowing through the validator unchanged.
    """

    model_config = ConfigDict(extra="allow")

    id: str = Field(title="id", description="Model identifier.")
    object: t.Literal["model"] = Field(default="model", title="object", description="Entry kind discriminator.")
    created: int = Field(title="created", description="Unix timestamp at which the model was registered.")
    owned_by: str = Field(title="owned_by", description="Owning organisation; Flama returns its own identifier.")


SCHEMAS["flama.llm_openai.ModelEntry"] = ModelEntry


class ModelsOutput(BaseModel):
    """OpenAI ``GET /v1/models`` response body."""

    object: t.Literal["list"] = Field(default="list", title="object", description="Response object kind discriminator.")
    data: list[ModelEntry] = Field(
        title="data", description="List of available models; Flama returns a single entry per resource."
    )


SCHEMAS["flama.llm_openai.ModelsOutput"] = ModelsOutput
