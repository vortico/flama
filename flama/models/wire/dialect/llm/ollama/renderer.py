import typing as t
from datetime import datetime, timezone

from flama import types
from flama.models.transport.output.llm.event import StartEvent, StopEvent, TextEvent, ToolEvent, TraceEvent
from flama.models.wire.dialect._base import Renderer

__all__ = ["OllamaRenderer"]


class OllamaRenderer(Renderer[types.JSONSchema]):
    """L2 -> Ollama NDJSON strategy.

    Public renderer for the Ollama dialect. Two wire formats coexist behind a *api* dial - ``"chat"`` emits
    ``/api/chat`` frames (running ``message.content`` deltas, optional ``message.tool_calls`` blocks, and a
    terminal ``done: true`` frame); ``"generate"`` emits ``/api/generate`` frames (running ``response``
    deltas plus a terminal frame) and suppresses tool calls (the legacy raw endpoint has no tool semantics).

    Non-``output`` channel text is routed to the ``message.thinking`` field (Ollama's thinking-model
    contract, triggered by ``think: true`` in the request), and a :class:`~flama.models.StopEvent` with
    ``stop_reason="error"`` injects an ``{"error": "..."}`` frame before the terminal frame. Running
    ``input_tokens`` / ``output_tokens`` totals captured from :class:`~flama.models.StartEvent` and
    :class:`~flama.models.TraceEvent` are stamped on the terminal frame's ``prompt_eval_count`` /
    ``eval_count``. No role-opening frame is emitted (Ollama frames are self-describing) and no ``[DONE]``
    sentinel is appended (the terminal frame's ``done: true`` is the EOS signal).

    :param api: ``"chat"`` (chat frame shape) or ``"generate"`` (generate frame shape).
    :param model: Model identifier echoed on every frame.
    """

    _STOP_REASON_TO_OLLAMA: t.Final[dict[types.LLMTransportStopReason, str]] = {
        "stop": "stop",
        "max_tokens": "length",
        "tool_use": "stop",
        "content_filter": "stop",
        "cancelled": "stop",
        "error": "stop",
        "unknown": "stop",
    }

    def __init__(self, *, api: t.Literal["chat", "generate"], model: str) -> None:
        self._api = api
        self._model = model
        self._input_tokens = 0
        self._output_tokens = 0

    def _envelope(self, body: dict[str, t.Any], /) -> types.JSONSchema:
        return {"model": self._model, "created_at": datetime.now(timezone.utc).isoformat(), **body}

    def on_start(self, block: StartEvent) -> t.Iterable[types.JSONSchema]:
        if block.input_tokens is not None:
            self._input_tokens = block.input_tokens
        return ()

    def on_text(self, block: TextEvent) -> t.Iterable[types.JSONSchema]:
        if not block.text:
            return
        if block.channel == "output":
            if self._api == "chat":
                yield self._envelope({"message": {"role": "assistant", "content": block.text}, "done": False})
            else:
                yield self._envelope({"response": block.text, "done": False})
        elif self._api == "chat":
            yield self._envelope(
                {"message": {"role": "assistant", "content": "", "thinking": block.text}, "done": False}
            )

    def on_tool(self, block: ToolEvent) -> t.Iterable[types.JSONSchema]:
        if self._api != "chat" or not block.name:
            return
        yield self._envelope(
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{"function": {"name": block.name, "arguments": block.arguments}}],
                },
                "done": False,
            }
        )

    def on_trace(self, block: TraceEvent) -> t.Iterable[types.JSONSchema]:
        if block.token_count is not None and block.token_count > 0:
            self._output_tokens += block.token_count
        return ()

    def on_stop(self, block: StopEvent) -> t.Iterable[types.JSONSchema]:
        if block.stop_reason == "error":
            yield {"error": "LLM stream generation failed"}
        done_reason = self._STOP_REASON_TO_OLLAMA.get(block.stop_reason, "stop") if block.stop_reason else "stop"
        output_tokens = block.output_tokens if block.output_tokens is not None else self._output_tokens
        terminal: dict[str, t.Any] = {
            "done": True,
            "done_reason": done_reason,
            "prompt_eval_count": self._input_tokens,
            "eval_count": output_tokens,
        }
        if self._api == "chat":
            yield self._envelope({"message": {"role": "assistant", "content": ""}, **terminal})
        else:
            yield self._envelope({"response": "", **terminal})
