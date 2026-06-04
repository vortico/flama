import typing as t

from pydantic import BaseModel, ConfigDict, Field

from flama.schemas._libs.pydantic.schemas.core import SCHEMAS
from flama.schemas._libs.pydantic.schemas.llm_native import Message, Tool

__all__ = [
    "ChatChunk",
    "ChatInput",
    "ChatOutput",
    "GenerateChunk",
    "GenerateInput",
    "GenerateOutput",
    "ShowInput",
    "ShowOutput",
    "TagEntry",
    "TagsOutput",
    "VersionOutput",
]


class ChatInput(BaseModel):
    """Ollama ``POST /api/chat`` request body.

    Permissive: unknown sampling parameters are accepted and forwarded to the underlying model as generation params.
    """

    model_config = ConfigDict(extra="allow")

    model: str = Field(title="model", description="Model identifier; echoed back in the response.")
    messages: list[Message] = Field(
        title="messages",
        description="Conversation messages. Each entry must have 'role' and 'content' / 'tool_calls'.",
    )
    stream: bool = Field(default=True, title="stream", description="If true (default), stream NDJSON chunks.")
    tools: list[Tool] | None = Field(
        default=None, title="tools", description="Function-tool specs advertised to the model."
    )
    think: bool | None = Field(
        default=None,
        title="think",
        description=(
            "Boolean override of the resource's reasoning toggle. When omitted, falls back to the resource-level "
            "``reasoning`` flag (default: enabled when the backend supports thinking)."
        ),
    )


SCHEMAS["flama.llm_ollama.ChatInput"] = ChatInput


class ChatOutput(BaseModel):
    """Ollama ``POST /api/chat`` non-streaming response body."""

    model: str = Field(title="model", description="Model identifier; echoes the request.")
    created_at: str = Field(title="created_at", description="ISO-8601 timestamp at which the response was produced.")
    message: Message = Field(title="message", description="Assistant turn (role, content, optional tool_calls).")
    done: t.Literal[True] = Field(
        default=True, title="done", description="Terminal flag; always true for buffered responses."
    )
    done_reason: str | None = Field(
        default=None, title="done_reason", description="Why generation stopped (e.g. 'stop', 'length')."
    )
    prompt_eval_count: int | None = Field(default=None, title="prompt_eval_count", description="Input token count.")
    eval_count: int | None = Field(default=None, title="eval_count", description="Output token count.")


SCHEMAS["flama.llm_ollama.ChatOutput"] = ChatOutput


class ChatChunk(BaseModel):
    """Ollama ``POST /api/chat`` streaming chunk body (documentary; chunks are serialised manually).

    Frames are emitted as newline-delimited JSON objects (``application/x-ndjson``). The final frame carries
    ``done: true`` and the usage tally.
    """

    model: str = Field(title="model", description="Model identifier.")
    created_at: str = Field(title="created_at", description="ISO-8601 timestamp at which the chunk was produced.")
    message: Message = Field(title="message", description="Incremental assistant turn delta.")
    done: bool = Field(default=False, title="done", description="True only on the terminal frame.")
    done_reason: str | None = Field(default=None, title="done_reason", description="Why generation stopped.")
    prompt_eval_count: int | None = Field(
        default=None, title="prompt_eval_count", description="Input token count (terminal frame)."
    )
    eval_count: int | None = Field(default=None, title="eval_count", description="Output token count (terminal frame).")


SCHEMAS["flama.llm_ollama.ChatChunk"] = ChatChunk


class GenerateInput(BaseModel):
    """Ollama ``POST /api/generate`` request body (raw prompt completion).

    Permissive: unknown sampling parameters are accepted and forwarded to the underlying model as generation params.
    """

    model_config = ConfigDict(extra="allow")

    model: str = Field(title="model", description="Model identifier; echoed back in the response.")
    prompt: str = Field(title="prompt", description="Input prompt.")
    stream: bool = Field(default=True, title="stream", description="If true (default), stream NDJSON chunks.")
    system: str | None = Field(default=None, title="system", description="Optional system instruction.")


SCHEMAS["flama.llm_ollama.GenerateInput"] = GenerateInput


class GenerateOutput(BaseModel):
    """Ollama ``POST /api/generate`` non-streaming response body."""

    model: str = Field(title="model", description="Model identifier; echoes the request.")
    created_at: str = Field(title="created_at", description="ISO-8601 timestamp at which the response was produced.")
    response: str = Field(title="response", description="Assembled completion text.")
    done: t.Literal[True] = Field(
        default=True, title="done", description="Terminal flag; always true for buffered responses."
    )
    done_reason: str | None = Field(default=None, title="done_reason", description="Why generation stopped.")
    prompt_eval_count: int | None = Field(default=None, title="prompt_eval_count", description="Input token count.")
    eval_count: int | None = Field(default=None, title="eval_count", description="Output token count.")


