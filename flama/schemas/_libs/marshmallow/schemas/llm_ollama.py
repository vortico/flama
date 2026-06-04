import marshmallow

from flama.schemas._libs.marshmallow.schemas.core import SCHEMAS
from flama.schemas._libs.marshmallow.schemas.llm_native import Message, Tool

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


class ChatInput(marshmallow.Schema):
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
            "description": "Conversation messages. Each entry must have 'role' and 'content' / 'tool_calls'.",
        },
    )
    stream = marshmallow.fields.Boolean(
        load_default=True,
        metadata={"title": "stream", "description": "If true (default), stream NDJSON chunks."},
    )
    tools = marshmallow.fields.List(
        marshmallow.fields.Nested(Tool()),
        load_default=None,
        allow_none=True,
        metadata={"title": "tools", "description": "Function-tool specs advertised to the model."},
    )
    think = marshmallow.fields.Boolean(
        load_default=None,
        allow_none=True,
        metadata={
            "title": "think",
            "description": (
                "Boolean override of the resource's reasoning toggle. When omitted, falls back to the "
                "resource-level ``reasoning`` flag (default: enabled when the backend supports thinking)."
            ),
        },
    )


SCHEMAS["flama.llm_ollama.ChatInput"] = ChatInput


class ChatOutput(marshmallow.Schema):
    model = marshmallow.fields.String(
        required=True, metadata={"title": "model", "description": "Model identifier; echoes the request."}
    )
    created_at = marshmallow.fields.String(
        required=True,
        metadata={"title": "created_at", "description": "ISO-8601 timestamp at which the response was produced."},
    )
    message = marshmallow.fields.Nested(
        Message,
        required=True,
        metadata={"title": "message", "description": "Assistant turn (role, content, optional tool_calls)."},
    )
    done = marshmallow.fields.Boolean(
        load_default=True,
        metadata={"title": "done", "description": "Terminal flag; always true for buffered responses."},
    )
    done_reason = marshmallow.fields.String(
        load_default=None,
        allow_none=True,
        metadata={"title": "done_reason", "description": "Why generation stopped (e.g. 'stop', 'length')."},
    )
    prompt_eval_count = marshmallow.fields.Integer(
        load_default=None,
        allow_none=True,
        metadata={"title": "prompt_eval_count", "description": "Input token count."},
    )
    eval_count = marshmallow.fields.Integer(
        load_default=None,
        allow_none=True,
        metadata={"title": "eval_count", "description": "Output token count."},
    )


SCHEMAS["flama.llm_ollama.ChatOutput"] = ChatOutput


class ChatChunk(marshmallow.Schema):
    model = marshmallow.fields.String(required=True, metadata={"title": "model", "description": "Model identifier."})
    created_at = marshmallow.fields.String(
        required=True,
        metadata={"title": "created_at", "description": "ISO-8601 timestamp at which the chunk was produced."},
    )
    message = marshmallow.fields.Nested(
        Message,
        required=True,
        metadata={"title": "message", "description": "Incremental assistant turn delta."},
    )
    done = marshmallow.fields.Boolean(
        load_default=False, metadata={"title": "done", "description": "True only on the terminal frame."}
    )
    done_reason = marshmallow.fields.String(
        load_default=None,
        allow_none=True,
        metadata={"title": "done_reason", "description": "Why generation stopped."},
    )
    prompt_eval_count = marshmallow.fields.Integer(
        load_default=None,
        allow_none=True,
        metadata={"title": "prompt_eval_count", "description": "Input token count (terminal frame)."},
    )
    eval_count = marshmallow.fields.Integer(
        load_default=None,
        allow_none=True,
        metadata={"title": "eval_count", "description": "Output token count (terminal frame)."},
    )


SCHEMAS["flama.llm_ollama.ChatChunk"] = ChatChunk


class GenerateInput(marshmallow.Schema):
    class Meta:
        unknown = marshmallow.INCLUDE

    model = marshmallow.fields.String(
        required=True,
        metadata={"title": "model", "description": "Model identifier; echoed back in the response."},
    )
    prompt = marshmallow.fields.String(required=True, metadata={"title": "prompt", "description": "Input prompt."})
    stream = marshmallow.fields.Boolean(
        load_default=True,
        metadata={"title": "stream", "description": "If true (default), stream NDJSON chunks."},
    )
    system = marshmallow.fields.String(
        load_default=None,
        allow_none=True,
        metadata={"title": "system", "description": "Optional system instruction."},
    )


SCHEMAS["flama.llm_ollama.GenerateInput"] = GenerateInput


class GenerateOutput(marshmallow.Schema):
    model = marshmallow.fields.String(
        required=True, metadata={"title": "model", "description": "Model identifier; echoes the request."}
    )
    created_at = marshmallow.fields.String(
        required=True,
        metadata={"title": "created_at", "description": "ISO-8601 timestamp at which the response was produced."},
    )
    response = marshmallow.fields.String(
        required=True, metadata={"title": "response", "description": "Assembled completion text."}
    )
    done = marshmallow.fields.Boolean(
        load_default=True,
        metadata={"title": "done", "description": "Terminal flag; always true for buffered responses."},
    )
    done_reason = marshmallow.fields.String(
        load_default=None,
        allow_none=True,
        metadata={"title": "done_reason", "description": "Why generation stopped."},
    )
    prompt_eval_count = marshmallow.fields.Integer(
        load_default=None,
        allow_none=True,
        metadata={"title": "prompt_eval_count", "description": "Input token count."},
    )
    eval_count = marshmallow.fields.Integer(
        load_default=None,
        allow_none=True,
        metadata={"title": "eval_count", "description": "Output token count."},
    )


