import asyncio
import json
import typing as t
from collections.abc import AsyncGenerator

from flama import types
from flama.http.data_structures import FormData
from flama.http.requests.connection import HTTPConnection

__all__ = ["Request"]


def _parse_content_type(header: str) -> tuple[str, dict[str, str]]:
    """Parse a ``Content-Type`` header into ``(media_type, params)``."""
    parts = header.split(";")
    media_type = parts[0].strip().lower()
    params: dict[str, str] = {}
    for part in parts[1:]:
        part = part.strip()
        if "=" in part:
            k, _, v = part.partition("=")
            params[k.strip().lower()] = v.strip().strip('"')
    return media_type, params


class _EmptyReceive(types.Receive):
    async def __call__(self) -> types.Message:
        raise RuntimeError("Receive channel has not been made available")


class _EmptySend(types.Send):
    async def __call__(self, message: types.Message) -> None:
        raise RuntimeError("Send channel has not been made available")


class Request(HTTPConnection):
    """Incoming HTTP request.

    Wraps an ASGI *http* scope together with its ``receive`` and ``send`` channels to provide
    a high-level API for reading the request line, headers, body, and form data.

    :param scope: ASGI scope of type ``"http"``.
    :param receive: ASGI receive callable.
    :param send: ASGI send callable.
    """

    _form: FormData | None

    def __init__(
        self, scope: types.Scope, receive: types.Receive = _EmptyReceive(), send: types.Send = _EmptySend()
    ) -> None:
        super().__init__(scope)
        if scope["type"] != "http":
            raise RuntimeError("Request scope type must be 'http'")
        self._receive = receive
        self._send = send
        self._stream_consumed = False
        self._is_disconnected = False
        self._form = None

    @property
    def method(self) -> str:
        return t.cast(str, self.scope["method"])

    @property
    def receive(self) -> types.Receive:
        return self._receive

    async def stream(self) -> AsyncGenerator[bytes, None]:
        """Yield the raw request body as an async stream of byte chunks.

        :raises RuntimeError: If the stream has already been consumed.
        :raises ConnectionAbortedError: If the client disconnects mid-stream.
        """
        if hasattr(self, "_body"):
            yield self._body
            yield b""
            return

        if self._stream_consumed:
            raise RuntimeError("Stream consumed")

        while not self._stream_consumed:
            message = await self._receive()
            if message["type"] == "http.request":
                body = message.get("body", b"")
                if not message.get("more_body", False):
                    self._stream_consumed = True
                if body:
                    yield body
            elif message["type"] == "http.disconnect":
                self._is_disconnected = True
                raise ConnectionAbortedError()
        yield b""

    async def body(self) -> bytes:
        """Read and return the entire request body.

        The result is cached so subsequent calls return the same bytes without re-reading.
        """
        if not hasattr(self, "_body"):
            body = bytearray()
            async for chunk in self.stream():
                body.extend(chunk)
            self._body = bytes(body)
        return self._body

    async def json(self) -> t.Any:
        """Decode the request body as JSON.

        The result is cached after the first call.
        """
        if not hasattr(self, "_json"):
            self._json = json.loads(await self.body())
        return self._json

    async def form(self, *, max_files: int = 1000, max_fields: int = 1000) -> FormData:
        """Parse the request body as form data.

        Supports both ``application/x-www-form-urlencoded`` and ``multipart/form-data``.
        Multipart parsing streams directly from the ASGI ``receive`` callable via the
        Rust core (multer), avoiding full-body buffering.  The result is cached after the
        first call.

        :param max_files: Maximum file uploads allowed.
        :param max_fields: Maximum non-file fields allowed.
        :return: Parsed form data.
        """
        if self._form is None:
            content_type, options = _parse_content_type(self.headers.get("content-type", ""))

            if content_type == "multipart/form-data":
                boundary = options.get("boundary", "")
                self._form = await FormData.from_multipart(
                    self._receive, boundary, max_files=max_files, max_fields=max_fields
                )
            elif content_type == "application/x-www-form-urlencoded":
                body = await self.body()
                self._form = FormData.from_urlencoded(body)
            else:
                self._form = FormData()
        return self._form

    async def close(self) -> None:
        """Release resources held by parsed form data."""
        if self._form is not None:
            await self._form.close()

    async def is_disconnected(self) -> bool:
        """Non-blocking check for a client disconnect.

        Attempts to read from the receive channel without waiting. Returns ``True``
        if a ``http.disconnect`` message was received.
        """
        if not self._is_disconnected:
            message: types.Message = types.Message()
            try:
                message = await asyncio.wait_for(self._receive(), timeout=0)
            except (asyncio.TimeoutError, TimeoutError):
                pass
            if message.get("type") == "http.disconnect":
                self._is_disconnected = True
        return self._is_disconnected

    async def send_push_promise(self, path: str) -> None:
        """Send an HTTP/2 server push promise, if supported.

        :param path: The URL path to push.
        """
        if "http.response.push" in self.scope.get("extensions", {}):
            raw_headers: list[tuple[bytes, bytes]] = []
            for name in ("accept", "accept-encoding", "accept-language", "cache-control", "user-agent"):
                for value in self.headers.get_values(name):
                    raw_headers.append((name.encode("latin-1"), value.encode("latin-1")))
            await self._send(types.Message({"type": "http.response.push", "path": path, "headers": raw_headers}))
