from typesystem import Reference, Schema, fields

from flama.schemas._libs.typesystem.schemas.core import SCHEMAS

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

ChatInput = Schema(
    title="ChatInput",
    fields={
        "model": fields.String(title="model", description="Model identifier; echoed back in the response."),
        "messages": fields.Array(
            title="messages",
            description="Conversation messages. Each entry must have 'role' and 'content' / 'tool_calls'.",
            items=Reference(to="flama.llm_native.Message", definitions=SCHEMAS),
        ),
        "stream": fields.Boolean(title="stream", description="If true (default), stream NDJSON chunks.", default=True),
        "tools": fields.Array(
            title="tools",
            description="Function-tool specs advertised to the model.",
            items=Reference(to="flama.llm_native.Tool", definitions=SCHEMAS),
            allow_null=True,
            default=None,
        ),
        "think": fields.Boolean(
            title="think",
            description=(
                "Boolean override of the resource's reasoning toggle. When omitted, falls back to the "
                "resource-level ``reasoning`` flag (default: enabled when the backend supports thinking)."
            ),
            allow_null=True,
            default=None,
        ),
    },
)
SCHEMAS["flama.llm_ollama.ChatInput"] = ChatInput

ChatOutput = Schema(
    title="ChatOutput",
    fields={
        "model": fields.String(title="model", description="Model identifier; echoes the request."),
        "created_at": fields.String(
            title="created_at", description="ISO-8601 timestamp at which the response was produced."
        ),
        "message": Reference(to="flama.llm_native.Message", definitions=SCHEMAS),
        "done": fields.Boolean(
            title="done", description="Terminal flag; always true for buffered responses.", default=True
        ),
        "done_reason": fields.String(
            title="done_reason",
            description="Why generation stopped (e.g. 'stop', 'length').",
            allow_null=True,
            default=None,
        ),
        "prompt_eval_count": fields.Integer(
            title="prompt_eval_count", description="Input token count.", allow_null=True, default=None
        ),
        "eval_count": fields.Integer(
            title="eval_count", description="Output token count.", allow_null=True, default=None
        ),
    },
)
SCHEMAS["flama.llm_ollama.ChatOutput"] = ChatOutput

ChatChunk = Schema(
    title="ChatChunk",
    fields={
        "model": fields.String(title="model", description="Model identifier."),
        "created_at": fields.String(
            title="created_at", description="ISO-8601 timestamp at which the chunk was produced."
        ),
        "message": Reference(to="flama.llm_native.Message", definitions=SCHEMAS),
        "done": fields.Boolean(title="done", description="True only on the terminal frame.", default=False),
        "done_reason": fields.String(
            title="done_reason", description="Why generation stopped.", allow_null=True, default=None
        ),
        "prompt_eval_count": fields.Integer(
            title="prompt_eval_count",
            description="Input token count (terminal frame).",
            allow_null=True,
            default=None,
        ),
        "eval_count": fields.Integer(
            title="eval_count",
            description="Output token count (terminal frame).",
            allow_null=True,
            default=None,
        ),
    },
)
SCHEMAS["flama.llm_ollama.ChatChunk"] = ChatChunk

GenerateInput = Schema(
    title="GenerateInput",
    fields={
        "model": fields.String(title="model", description="Model identifier; echoed back in the response."),
        "prompt": fields.String(title="prompt", description="Input prompt."),
        "stream": fields.Boolean(title="stream", description="If true (default), stream NDJSON chunks.", default=True),
        "system": fields.String(
            title="system", description="Optional system instruction.", allow_null=True, default=None
        ),
    },
)
SCHEMAS["flama.llm_ollama.GenerateInput"] = GenerateInput

GenerateOutput = Schema(
    title="GenerateOutput",
    fields={
        "model": fields.String(title="model", description="Model identifier; echoes the request."),
        "created_at": fields.String(
            title="created_at", description="ISO-8601 timestamp at which the response was produced."
        ),
        "response": fields.String(title="response", description="Assembled completion text."),
        "done": fields.Boolean(
            title="done", description="Terminal flag; always true for buffered responses.", default=True
        ),
        "done_reason": fields.String(
            title="done_reason", description="Why generation stopped.", allow_null=True, default=None
        ),
        "prompt_eval_count": fields.Integer(
            title="prompt_eval_count", description="Input token count.", allow_null=True, default=None
        ),
        "eval_count": fields.Integer(
            title="eval_count", description="Output token count.", allow_null=True, default=None
        ),
    },
)
SCHEMAS["flama.llm_ollama.GenerateOutput"] = GenerateOutput