SCHEMAS["flama.llm_ollama.GenerateOutput"] = GenerateOutput


class GenerateChunk(BaseModel):
    """Ollama ``POST /api/generate`` streaming chunk body (documentary; chunks are serialised manually)."""

    model: str = Field(title="model", description="Model identifier.")
    created_at: str = Field(title="created_at", description="ISO-8601 timestamp at which the chunk was produced.")
    response: str = Field(title="response", description="Incremental completion text delta.")
    done: bool = Field(default=False, title="done", description="True only on the terminal frame.")
    done_reason: str | None = Field(default=None, title="done_reason", description="Why generation stopped.")
    prompt_eval_count: int | None = Field(
        default=None, title="prompt_eval_count", description="Input token count (terminal frame)."
    )
    eval_count: int | None = Field(default=None, title="eval_count", description="Output token count (terminal frame).")


SCHEMAS["flama.llm_ollama.GenerateChunk"] = GenerateChunk


class TagEntry(BaseModel):
    """Single registry entry returned by ``GET /api/tags``."""

    model_config = ConfigDict(extra="allow")

    name: str = Field(title="name", description="Model identifier.")
    modified_at: str = Field(
        title="modified_at", description="ISO-8601 timestamp at which the model was last modified."
    )
    size: int = Field(title="size", description="On-disk size in bytes.")
    digest: str = Field(title="digest", description="Content-addressable digest of the model artifact.")
    details: dict[str, t.Any] = Field(
        default_factory=dict,
        title="details",
        description="Free-form model details (family, format, parameter_size, quantization_level, ...).",
    )


SCHEMAS["flama.llm_ollama.TagEntry"] = TagEntry


class TagsOutput(BaseModel):
    """Ollama ``GET /api/tags`` response body."""

    models: list[TagEntry] = Field(
        title="models", description="List of locally available models; Flama returns a single entry per resource."
    )


SCHEMAS["flama.llm_ollama.TagsOutput"] = TagsOutput


class ShowInput(BaseModel):
    """Ollama ``POST /api/show`` request body.

    Both ``model`` (newer clients) and ``name`` (legacy clients) carry the model identifier; either is accepted
    and the path-routed resource name takes precedence in any case.
    """

    model_config = ConfigDict(extra="allow")

    model: str | None = Field(default=None, title="model", description="Model identifier (newer field name).")
    name: str | None = Field(default=None, title="name", description="Model identifier (legacy field name).")
    verbose: bool = Field(
        default=False, title="verbose", description="Include verbose metadata (currently ignored by Flama)."
    )


SCHEMAS["flama.llm_ollama.ShowInput"] = ShowInput


class ShowOutput(BaseModel):
    """Ollama ``POST /api/show`` response body.

    Mirrors the shape returned by upstream Ollama so clients that probe ``/api/show`` for capability discovery
    (GitHub Copilot Chat, OpenWebUI, LiteLLM) can negotiate against Flama. Most string fields are intentionally
    empty: Flama does not persist a Modelfile / template / parameters block, but the keys must be present for
    strict clients.
    """

    model_config = ConfigDict(protected_namespaces=())

    modelfile: str = Field(default="", title="modelfile", description="Modelfile source (empty in Flama).")
    parameters: str = Field(default="", title="parameters", description="Modelfile parameters block (empty).")
    template: str = Field(default="", title="template", description="Prompt template source (empty).")
    details: dict[str, t.Any] = Field(
        title="details",
        description="Free-form model details (family, format, parameter_size, quantization_level, …).",
    )
    model_info: dict[str, t.Any] = Field(
        title="model_info",
        description="Architectural facts (``general.architecture``, context length, …) used for capability gating.",
    )
    capabilities: list[str] = Field(
        title="capabilities",
        description=(
            "Capability tokens consumed by clients; Flama advertises ``completion`` plus the supported subset of "
            "``tools`` / ``vision`` / ``audio`` / ``thinking`` based on the loaded model's capabilities."
        ),
    )


SCHEMAS["flama.llm_ollama.ShowOutput"] = ShowOutput


class VersionOutput(BaseModel):
    """Ollama ``GET /api/version`` response body."""

    version: str = Field(title="version", description="Server version string; Flama returns its own package version.")


SCHEMAS["flama.llm_ollama.VersionOutput"] = VersionOutput
