import json
import string
import time
import typing as t
import uuid

from flama import types
from flama._core.json_encoder import encode_json
from flama.http.responses.sse import ServerSentEvent
from flama.models.transport.output.llm.event import StartEvent, StopEvent, TextEvent, ToolEvent
from flama.models.wire.dialect.base import Renderer

__all__ = ["OpenAIRenderer"]


class _ChatCompletionRenderer(Renderer[ServerSentEvent]):
    """L2 -> OpenAI chat-completions / completions SSE strategy.

    Internal delegate driving the chat-stream FSM (role, content, tool-call, terminal). ``"chat"`` mode emits
    ``chat.completion.chunk`` envelopes; ``"completion"`` mode emits ``text_completion`` envelopes and
    suppresses tool calls and non-``output`` channels (the legacy completion endpoint has no tool semantics).

    Off-output (``thinking``) channel text always projects to ``delta.reasoning_content`` (the DeepSeek
    convention picked up by Continue / Cline / Avante.nvim / Open WebUI / Roo / Kilo / newer Copilot Chat).
    Clients that don't parse this field receive empty deltas; the OpenAI Responses API surface (mounted at
    ``/v1/responses``) is the recommended channel for those clients.
    """

    _STOP_REASON_TO_OPENAI: t.Final[dict[types.LLMTransportStopReason, str]] = {
        "stop": "stop",
        "max_tokens": "length",
        "tool_use": "tool_calls",
        "content_filter": "content_filter",
        "cancelled": "stop",
        "error": "stop",
        "unknown": "stop",
    }

    def __init__(
        self,
        *,
        api: t.Literal["chat", "completion"],
        model: str,
        id: str,
        created: int,
    ) -> None:
        self._api = api
        self._model = model
        self._id = id
        self._created = created
        self._tool_index = -1
        self._role_emitted = False

    def _envelope(self, choice: dict[str, t.Any], /, **extras: t.Any) -> ServerSentEvent:
        object_kind = "chat.completion.chunk" if self._api == "chat" else "text_completion"
        body: dict[str, t.Any] = {
            "id": self._id,
            "object": object_kind,
            "created": self._created,
            "model": self._model,
            "choices": [choice],
            **extras,
        }
        return ServerSentEvent(data=encode_json(body, compact=True).decode())

    def on_start(self, block: StartEvent) -> t.Iterable[ServerSentEvent]:
        if self._api == "chat" and not self._role_emitted:
            self._role_emitted = True
            yield self._envelope({"index": 0, "delta": {"role": "assistant"}, "finish_reason": None})

    def on_text(self, block: TextEvent) -> t.Iterable[ServerSentEvent]:
        if not block.text:
            return
        if block.channel == "output":
            if self._api == "chat":
                yield self._envelope({"index": 0, "delta": {"content": block.text}, "finish_reason": None})
            else:
                yield self._envelope({"index": 0, "text": block.text, "finish_reason": None})
            return
        if self._api == "completion":
            return
        yield self._envelope({"index": 0, "delta": {"reasoning_content": block.text}, "finish_reason": None})

    def on_tool(self, block: ToolEvent) -> t.Iterable[ServerSentEvent]:
        if self._api == "completion" or not block.name:
            return
        self._tool_index += 1
        yield self._envelope(
            {
                "index": 0,
                "delta": {
                    "tool_calls": [
                        {
                            "index": self._tool_index,
                            "id": block.id,
                            "type": "function",
                            "function": {"name": block.name, "arguments": json.dumps(block.arguments)},
                        }
                    ],
                },
                "finish_reason": None,
            }
        )

    def on_stop(self, block: StopEvent) -> t.Iterable[ServerSentEvent]:
        if block.stop_reason == "error":
            yield self._envelope(
                {"index": 0, "delta": {}, "finish_reason": None},
                error={"message": "LLM stream generation failed", "type": "internal_error", "code": 500},
            )
        finish = self._STOP_REASON_TO_OPENAI.get(block.stop_reason, "stop") if block.stop_reason else "stop"
        if self._api == "chat":
            yield self._envelope({"index": 0, "delta": {}, "finish_reason": finish})
        else:
            yield self._envelope({"index": 0, "text": "", "finish_reason": finish})
        yield ServerSentEvent(data="[DONE]")

    def flush(self) -> t.Iterable[ServerSentEvent]:
        return ()


