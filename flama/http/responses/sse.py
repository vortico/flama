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
    data: str
    event: str | None = None
    id: str | None = None
    retry: int | None = None

    def encode(self) -> bytes:
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