SCHEMAS["flama.llm_ollama.GenerateOutput"] = GenerateOutput


class GenerateChunk(marshmallow.Schema):
    model = marshmallow.fields.String(required=True, metadata={"title": "model", "description": "Model identifier."})
    created_at = marshmallow.fields.String(
        required=True,
        metadata={"title": "created_at", "description": "ISO-8601 timestamp at which the chunk was produced."},
    )
    response = marshmallow.fields.String(
        required=True, metadata={"title": "response", "description": "Incremental completion text delta."}
    )
    done = marshmallow.fields.Boolean(
        load_default=False, metadata={"title": "done", "description": "True only on the terminal frame."}
    )
    done_reason = marshmallow.fields.String(
        load_default=None,
        allow_none=True,
        metadata={"title": "done_reason", "description": "Why generation stopped."},
    )
    prompt_eval_count = marshmallow.fields.Integer(
        load_default=None,
        allow_none=True,
        metadata={"title": "prompt_eval_count", "description": "Input token count (terminal frame)."},
    )
    eval_count = marshmallow.fields.Integer(
        load_default=None,
        allow_none=True,
        metadata={"title": "eval_count", "description": "Output token count (terminal frame)."},
    )


SCHEMAS["flama.llm_ollama.GenerateChunk"] = GenerateChunk


class TagEntry(marshmallow.Schema):
    """Single registry entry returned by ``GET /api/tags``."""

    class Meta:
        unknown = marshmallow.INCLUDE

    name = marshmallow.fields.String(
        required=True,
        metadata={"title": "name", "description": "Model identifier."},
    )
    modified_at = marshmallow.fields.String(
        required=True,
        metadata={
            "title": "modified_at",
            "description": "ISO-8601 timestamp at which the model was last modified.",
        },
    )
    size = marshmallow.fields.Integer(
        required=True,
        metadata={"title": "size", "description": "On-disk size in bytes."},
    )
    digest = marshmallow.fields.String(
        required=True,
        metadata={"title": "digest", "description": "Content-addressable digest of the model artifact."},
    )
    details = marshmallow.fields.Dict(
        load_default=dict,
        metadata={
            "title": "details",
            "description": "Free-form model details (family, format, parameter_size, quantization_level, ...).",
        },
    )


SCHEMAS["flama.llm_ollama.TagEntry"] = TagEntry


class TagsOutput(marshmallow.Schema):
    models = marshmallow.fields.List(
        marshmallow.fields.Nested(TagEntry()),
        required=True,
        metadata={
            "title": "models",
            "description": "List of locally available models; Flama returns a single entry per resource.",
        },
    )


SCHEMAS["flama.llm_ollama.TagsOutput"] = TagsOutput


class ShowInput(marshmallow.Schema):
    class Meta:
        unknown = marshmallow.INCLUDE

    model = marshmallow.fields.String(
        load_default=None,
        allow_none=True,
        metadata={"title": "model", "description": "Model identifier (newer field name)."},
    )
    name = marshmallow.fields.String(
        load_default=None,
        allow_none=True,
        metadata={"title": "name", "description": "Model identifier (legacy field name)."},
    )
    verbose = marshmallow.fields.Boolean(
        load_default=False,
        metadata={"title": "verbose", "description": "Include verbose metadata (currently ignored by Flama)."},
    )


SCHEMAS["flama.llm_ollama.ShowInput"] = ShowInput


class ShowOutput(marshmallow.Schema):
    modelfile = marshmallow.fields.String(
        load_default="",
        metadata={"title": "modelfile", "description": "Modelfile source (empty in Flama)."},
    )
    parameters = marshmallow.fields.String(
        load_default="",
        metadata={"title": "parameters", "description": "Modelfile parameters block (empty)."},
    )
    template = marshmallow.fields.String(
        load_default="",
        metadata={"title": "template", "description": "Prompt template source (empty)."},
    )
    details = marshmallow.fields.Dict(
        required=True,
        metadata={
            "title": "details",
            "description": "Free-form model details (family, format, parameter_size, quantization_level, …).",
        },
    )
    model_info = marshmallow.fields.Dict(
        required=True,
        metadata={
            "title": "model_info",
            "description": (
                "Architectural facts (``general.architecture``, context length, …) used for capability gating."
            ),
        },
    )
    capabilities = marshmallow.fields.List(
        marshmallow.fields.String(),
        required=True,
        metadata={
            "title": "capabilities",
            "description": (
                "Capability tokens consumed by clients; Flama advertises ``completion`` plus the supported subset "
                "of ``tools`` / ``vision`` / ``audio`` / ``thinking`` based on the loaded model's capabilities."
            ),
        },
    )


SCHEMAS["flama.llm_ollama.ShowOutput"] = ShowOutput


class VersionOutput(marshmallow.Schema):
    version = marshmallow.fields.String(
        required=True,
        metadata={
            "title": "version",
            "description": "Server version string; Flama returns its own package version.",
        },
    )


SCHEMAS["flama.llm_ollama.VersionOutput"] = VersionOutput
