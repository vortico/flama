import dataclasses
import typing as t

from flama import concurrency
from flama.http.responses.response import Response, StreamingResponse

if t.TYPE_CHECKING:
    from collections.abc import AsyncIterable, Iterable, Mapping

    from flama.background import BackgroundTask


__all__ = ["ServerSentEvent", "ServerSentEventResponse"]


@dataclasses.dataclass
class ServerSentEvent:
    """A single Server-Sent Event frame.

    Emitting a frame with only :attr:`comment` set produces a comment line (``": ..."``)
    instead of a regular event. Comment-only frames are used as heartbeats: they keep the
    HTTP connection alive through proxies that enforce read timeouts without affecting the
    client-side ``EventSource`` event handlers.

    :param data: Event payload (one ``data:`` line per ``\\n``-separated chunk).
    :param event: Optional event name; clients dispatch on it via ``addEventListener``.
    :param id: Optional event id; the latest received id is replayed by clients via
        ``Last-Event-ID`` after a reconnection.
    :param retry: Optional reconnection retry interval in milliseconds.
    :param comment: Optional comment line; if set, the frame is rendered as a comment-only
        line and other fields are ignored.
    """

    data: str = ""
    event: str | None = None
    id: str | None = None
    retry: int | None = None
    comment: str | None = None

    def encode(self) -> bytes:
        if self.comment is not None:
            return f": {self.comment}\n\n".encode()
        lines: list[str] = []
        if self.id is not None:
            lines.append(f"id: {self.id}")
        if self.event is not None:
            lines.append(f"event: {self.event}")
        if self.retry is not None:
            lines.append(f"retry: {self.retry}")
        for line in self.data.splitlines():
            lines.append(f"data: {line}")
        return ("\n".join(lines) + "\n\n").encode()


class ServerSentEventResponse(StreamingResponse[ServerSentEvent | str]):
    media_type = "text/event-stream"

    def __init__(
        self,
        content: "AsyncIterable[ServerSentEvent | str] | Iterable[ServerSentEvent | str]",
        status_code: int = 200,
        headers: "Mapping[str, str] | None" = None,
        background: "BackgroundTask | None" = None,
    ) -> None:
        self.content = concurrency.iterate(content)
        Response.__init__(self, status_code=status_code, headers=headers, background=background)

    def encode(self, chunk: "ServerSentEvent | str") -> bytes:
        if isinstance(chunk, ServerSentEvent):
            return chunk.encode()
        return ServerSentEvent(data=chunk).encode()

    def _init_headers(self, headers: "Mapping[str, str] | None" = None) -> None:
        super()._init_headers(headers)
        raw = dict(self.raw_headers)
        raw.setdefault(b"cache-control", b"no-cache")
        raw.setdefault(b"connection", b"keep-alive")
        self.raw_headers = list(raw.items())
