import typing as t

from pydantic import BaseModel, ConfigDict, Field

from flama.schemas._libs.pydantic.schemas.core import SCHEMAS

__all__ = [
    "MessagesInput",
    "MessagesOutput",
    "MessagesUsage",
    "ModelInfo",
    "ModelsOutput",
    "ToolChoiceObject",
]


class ToolChoiceObject(BaseModel):
    """Tool selection policy object accepted by Anthropic's Messages API.

    Anthropic accepts ``type: "auto" | "any" | "tool" | "none"``; when ``type="tool"`` an additional
    ``name`` field pins the call. Flama keeps the schema permissive (``extra="allow"``) so newer
    Anthropic-only fields (``disable_parallel_tool_use`` …) flow through unchanged.
    """

    model_config = ConfigDict(extra="allow")

    type: str = Field(title="type", description="Tool choice kind discriminator.")
    name: str | None = Field(
        default=None,
        title="name",
        description="Target tool name (only meaningful when ``type='tool'``).",
    )


SCHEMAS["flama.llm_anthropic.ToolChoiceObject"] = ToolChoiceObject


class MessagesInput(BaseModel):
    """Anthropic ``POST /v1/messages`` request body.

    Permissive: unknown sampling parameters (``temperature``, ``top_p``, ``top_k``, ``stop_sequences``,
    ``metadata``, ``service_tier`` …) and free-form ``messages`` / ``content`` shapes are accepted and
    forwarded to the underlying model unchanged. Anthropic-specific fields (``system``, ``thinking``,
    ``tool_choice``) are normalised by the serving handler before message parsing.
    """

    model_config = ConfigDict(extra="allow")

    model: str = Field(title="model", description="Model identifier; echoed back in the response.")
    messages: list[dict[str, t.Any]] = Field(
        title="messages",
        description=(
            "Conversation messages. Each entry must carry ``role`` (``user`` / ``assistant``) and ``content`` "
            "(string or list of typed content blocks: ``text``, ``image``, ``tool_use``, ``tool_result``, "
            "``thinking``)."
        ),
    )
    max_tokens: int = Field(
        title="max_tokens",
        description="Maximum number of tokens to generate (Anthropic-required; forwarded to the backend).",
    )
    system: str | list[dict[str, t.Any]] | None = Field(
        default=None,
        title="system",
        description=(
            "Optional system instruction. Anthropic accepts either a single string or a list of typed blocks "
            "(typically ``text``); both are flattened into a leading system message by the handler."
        ),
    )
    stream: bool = Field(default=False, title="stream", description="If true, stream named SSE events.")
    tools: list[dict[str, t.Any]] | None = Field(
        default=None,
        title="tools",
        description=(
            "Function-tool specs advertised to the model. Anthropic's wire shape uses "
            "``{name, description, input_schema}``; the handler translates each entry to canonical "
            "``Tool`` instances before delegating to the model."
        ),
    )
    tool_choice: ToolChoiceObject | None = Field(
        default=None,
        title="tool_choice",
        description="Tool selection policy (``auto`` / ``any`` / ``tool`` / ``none``).",
    )
    thinking: dict[str, t.Any] | None = Field(
        default=None,
        title="thinking",
        description=(
            "Anthropic extended-thinking knob. ``{'type': 'enabled', 'budget_tokens': N}`` enables reasoning; "
            "``{'type': 'disabled'}`` disables it. The handler maps this onto Flama's ``enable_thinking`` / "
            "``reasoning_effort`` chat-template kwargs."
        ),
    )


SCHEMAS["flama.llm_anthropic.MessagesInput"] = MessagesInput


class MessagesUsage(BaseModel):
    """Token usage tally returned in Anthropic Messages API payloads."""

    input_tokens: int = Field(title="input_tokens", description="Input token count.")
    output_tokens: int = Field(title="output_tokens", description="Output token count.")


SCHEMAS["flama.llm_anthropic.MessagesUsage"] = MessagesUsage


class MessagesOutput(BaseModel):
    """Anthropic ``POST /v1/messages`` non-streaming response body.

    The ``content`` field stays loose (``list[dict]``): the discriminated-union schema for content blocks
    (``text`` / ``tool_use`` / ``thinking``) is large enough to merit its own task. Clients that strict-validate
    individual blocks should consume :attr:`AnthropicAssembler.envelope` output, which always projects the
    canonical shape.
    """

    id: str = Field(title="id", description="Generation identifier (``msg_<hex>``).")
    type: t.Literal["message"] = Field(
        default="message", title="type", description="Response object kind discriminator."
    )
    role: t.Literal["assistant"] = Field(
        default="assistant", title="role", description="Anthropic always returns the assistant role."
    )
    model: str = Field(title="model", description="Model identifier; echoes the request.")
    content: list[dict[str, t.Any]] = Field(
        title="content",
        description="Ordered list of content blocks (``text``, ``tool_use``, ``thinking``).",
    )
    stop_reason: str | None = Field(
        default=None,
        title="stop_reason",
        description="Why generation ended (``end_turn``, ``max_tokens``, ``tool_use``, ``stop_sequence``).",
    )
    stop_sequence: str | None = Field(
        default=None,
        title="stop_sequence",
        description="Stop sequence that terminated generation (or ``null``).",
    )
    usage: MessagesUsage | None = Field(default=None, title="usage", description="Token usage tally.")


SCHEMAS["flama.llm_anthropic.MessagesOutput"] = MessagesOutput


class ModelInfo(BaseModel):
    """Single entry returned by Anthropic ``GET /v1/models``.

    ``extra="allow"`` keeps Flama-specific extensions (notably the ``capabilities`` map) flowing through
    the validator unchanged.
    """

    model_config = ConfigDict(extra="allow")

    id: str = Field(title="id", description="Model identifier.")
    type: t.Literal["model"] = Field(default="model", title="type", description="Entry kind discriminator.")
    display_name: str = Field(
        title="display_name",
        description="Human-readable model name; Flama mirrors the resource name.",
    )
    created_at: str = Field(
        title="created_at",
        description="ISO-8601 timestamp at which the model was registered.",
    )


SCHEMAS["flama.llm_anthropic.ModelInfo"] = ModelInfo


class ModelsOutput(BaseModel):
    """Anthropic ``GET /v1/models`` response body."""

    data: list[ModelInfo] = Field(
        title="data",
        description="List of available models; Flama returns a single entry per resource.",
    )
    has_more: bool = Field(
        default=False,
        title="has_more",
        description="Pagination flag; Flama always returns false (single-page response).",
    )
    first_id: str | None = Field(
        default=None,
        title="first_id",
        description="Cursor anchor (id of the first entry).",
    )
    last_id: str | None = Field(
        default=None,
        title="last_id",
        description="Cursor anchor (id of the last entry).",
    )


SCHEMAS["flama.llm_anthropic.ModelsOutput"] = ModelsOutput
