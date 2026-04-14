import typing as t

from flama import concurrency, exceptions, types
from flama.codecs import BrotliCodec, CompressionCodec, CompressionNegotiator, GzipCodec
from flama.http.data_structures import Headers, MutableHeaders
from flama.middleware.base import Middleware

if t.TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["CompressionMiddleware"]

_EXCLUDED_CONTENT_TYPES = ("text/event-stream",)


class CompressionMiddleware(Middleware):
    """ASGI middleware that compresses response bodies.

    Negotiates the best compression algorithm from the request's ``Accept-Encoding`` header, trying each configured
    codec in priority order and falling back to no compression.

    :param minimum_size: Minimum response body size (bytes) to trigger compression.
    :param codecs: Compression codecs in preference order. Defaults to ``[BrotliCodec(), GzipCodec()]``.
    """

    def __init__(self, minimum_size: int = 500, codecs: "Sequence[CompressionCodec] | None" = None) -> None:
        self._negotiator = CompressionNegotiator(codecs if codecs else [BrotliCodec(), GzipCodec()])
        self._minimum_size = minimum_size

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        if scope["type"] != "http":
            await concurrency.run(self.app, scope, receive, send)
            return

        try:
            codec = self._negotiator.negotiate(Headers(scope=scope).get("accept-encoding"))
        except exceptions.NoCodecAvailable:
            await concurrency.run(self.app, scope, receive, send)
            return

        initial_message: types.Message | None = None
        started = False

        async def _send(message: types.Message) -> None:
            nonlocal initial_message, started

            if message["type"] == "http.response.start":
                initial_message = message
                return

            if message["type"] == "http.response.body":
                assert initial_message is not None

                body = message.get("body", b"")
                more_body = message.get("more_body", False)

                if not started:
                    started = True

                    if self._should_skip(initial_message, body, more_body):
                        await send(initial_message)
                        await send(message)
                        return

                    compressed = await codec.decode((body, not more_body))
                    self._patch_headers(initial_message, codec, body, compressed, more_body)
                    message["body"] = compressed
                    await send(initial_message)
                    await send(message)
                else:
                    message["body"] = await codec.decode((body, not more_body))
                    await send(message)

                return

            if initial_message is not None:
                await send(initial_message)
            await send(message)

        await concurrency.run(self.app, scope, receive, _send)

    def _should_skip(self, initial_message: types.Message, body: bytes, more_body: bool) -> bool:
        """Decide whether compression should be skipped for the first body chunk.

        :param initial_message: Buffered ``http.response.start`` message.
        :param body: First body chunk.
        :param more_body: Whether more chunks will follow.
        :return: ``True`` when compression must be skipped.
        """
        headers = Headers(raw=initial_message["headers"])

        if "content-encoding" in headers or headers.get("content-type", "").startswith("text/event-stream"):
            return True

        return len(body) < self._minimum_size and not more_body

    @staticmethod
    def _patch_headers(
        initial_message: types.Message,
        codec: CompressionCodec,
        original: bytes,
        compressed: bytes,
        more_body: bool,
    ) -> None:
        """Update response headers to reflect compression.

        :param initial_message: Buffered ``http.response.start`` message.
        :param codec: Compression codec used.
        :param original: Original uncompressed body.
        :param compressed: Compressed body.
        :param more_body: Whether more chunks will follow.
        """
        headers = MutableHeaders(raw=initial_message["headers"])
        headers.add_vary_header("Accept-Encoding")

        if compressed != original:
            headers["Content-Encoding"] = codec.encoding
            if more_body:
                del headers["Content-Length"]
            else:
                headers["Content-Length"] = str(len(compressed))