class _MessagesRenderer(Renderer[ServerSentEvent]):
    """L2 -> OpenAI Responses API SSE strategy.

    Internal delegate driving the Responses-API FSM. Each frame carries an ``event:`` line with the
    response-event ``type`` (``response.created`` / ``response.output_item.added`` / ...) and a body that
    either lives directly on the data envelope (item / content / delta events) or under a top-level
    ``response`` envelope (lifecycle events).

    Off-output (``thinking``) channel text always opens a parallel ``reasoning_0`` output item driven by
    ``response.reasoning_summary_text.*`` events, matching the structured reasoning shape the OpenAI
    Responses API contract specifies. Clients that don't render reasoning summaries simply ignore those
    items.
    """

    def __init__(
        self,
        *,
        model: str,
        id: str,
        created: int,
    ) -> None:
        self._model = model
        self._id = id
        self._created = created
        self._tool_index = -1
        self._message_open = False
        self._reasoning_open = False
        self._text_parts: list[str] = []
        self._reasoning_parts: list[str] = []
        self._input_tokens = 0

    def _frame(self, type_: str, payload: dict[str, t.Any], /) -> ServerSentEvent:
        return ServerSentEvent(
            event=type_,
            data=encode_json({"type": type_, **payload}, compact=True).decode(),
        )

    def _response_envelope_frame(self, type_: str, status: str, /, **extras: t.Any) -> ServerSentEvent:
        response: dict[str, t.Any] = {
            "id": self._id,
            "object": "response",
            "created_at": self._created,
            "status": status,
            "model": self._model,
            "output": [],
            **extras,
        }
        return ServerSentEvent(
            event=type_,
            data=encode_json({"type": type_, "response": response}, compact=True).decode(),
        )

    def on_start(self, block: StartEvent) -> t.Iterable[ServerSentEvent]:
        self._input_tokens = block.input_tokens or 0
        yield self._response_envelope_frame("response.created", "in_progress")
        yield from self._open_message()

    def on_text(self, block: TextEvent) -> t.Iterable[ServerSentEvent]:
        if not block.text:
            return
        if block.channel == "output":
            yield from self._close_reasoning()
            yield from self._emit_output_text(block.text)
            return
        yield from self._open_reasoning()
        self._reasoning_parts.append(block.text)
        yield self._frame(
            "response.reasoning_summary_text.delta",
            {"output_index": 1, "summary_index": 0, "delta": block.text},
        )

    def on_tool(self, block: ToolEvent) -> t.Iterable[ServerSentEvent]:
        if not block.name:
            return
        yield from self._close_reasoning()
        self._tool_index += 1
        arguments = json.dumps(block.arguments)
        item = {
            "id": block.id,
            "type": "function_call",
            "call_id": block.id,
            "name": block.name,
            "arguments": arguments,
        }
        output_index = self._tool_index + 1
        yield self._frame("response.output_item.added", {"output_index": output_index, "item": item})
        yield self._frame(
            "response.function_call_arguments.delta",
            {"output_index": output_index, "item_id": block.id, "delta": arguments},
        )
        yield self._frame(
            "response.function_call_arguments.done",
            {"output_index": output_index, "item_id": block.id, "arguments": arguments},
        )
        yield self._frame("response.output_item.done", {"output_index": output_index, "item": item})

    def on_stop(self, block: StopEvent) -> t.Iterable[ServerSentEvent]:
        if block.stop_reason == "error":
            yield self._response_envelope_frame(
                "response.failed",
                "failed",
                error={"message": "LLM stream generation failed", "type": "internal_error", "code": 500},
            )
            return
        usage = {
            "input_tokens": self._input_tokens,
            "output_tokens": block.output_tokens or 0,
            "total_tokens": self._input_tokens + (block.output_tokens or 0),
        }
        yield self._response_envelope_frame("response.completed", "completed", usage=usage)

    def flush(self) -> t.Iterable[ServerSentEvent]:
        yield from self._close_reasoning()
        yield from self._close_message()

    def _emit_output_text(self, text: str) -> t.Iterable[ServerSentEvent]:
        yield from self._open_message()
        self._text_parts.append(text)
        yield self._frame(
            "response.output_text.delta",
            {"output_index": 0, "content_index": 0, "delta": text},
        )

    def _open_message(self) -> t.Iterable[ServerSentEvent]:
        if self._message_open:
            return
        self._message_open = True
        item = {
            "id": "msg_0",
            "type": "message",
            "status": "in_progress",
            "role": "assistant",
            "content": [],
        }
        yield self._frame("response.output_item.added", {"output_index": 0, "item": item})
        yield self._frame(
            "response.content_part.added",
            {"output_index": 0, "content_index": 0, "part": {"type": "output_text", "text": ""}},
        )

    def _close_message(self) -> t.Iterable[ServerSentEvent]:
        if not self._message_open:
            return
        text = "".join(self._text_parts)
        yield self._frame(
            "response.output_text.done",
            {"output_index": 0, "content_index": 0, "text": text},
        )
        yield self._frame(
            "response.content_part.done",
            {
                "output_index": 0,
                "content_index": 0,
                "part": {"type": "output_text", "text": text},
            },
        )
        item = {
            "id": "msg_0",
            "type": "message",
            "status": "completed",
            "role": "assistant",
            "content": [{"type": "output_text", "text": text}],
        }
        yield self._frame("response.output_item.done", {"output_index": 0, "item": item})
        self._message_open = False

    def _open_reasoning(self) -> t.Iterable[ServerSentEvent]:
        if self._reasoning_open:
            return
        self._reasoning_open = True
        item = {"id": "reasoning_0", "type": "reasoning", "status": "in_progress", "summary": []}
        yield self._frame("response.output_item.added", {"output_index": 1, "item": item})

    def _close_reasoning(self) -> t.Iterable[ServerSentEvent]:
        if not self._reasoning_open:
            return
        text = "".join(self._reasoning_parts)
        yield self._frame(
            "response.reasoning_summary_text.done",
            {"output_index": 1, "summary_index": 0, "text": text},
        )
        item = {
            "id": "reasoning_0",
            "type": "reasoning",
            "status": "completed",
            "summary": [{"type": "summary_text", "text": text}],
        }
        yield self._frame("response.output_item.done", {"output_index": 1, "item": item})
        self._reasoning_open = False