GenerateChunk = Schema(
    title="GenerateChunk",
    fields={
        "model": fields.String(title="model", description="Model identifier."),
        "created_at": fields.String(
            title="created_at", description="ISO-8601 timestamp at which the chunk was produced."
        ),
        "response": fields.String(title="response", description="Incremental completion text delta."),
        "done": fields.Boolean(title="done", description="True only on the terminal frame.", default=False),
        "done_reason": fields.String(
            title="done_reason", description="Why generation stopped.", allow_null=True, default=None
        ),
        "prompt_eval_count": fields.Integer(
            title="prompt_eval_count",
            description="Input token count (terminal frame).",
            allow_null=True,
            default=None,
        ),
        "eval_count": fields.Integer(
            title="eval_count",
            description="Output token count (terminal frame).",
            allow_null=True,
            default=None,
        ),
    },
)
SCHEMAS["flama.llm_ollama.GenerateChunk"] = GenerateChunk

TagEntry = Schema(
    title="TagEntry",
    fields={
        "name": fields.String(title="name", description="Model identifier."),
        "modified_at": fields.String(
            title="modified_at",
            description="ISO-8601 timestamp at which the model was last modified.",
        ),
        "size": fields.Integer(title="size", description="On-disk size in bytes."),
        "digest": fields.String(title="digest", description="Content-addressable digest of the model artifact."),
        "details": fields.Object(
            title="details",
            description="Free-form model details (family, format, parameter_size, quantization_level, ...).",
            default={},
        ),
    },
)
SCHEMAS["flama.llm_ollama.TagEntry"] = TagEntry

TagsOutput = Schema(
    title="TagsOutput",
    fields={
        "models": fields.Array(
            title="models",
            description="List of locally available models; Flama returns a single entry per resource.",
            items=Reference(to="flama.llm_ollama.TagEntry", definitions=SCHEMAS),
        ),
    },
)
SCHEMAS["flama.llm_ollama.TagsOutput"] = TagsOutput

ShowInput = Schema(
    title="ShowInput",
    fields={
        "model": fields.String(
            title="model",
            description="Model identifier (newer field name).",
            allow_null=True,
            default=None,
        ),
        "name": fields.String(
            title="name",
            description="Model identifier (legacy field name).",
            allow_null=True,
            default=None,
        ),
        "verbose": fields.Boolean(
            title="verbose",
            description="Include verbose metadata (currently ignored by Flama).",
            default=False,
        ),
    },
)
SCHEMAS["flama.llm_ollama.ShowInput"] = ShowInput

ShowOutput = Schema(
    title="ShowOutput",
    fields={
        "modelfile": fields.String(
            title="modelfile",
            description="Modelfile source (empty in Flama).",
            allow_blank=True,
            default="",
        ),
        "parameters": fields.String(
            title="parameters",
            description="Modelfile parameters block (empty).",
            allow_blank=True,
            default="",
        ),
        "template": fields.String(
            title="template",
            description="Prompt template source (empty).",
            allow_blank=True,
            default="",
        ),
        "details": fields.Object(
            title="details",
            description="Free-form model details (family, format, parameter_size, quantization_level, …).",
        ),
        "model_info": fields.Object(
            title="model_info",
            description="Architectural facts (``general.architecture``, context length, …) used for capability gating.",
        ),
        "capabilities": fields.Array(
            title="capabilities",
            description=(
                "Capability tokens consumed by clients; Flama advertises ``completion`` plus the supported subset "
                "of ``tools`` / ``vision`` / ``audio`` / ``thinking`` based on the loaded model's capabilities."
            ),
            items=fields.String(),
        ),
    },
)
SCHEMAS["flama.llm_ollama.ShowOutput"] = ShowOutput

VersionOutput = Schema(
    title="VersionOutput",
    fields={
        "version": fields.String(
            title="version", description="Server version string; Flama returns its own package version."
        ),
    },
)
SCHEMAS["flama.llm_ollama.VersionOutput"] = VersionOutput
