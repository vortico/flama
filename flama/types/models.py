import typing as t

__all__ = [
    "ModelLib",
    "ModelFamily",
    "LLMEngineChannelScanners",
    "LLMEngineToolParsers",
    "LLMEngineToolScanners",
    "LLMTransportContentType",
    "LLMTransportEvent",
    "LLMTransportRole",
    "LLMTransportShape",
    "LLMTransportStopReason",
    "LLMRuntime",
    "LLMServing",
]

ModelLib = t.Literal["sklearn", "tensorflow", "torch", "keras", "transformers"]
ModelFamily = t.Literal["llm", "ml"]

# LLM Engine Layer
LLMEngineChannelScanners = t.Literal["passthrough", "harmony", "channel", "think"]
LLMEngineToolScanners = t.Literal[
    "passthrough", "tool_call", "tool_calls", "python_tag", "pythonic", "python_block", "tool_call_pipe"
]
LLMEngineToolParsers = t.Literal[
    "passthrough", "json_object", "json_array", "json_sequence", "named_json_sequence", "pythonic", "call_notation"
]

# LLM Transport Layer
LLMTransportContentType = t.Literal["text", "image:url", "image:uri", "audio:url", "audio:uri"]
LLMTransportEvent = t.Literal["start", "stop", "text", "tool", "trace"]
LLMTransportRole = t.Literal["system", "user", "assistant", "tool"]
LLMTransportShape = t.Literal["raw", "chat", "conversation"]
LLMTransportStopReason = t.Literal[
    "stop",
    "max_tokens",
    "tool_use",
    "content_filter",
    "cancelled",
    "error",
    "unknown",
]

LLMRuntime = t.Literal["vllm", "mlx"]
LLMServing = t.Literal["native", "openai", "ollama", "anthropic"]