class OpenAIRenderer(Renderer[ServerSentEvent]):
    """L2 -> OpenAI SSE strategy.

    Public renderer for the OpenAI dialect. Picks the appropriate internal FSM strategy based on *api*:
    ``"chat"`` and ``"completion"`` route to the chat-completions / completions chunk shape;
    ``"response"`` routes to the Responses API event shape. Per-stream identity (envelope ``id`` /
    ``model`` / ``created``) is allocated once on construction and stamped onto every emitted frame.

    Reasoning content is always projected via ``delta.reasoning_content`` (chat-completions) or the
    structured ``response.reasoning_summary_text.*`` events (Responses API); see
    :class:`_ChatCompletionRenderer` and :class:`_MessagesRenderer` for the per-mode contract.

    :param api: ``"chat"`` (chat.completion.chunk), ``"completion"`` (text_completion), or ``"response"``
        (Responses API). Selects the FSM family and the envelope ``object`` literal.
    :param model: Model identifier echoed on every frame.
    :param generation_id: Optional generation UUID anchoring the ``chatcmpl-`` / ``cmpl-`` / ``resp-``
        envelope id; a fresh one is allocated when omitted.
    """

    _KIND_PREFIX: t.Final[dict[t.Literal["chat", "completion", "response"], str]] = {
        "chat": "chatcmpl",
        "completion": "cmpl",
        "response": "resp",
    }
    _EVENT_ID_TEMPLATE: t.Final[string.Template] = string.Template("$prefix-$message_id")

    def __init__(
        self,
        *,
        api: t.Literal["chat", "completion", "response"],
        model: str,
        generation_id: uuid.UUID | None = None,
    ) -> None:
        envelope_id = OpenAIRenderer._event_id(api, generation_id)
        created = int(time.time())
        self._delegate: Renderer[ServerSentEvent]
        if api == "chat" or api == "completion":
            self._delegate = _ChatCompletionRenderer(api=api, model=model, id=envelope_id, created=created)
        else:
            self._delegate = _MessagesRenderer(model=model, id=envelope_id, created=created)

    def on_start(self, block: StartEvent) -> t.Iterable[ServerSentEvent]:
        return self._delegate.on_start(block)

    def on_text(self, block: TextEvent) -> t.Iterable[ServerSentEvent]:
        return self._delegate.on_text(block)

    def on_tool(self, block: ToolEvent) -> t.Iterable[ServerSentEvent]:
        return self._delegate.on_tool(block)

    def on_stop(self, block: StopEvent) -> t.Iterable[ServerSentEvent]:
        return self._delegate.on_stop(block)

    def flush(self) -> t.Iterable[ServerSentEvent]:
        return self._delegate.flush()

    @classmethod
    def _event_id(cls, api: t.Literal["chat", "completion", "response"], generation_id: uuid.UUID | None, /) -> str:
        return cls._EVENT_ID_TEMPLATE.safe_substitute(
            {"prefix": cls._KIND_PREFIX[api], "message_id": (generation_id or uuid.uuid4()).hex}
        )
