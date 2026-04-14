import typing as t

from flama import concurrency, types
from flama.middleware.base import Middleware

if t.TYPE_CHECKING:
    from flama.http.requests.http import Request
    from flama.http.responses.response import Response

__all__ = ["BaseHTTPMiddleware"]


class BaseHTTPMiddleware(Middleware):
    """Base class for HTTP middleware using before/after/error hooks.

    Subclass and override any combination of :meth:`before`, :meth:`after`, and
    :meth:`error` to implement custom middleware logic.  Non-HTTP scopes are
    passed through to the inner application unchanged.

    Unlike a dispatch/call_next pattern, this approach does **not** buffer the
    response body -- it intercepts only the ``http.response.start`` ASGI message,
    so streaming responses work with zero overhead.
    """

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        if scope["type"] != "http":
            await concurrency.run(self.app, scope, receive, send)
            return

        from flama.http.requests.http import Request
        from flama.http.responses.response import Response

        request = Request(scope, receive)

        early_response = await self.before(request)
        if early_response is not None:
            await early_response(scope, receive, send)
            return

        response_started = False

        async def send_wrapper(message: types.Message) -> None:
            nonlocal response_started

            if message["type"] == "http.response.start":
                response_started = True
                response = Response(status_code=message["status"])
                response.raw_headers = list(message.get("headers", []))
                modified = await self.after(request, response)
                await send(
                    types.Message(
                        {
                            "type": "http.response.start",
                            "status": modified.status_code,
                            "headers": modified.raw_headers,
                        }
                    )
                )
            else:
                await send(message)

        try:
            await concurrency.run(self.app, scope, receive, send_wrapper)
        except Exception as exc:
            error_response = await self.error(request, exc)
            if error_response is not None and not response_started:
                await error_response(scope, receive, send)
                return
            raise

    async def before(self, request: "Request") -> "Response | None":
        """Hook called before the downstream application.

        Return a :class:`~flama.http.responses.response.Response` to short-circuit
        the request (the downstream app will not be called).  Return ``None`` to
        continue normally.

        :param request: The incoming HTTP request.
        :return: A response to short-circuit, or ``None`` to continue.
        """
        return None  # pragma: no cover

    async def after(self, request: "Request", response: "Response") -> "Response":
        """Hook called after the downstream application produces a response start.

        The *response* object carries ``status_code`` and ``headers`` from the
        ``http.response.start`` ASGI message.  Modify them in place or return a
        new :class:`~flama.http.responses.response.Response`.  The response body
        streams through unchanged -- it is **not** buffered.

        :param request: The incoming HTTP request.
        :param response: The response metadata (status and headers).
        :return: The (possibly modified) response.
        """
        return response  # pragma: no cover

    async def error(self, request: "Request", exc: Exception) -> "Response | None":
        """Hook called when the downstream application raises an exception.

        Return a :class:`~flama.http.responses.response.Response` to send an
        error response (only possible if the response has not started yet).
        Return ``None`` to let the exception propagate.

        :param request: The incoming HTTP request.
        :param exc: The exception raised by the downstream app.
        :return: An error response, or ``None`` to re-raise.
        """
        return None  # pragma: no cover
