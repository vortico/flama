import typing as t
from collections.abc import AsyncIterable, Iterable

from flama import concurrency, types
from flama.http.responses.response import Response

if t.TYPE_CHECKING:
    from collections.abc import Mapping

    from flama.background import BackgroundTask

__all__ = ["StreamingResponse"]


class StreamingResponse(Response):
    body_iterator: "AsyncIterable[str | bytes]"

    def __init__(
        self,
        content: "AsyncIterable[str | bytes] | Iterable[str | bytes]",
        status_code: int = 200,
        headers: "Mapping[str, str] | None" = None,
        media_type: str | None = None,
        background: "BackgroundTask | None" = None,
    ) -> None:
        if isinstance(content, AsyncIterable):
            self.body_iterator = t.cast("AsyncIterable[str | bytes]", content)
        else:
            self.body_iterator = concurrency.iterate_in_threadpool(content)

        super().__init__(
            content=b"",
            status_code=status_code,
            headers=headers,
            media_type=media_type,
            background=background,
        )

    def _init_headers(self, headers: "Mapping[str, str] | None" = None) -> None:
        super()._init_headers(headers)
        self.raw_headers = [(k, v) for k, v in self.raw_headers if k != b"content-length"]

    async def _stream_response(self, send: types.Send) -> None:
        await send(
            types.Message({"type": "http.response.start", "status": self.status_code, "headers": self.raw_headers})
        )

        async for chunk in self.body_iterator:
            if not isinstance(chunk, bytes | memoryview):
                chunk = chunk.encode(self.charset)
            await send(types.Message({"type": "http.response.body", "body": chunk, "more_body": True}))

        await send(types.Message({"type": "http.response.body", "body": b"", "more_body": False}))

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        try:
            await self._stream_response(send)
        except OSError:
            return

        if self.background is not None:
            await self.background()
